"""
Servicio de ingesta de datos de mercado.
Fuentes: Data912 (principal), DolarAPI, BCRA APIs, yfinance (complemento).
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
import pandas as pd
from sqlalchemy import select, text, inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.asset import Asset, AssetType
from app.models.price import PriceDaily
from app.models.macro import MacroData

logger = logging.getLogger(__name__)
settings = get_settings()


def _upsert(engine_url: str):
    """Return the appropriate insert function based on the database dialect."""
    if engine_url.startswith("sqlite"):
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    return dialect_insert


def db_insert(model):
    """Create a dialect-aware insert statement."""
    return _upsert(settings.database_url)(model)

# Timeout for HTTP requests
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


# ──────────────────────────────────────────────
# DATA912 - Market Data (principal)
# ──────────────────────────────────────────────

DATA912 = settings.data912_base_url

LIVE_ENDPOINTS = {
    AssetType.ACCION: "/live/arg_stocks",
    AssetType.CEDEAR: "/live/arg_cedears",
    AssetType.BONO_SOBERANO: "/live/arg_bonds",
    AssetType.LETRA: "/live/arg_notes",
    AssetType.ON: "/live/arg_corp",
}

HISTORICAL_ENDPOINTS = {
    AssetType.ACCION: "/historical/stocks",
    AssetType.CEDEAR: "/historical/cedears",
    AssetType.BONO_SOBERANO: "/historical/bonds",
}


async def fetch_json(url: str, headers: dict | None = None) -> list | dict | None:
    """Generic async HTTP GET that returns parsed JSON."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP {e.response.status_code} fetching {url}")
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
    return None


async def sync_assets_from_live(db: AsyncSession) -> int:
    """
    Fetch all live panels from Data912 and upsert assets into the DB.
    Returns number of assets synced.
    """
    total = 0
    for asset_type, endpoint in LIVE_ENDPOINTS.items():
        data = await fetch_json(f"{DATA912}{endpoint}")
        if not data:
            logger.warning(f"No data from {endpoint}")
            continue

        for item in data:
            ticker = item.get("symbol", "").strip()
            if not ticker:
                continue

            stmt = db_insert(Asset).values(
                ticker=ticker,
                name=ticker,  # Data912 doesn't provide full names
                asset_type=asset_type,
                currency="ARS",
                is_active=True,
            ).on_conflict_do_update(
                index_elements=["ticker"],
                set_={"is_active": True, "asset_type": asset_type},
            )
            await db.execute(stmt)
            total += 1

    await db.commit()
    logger.info(f"Synced {total} assets from Data912 live panels")
    return total


async def fetch_live_prices(db: AsyncSession) -> int:
    """
    Fetch current prices from all live panels and store as today's prices.
    Uses UPSERT to avoid duplicates.
    """
    today = date.today()
    total = 0

    for asset_type, endpoint in LIVE_ENDPOINTS.items():
        data = await fetch_json(f"{DATA912}{endpoint}")
        if not data:
            continue

        for item in data:
            ticker = item.get("symbol", "").strip()
            price = item.get("c")
            if not ticker or price is None:
                continue

            stmt = db_insert(PriceDaily).values(
                ticker=ticker,
                date=today,
                close=float(price),
                volume=item.get("v"),
                change_pct=item.get("pct_change"),
            ).on_conflict_do_update(
                index_elements=["ticker", "date"],
                set_={
                    "close": float(price),
                    "volume": item.get("v"),
                    "change_pct": item.get("pct_change"),
                },
            )
            await db.execute(stmt)
            total += 1

    await db.commit()
    logger.info(f"Updated {total} live prices")
    return total


async def fetch_historical_prices(
    db: AsyncSession,
    ticker: str,
    asset_type: AssetType,
    since: Optional[date] = None,
) -> int:
    """
    Fetch full historical OHLCV for a ticker from Data912 and store in DB.
    Returns number of rows inserted.
    """
    base = HISTORICAL_ENDPOINTS.get(asset_type)
    if not base:
        logger.warning(f"No historical endpoint for {asset_type}")
        return 0

    data = await fetch_json(f"{DATA912}{base}/{ticker}")
    if not data:
        return 0

    count = 0
    for bar in data:
        bar_date = bar.get("date")
        if not bar_date:
            continue
        try:
            d = datetime.strptime(bar_date, "%Y-%m-%d").date()
        except ValueError:
            continue

        if since and d < since:
            continue

        stmt = db_insert(PriceDaily).values(
            ticker=ticker,
            date=d,
            open=bar.get("o"),
            high=bar.get("h"),
            low=bar.get("l"),
            close=bar.get("c"),
            volume=bar.get("v"),
            change_pct=bar.get("dr"),
        ).on_conflict_do_nothing(index_elements=["ticker", "date"])
        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info(f"Stored {count} historical bars for {ticker}")
    return count


