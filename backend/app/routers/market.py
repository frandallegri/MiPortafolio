"""
Market data endpoints: live prices, dollar rates, macro data.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.price import PriceDaily
from app.models.macro import MacroData
from app.services.data_ingestion import (
    fetch_dolar_rates,
    fetch_live_prices,
    fetch_mep_ccl_rates,
    DATA912,
    fetch_json,
)

router = APIRouter(prefix="/market", tags=["market"], dependencies=[Depends(get_current_user)])


@router.get("/live/stocks")
async def get_live_stocks():
    """Get live Argentine stock prices from Data912."""
    data = await fetch_json(f"{DATA912}/live/arg_stocks")
    return data or []


@router.get("/live/cedears")
async def get_live_cedears():
    """Get live CEDEAR prices."""
    data = await fetch_json(f"{DATA912}/live/arg_cedears")
    return data or []


@router.get("/live/bonds")
async def get_live_bonds():
    """Get live bond prices."""
    data = await fetch_json(f"{DATA912}/live/arg_bonds")
    return data or []


@router.get("/live/all")
async def get_live_all():
    """Get all live prices grouped by type."""
    from app.services.data_ingestion import LIVE_ENDPOINTS
    result = {}
    for asset_type, endpoint in LIVE_ENDPOINTS.items():
        data = await fetch_json(f"{DATA912}{endpoint}")
        result[asset_type.value] = data or []
    return result


@router.get("/dollar")
async def get_dollar_rates(db: AsyncSession = Depends(get_db)):
    """Get current dollar rates (MEP, CCL, blue, oficial)."""
    rates = await fetch_dolar_rates(db)
    return rates


@router.get("/mep-ccl")
async def get_mep_ccl(db: AsyncSession = Depends(get_db)):
    """Get detailed MEP and CCL rates from Data912."""
    return await fetch_mep_ccl_rates(db)


@router.get("/macro/latest")
async def get_latest_macro(db: AsyncSession = Depends(get_db)):
    """Get the latest value for each macro indicator."""
    subq = (
        select(
            MacroData.indicator,
            func.max(MacroData.date).label("max_date"),
        )
        .group_by(MacroData.indicator)
        .subquery()
    )

    result = await db.execute(
        select(MacroData)
        .join(subq, (MacroData.indicator == subq.c.indicator) & (MacroData.date == subq.c.max_date))
    )
    rows = result.scalars().all()

    return {
        r.indicator: {"value": r.value, "date": r.date.isoformat(), "extra": r.extra}
        for r in rows
    }


@router.get("/prices/{ticker}")
async def get_price_history(
    ticker: str,
    days: int = Query(default=90, ge=1, le=3000),
    db: AsyncSession = Depends(get_db),
):
    """Get historical prices for a ticker."""
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(PriceDaily)
        .where(PriceDaily.ticker == ticker.upper(), PriceDaily.date >= since)
        .order_by(PriceDaily.date.asc())
    )
    rows = result.scalars().all()

    return [
        {
            "date": r.date.isoformat(),
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
            "change_pct": r.change_pct,
        }
        for r in rows
    ]
