"""
Deteccion de regimen de mercado y fuerza relativa vs Merval.
Bull/Bear/Sideways afecta los umbrales y pesos del scoring.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd
import ta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price import PriceDaily

logger = logging.getLogger(__name__)

# Tickers proxy del mercado (se prueba en orden)
MARKET_PROXIES = ["GGAL", "BMA", "BBAR", "TECO2"]

# Cache en memoria del regimen (se refresca por el scanner)
_cached_regime: dict | None = None
_cached_merval_df: pd.DataFrame | None = None


async def load_market_data(db: AsyncSession, limit: int = 500) -> Optional[pd.DataFrame]:
    """Carga datos del proxy de mercado (GGAL u otro líquido)."""
    global _cached_merval_df

    for ticker in MARKET_PROXIES:
        result = await db.execute(
            select(PriceDaily)
            .where(PriceDaily.ticker == ticker)
            .order_by(PriceDaily.date.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        if len(rows) >= 50:
            data = [{
                "date": r.date,
                "open": float(r.open or r.close),
                "high": float(r.high or r.close),
                "low": float(r.low or r.close),
                "close": float(r.close),
                "volume": float(r.volume or 0),
            } for r in rows]
            df = pd.DataFrame(data).sort_values("date").reset_index(drop=True)
            _cached_merval_df = df
            logger.info(f"Proxy de mercado: {ticker} ({len(df)} barras)")
            return df

    return None


def get_cached_merval_df() -> Optional[pd.DataFrame]:
    return _cached_merval_df


def detect_regime(merval_df: Optional[pd.DataFrame]) -> dict:
    """
    Detecta regimen de mercado: bull / bear / sideways.

    Returns:
        {
            "regime": "bull" | "bear" | "sideways",
            "strength": float 0-1,
            "volatility": "low" | "normal" | "high",
            "description": str,
            "weight_modifier": float (multiplier para buy signals en bear markets)
        }
    """
    global _cached_regime

    if merval_df is None or len(merval_df) < 50:
        return _default_regime()

    close = merval_df["close"]
    high = merval_df["high"]
    low = merval_df["low"]
    current = float(close.iloc[-1])

    # ── Medias moviles ──
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else sma50

    # ── Retornos ──
    ret_20d = (current / float(close.iloc[-20]) - 1) * 100 if len(close) >= 20 else 0
    ret_60d = (current / float(close.iloc[-60]) - 1) * 100 if len(close) >= 60 else 0

    # ── Volatilidad (ATR%) ──
    atr_pct = 0.0
    if len(merval_df) >= 14:
        atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1]
        atr_pct = float(atr / current * 100) if current > 0 else 0

    # ── ADX ──
    adx_val = 20.0
    if len(merval_df) >= 14:
        adx_val = float(ta.trend.ADXIndicator(high, low, close, window=14).adx().iloc[-1])

    # ── Scoring de regimen ──
    bull_pts = 0.0
    total = 0.0

    # Precio vs SMA50
    total += 1
    if current > float(sma50):
        bull_pts += 1

    # Precio vs SMA200
    if not pd.isna(sma200):
        total += 1
        if current > float(sma200):
            bull_pts += 1

    # Golden/Death cross
    if not pd.isna(sma200):
        total += 1
        if float(sma50) > float(sma200):
            bull_pts += 1

    # Retorno 20d
    total += 1
    if ret_20d > 3:
        bull_pts += 1
    elif ret_20d > 0:
        bull_pts += 0.5

    # Retorno 60d
    if len(close) >= 60:
        total += 1
        if ret_60d > 10:
            bull_pts += 1
        elif ret_60d > 0:
            bull_pts += 0.5

    ratio = bull_pts / total if total > 0 else 0.5

    # Clasificacion
    if ratio >= 0.7:
        regime = "bull"
        weight_mod = 1.15  # Boost buy signals
        desc = f"Mercado alcista ({ret_20d:+.1f}% 20d)"
    elif ratio <= 0.3:
        regime = "bear"
        weight_mod = 0.80  # Dampen buy signals, boost sell
        desc = f"Mercado bajista ({ret_20d:+.1f}% 20d)"
    else:
        regime = "sideways"
        weight_mod = 1.0
        desc = f"Mercado lateral ({ret_20d:+.1f}% 20d)"

    # Volatilidad
    if atr_pct > 3:
        vol = "high"
    elif atr_pct > 1.5:
        vol = "normal"
    else:
        vol = "low"

    _cached_regime = {
        "regime": regime,
        "strength": round(ratio, 2),
        "volatility": vol,
        "description": desc,
        "weight_modifier": weight_mod,
        "adx": round(adx_val, 1) if not pd.isna(adx_val) else 0,
        "ret_20d": round(ret_20d, 2),
        "ret_60d": round(ret_60d, 2),
        "atr_pct": round(atr_pct, 2),
    }
    return _cached_regime


def get_cached_regime() -> dict:
    return _cached_regime or _default_regime()


def _default_regime() -> dict:
    return {
        "regime": "sideways",
        "strength": 0.5,
        "volatility": "normal",
        "description": "Sin datos de mercado",
        "weight_modifier": 1.0,
    }


# ────────────────────────────────────────
# FUERZA RELATIVA vs MERVAL
# ────────────────────────────────────────

def calculate_relative_strength(ticker_df: pd.DataFrame, merval_df: pd.DataFrame) -> dict:
    """
    Calcula fuerza relativa de un ticker vs el proxy de mercado.
    Periodos: 5d, 20d, 60d.
    """
    if ticker_df is None or merval_df is None:
        return {}
    if len(ticker_df) < 20 or len(merval_df) < 20:
        return {}

    ticker_close = ticker_df["close"]
    merval_close = merval_df["close"]

    result = {}

    for period, label in [(5, "5d"), (20, "20d"), (60, "60d")]:
        if len(ticker_close) >= period and len(merval_close) >= period:
            t_ret = float(ticker_close.iloc[-1]) / float(ticker_close.iloc[-period]) - 1
            m_ret = float(merval_close.iloc[-1]) / float(merval_close.iloc[-period]) - 1
            rs = (t_ret - m_ret) * 100
            result[f"rs_{label}"] = round(rs, 2)

    # Metrica principal: 20d
    if "rs_20d" in result:
        result["rs_vs_merval"] = result["rs_20d"]

    return result