async def fetch_all_historical(db: AsyncSession, since: Optional[date] = None) -> int:
    """Fetch historical data for ALL assets in DB. Use for initial load."""
    result = await db.execute(select(Asset).where(Asset.is_active == True))
    assets = result.scalars().all()
    total = 0
    for asset in assets:
        if asset.asset_type in HISTORICAL_ENDPOINTS:
            n = await fetch_historical_prices(db, asset.ticker, asset.asset_type, since)
            total += n
    return total


# ──────────────────────────────────────────────
# DOLAR API
# ──────────────────────────────────────────────

DOLAR_API = settings.dolar_api_base_url

DOLAR_ENDPOINTS = {
    "dolar_oficial": "/v1/dolares/oficial",
    "dolar_blue": "/v1/dolares/blue",
    "dolar_mep": "/v1/dolares/bolsa",
    "dolar_ccl": "/v1/dolares/contadoconliqui",
    "dolar_mayorista": "/v1/dolares/mayorista",
    "dolar_tarjeta": "/v1/dolares/tarjeta",
    "dolar_cripto": "/v1/dolares/cripto",
}


async def fetch_dolar_rates(db: AsyncSession) -> dict:
    """Fetch all dollar rates and store in macro_data. Returns current rates dict."""
    today = date.today()
    rates = {}

    for indicator, endpoint in DOLAR_ENDPOINTS.items():
        data = await fetch_json(f"{DOLAR_API}{endpoint}")
        if not data:
            continue

        venta = data.get("venta")
        if venta is None:
            continue

        rates[indicator] = {
            "compra": data.get("compra"),
            "venta": venta,
        }

        stmt = db_insert(MacroData).values(
            indicator=indicator,
            date=today,
            value=float(venta),
            extra=f"compra={data.get('compra')}",
        ).on_conflict_do_update(
            index_elements=["indicator", "date"],
            set_={"value": float(venta), "extra": f"compra={data.get('compra')}"},
        )
        await db.execute(stmt)

    await db.commit()
    logger.info(f"Updated {len(rates)} dollar rates")
    return rates


# ──────────────────────────────────────────────
# DATA912 - MEP & CCL rates
# ──────────────────────────────────────────────

async def fetch_mep_ccl_rates(db: AsyncSession) -> dict:
    """Fetch MEP and CCL detailed rates from Data912."""
    rates = {}
    today = date.today()

    for name, endpoint in [("mep_detail", "/live/mep"), ("ccl_detail", "/live/ccl")]:
        data = await fetch_json(f"{DATA912}{endpoint}")
        if data:
            rates[name] = data

    return rates


# ──────────────────────────────────────────────
# BCRA API (Official v4.0)
# ──────────────────────────────────────────────

BCRA_API = settings.bcra_api_base_url

# Key variable IDs from BCRA
BCRA_VARIABLES = {
    "reservas_internacionales": 1,
    "tipo_cambio_minorista": 4,
    "tipo_cambio_mayorista": 5,
    "tasa_badlar": 7,
    "tasa_depositos_30d": 12,
    "tasa_prestamos_personales": 14,
    "base_monetaria": 15,
    "inflacion_mensual": 27,
    "inflacion_interanual": 28,
    "inflacion_esperada": 29,
    "cer": 30,
    "uva": 31,
}


