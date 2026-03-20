"""
Senales macro para el scoring:
1. Riesgo pais (tendencia 7d)
2. Spread CCL/MEP (compresion = alcista)
3. Dolar CCL tendencia (estable = alcista para acciones)
4. S&P 500 lag 1 dia (para CEDEARs)
"""
import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.macro import MacroData

logger = logging.getLogger(__name__)

# Cache
_macro_signals: dict = {}
_sp500_last: dict = {}


async def load_macro_signals(db: AsyncSession) -> dict:
    """
    Carga indicadores macro recientes y calcula tendencias.
    Retorna dict con senales listas para el scoring.
    """
    global _macro_signals

    signals = {}

    # ── Riesgo pais ──
    rp = await _get_indicator_series(db, "riesgo_pais", days=14)
    if len(rp) >= 7:
        current = rp[-1]
        prev_7d = rp[-7] if len(rp) >= 7 else rp[0]
        if prev_7d > 0:
            rp_change_7d = (current / prev_7d - 1) * 100
            signals["riesgo_pais"] = round(current, 0)
            signals["riesgo_pais_7d_chg"] = round(rp_change_7d, 2)

    # ── Dolar CCL ──
    ccl = await _get_indicator_series(db, "dolar_ccl", days=14)
    if not ccl:
        ccl = await _get_indicator_series(db, "ccl", days=14)
    if len(ccl) >= 7:
        current = ccl[-1]
        prev_7d = ccl[-7] if len(ccl) >= 7 else ccl[0]
        if prev_7d > 0:
            signals["ccl"] = round(current, 2)
            signals["ccl_7d_chg"] = round((current / prev_7d - 1) * 100, 2)

    # ── Dolar MEP ──
    mep = await _get_indicator_series(db, "dolar_mep", days=14)
    if not mep:
        mep = await _get_indicator_series(db, "mep", days=14)
    if len(mep) >= 2:
        signals["mep"] = round(mep[-1], 2)

    # ── Spread CCL/MEP (brecha) ──
    if "ccl" in signals and "mep" in signals and signals["mep"] > 0:
        spread = (signals["ccl"] / signals["mep"] - 1) * 100
        signals["ccl_mep_spread"] = round(spread, 2)

        # Spread historico: comparar con hace 7 dias
        if len(ccl) >= 7 and len(mep) >= 7:
            spread_prev = (ccl[-7] / mep[-7] - 1) * 100 if mep[-7] > 0 else spread
            signals["spread_7d_chg"] = round(spread - spread_prev, 2)

    # ── S&P 500 (lag 1 dia) ──
    sp500 = await _load_sp500()
    if sp500:
        signals.update(sp500)

    _macro_signals = signals
    logger.info(f"Macro signals loaded: {list(signals.keys())}")
    return signals


def get_cached_macro_signals() -> dict:
    return _macro_signals


async def _get_indicator_series(db: AsyncSession, indicator: str, days: int = 14) -> list[float]:
    """Carga serie temporal de un indicador macro."""
    result = await db.execute(
        select(MacroData)
        .where(MacroData.indicator == indicator)
        .order_by(MacroData.date.desc())
        .limit(days)
    )
    rows = result.scalars().all()
    if not rows:
        return []
    return [float(r.value) for r in reversed(rows)]


async def _load_sp500() -> dict:
    """Carga ultimo retorno del S&P 500 via yfinance."""
    global _sp500_last
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY")
        hist = spy.history(period="5d")
        if hist is not None and len(hist) >= 2:
            last_close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2])
            ret = (last_close / prev_close - 1) * 100
            _sp500_last = {
                "sp500_last": round(last_close, 2),
                "sp500_return_1d": round(ret, 2),
            }
            # 5-day return
            if len(hist) >= 5:
                ret_5d = (last_close / float(hist["Close"].iloc[0]) - 1) * 100
                _sp500_last["sp500_return_5d"] = round(ret_5d, 2)
            return _sp500_last
    except Exception as e:
        logger.warning(f"S&P 500 fetch failed: {e}")
    return _sp500_last  # return cached if fetch fails