async def fetch_bcra_variable(
    db: AsyncSession,
    indicator_name: str,
    variable_id: int,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
) -> int:
    """Fetch a BCRA variable time series and store in macro_data."""
    url = f"{BCRA_API}/estadisticas/v4.0/Monetarias/{variable_id}"
    params = {}
    if desde:
        params["Desde"] = desde
    if hasta:
        params["Hasta"] = hasta
    params["Limit"] = 3000

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"Error fetching BCRA variable {variable_id}: {e}")
        return 0

    results = data.get("results", [])
    count = 0
    for item in results:
        fecha = item.get("fecha")
        valor = item.get("valor")
        if fecha is None or valor is None:
            continue

        try:
            d = datetime.strptime(fecha, "%Y-%m-%d").date()
        except ValueError:
            continue

        stmt = db_insert(MacroData).values(
            indicator=indicator_name,
            date=d,
            value=float(valor),
        ).on_conflict_do_nothing(index_elements=["indicator", "date"])
        await db.execute(stmt)
        count += 1

    await db.commit()
    logger.info(f"Stored {count} BCRA records for {indicator_name}")
    return count


async def fetch_all_bcra_data(db: AsyncSession, desde: Optional[str] = None) -> int:
    """Fetch all key BCRA variables."""
    total = 0
    for name, var_id in BCRA_VARIABLES.items():
        n = await fetch_bcra_variable(db, name, var_id, desde=desde)
        total += n
    return total


# ──────────────────────────────────────────────
# RIESGO PAIS (from estadisticasbcra.com)
# ──────────────────────────────────────────────

async def fetch_riesgo_pais(db: AsyncSession) -> Optional[float]:
    """Fetch riesgo pais from the unofficial BCRA stats API."""
    token = settings.estadisticas_bcra_token
    if not token:
        logger.warning("No estadisticas_bcra_token configured, skipping riesgo_pais")
        return None

    url = "https://api.estadisticasbcra.com/riesgo_pais"
    headers = {"Authorization": f"BEARER {token}"}
    data = await fetch_json(url, headers=headers)

    if not data:
        return None

    # Store last 30 days
    count = 0
    latest_value = None
    for item in data[-30:]:
        d_str = item.get("d")
        v = item.get("v")
        if not d_str or v is None:
            continue
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        stmt = db_insert(MacroData).values(
            indicator="riesgo_pais",
            date=d,
            value=float(v),
        ).on_conflict_do_nothing(index_elements=["indicator", "date"])
        await db.execute(stmt)
        count += 1
        latest_value = v

    await db.commit()
    logger.info(f"Stored {count} riesgo_pais records")
    return latest_value


# ──────────────────────────────────────────────
# MERVAL INDEX (from estadisticasbcra.com)
# ──────────────────────────────────────────────

async def fetch_merval_index(db: AsyncSession) -> Optional[float]:
    """Fetch Merval index historical data."""
    token = settings.estadisticas_bcra_token
    if not token:
        return None

    url = "https://api.estadisticasbcra.com/merval"
    headers = {"Authorization": f"BEARER {token}"}
    data = await fetch_json(url, headers=headers)

    if not data:
        return None

    count = 0
    latest = None
    for item in data[-60:]:
        d_str = item.get("d")
        v = item.get("v")
        if not d_str or v is None:
            continue
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        stmt = db_insert(MacroData).values(
            indicator="merval",
            date=d,
            value=float(v),
        ).on_conflict_do_nothing(index_elements=["indicator", "date"])
        await db.execute(stmt)
        count += 1
        latest = v

    await db.commit()
    return latest


# ──────────────────────────────────────────────
# FULL SYNC ORCHESTRATOR
# ──────────────────────────────────────────────

async def run_full_daily_sync(db: AsyncSession) -> dict:
    """
    Run the complete daily data sync pipeline.
    Called by the post-market cron job (17:15 AR).
    """
    results = {}

    # 1. Sync asset list
    results["assets_synced"] = await sync_assets_from_live(db)

    # 2. Fetch closing prices
    results["prices_updated"] = await fetch_live_prices(db)

    # 3. Dollar rates
    results["dolar_rates"] = await fetch_dolar_rates(db)

    # 4. BCRA macro data (last 7 days)
    week_ago = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
    results["bcra_records"] = await fetch_all_bcra_data(db, desde=week_ago)

    # 5. Riesgo pais & Merval
    results["riesgo_pais"] = await fetch_riesgo_pais(db)
    results["merval"] = await fetch_merval_index(db)

    logger.info(f"Full daily sync complete: {results}")
    return results
