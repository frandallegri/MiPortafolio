"""
Umbrales adaptativos por ticker.
En vez de RSI <30 = sobrevendido para todos, calcula percentiles
del historial propio de cada ticker.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Cache de umbrales por ticker
_thresholds_cache: dict[str, dict] = {}


def compute_adaptive_thresholds(df: pd.DataFrame, ticker: str) -> dict:
    """
    Calcula umbrales adaptativos basados en el historial del ticker.
    Usa percentiles 10/90 para sobrevendido/sobrecomprado.
    """
    if len(df) < 100:
        return {}

    thresholds = {}

    # RSI
    rsi = df.get("rsi_14")
    if rsi is not None:
        rsi_clean = rsi.dropna()
        if len(rsi_clean) > 50:
            thresholds["rsi_oversold"] = round(float(np.percentile(rsi_clean, 15)), 1)
            thresholds["rsi_overbought"] = round(float(np.percentile(rsi_clean, 85)), 1)

    # Stochastic
    stoch = df.get("stoch_k")
    if stoch is not None:
        s_clean = stoch.dropna()
        if len(s_clean) > 50:
            thresholds["stoch_oversold"] = round(float(np.percentile(s_clean, 10)), 1)
            thresholds["stoch_overbought"] = round(float(np.percentile(s_clean, 90)), 1)

    # Williams %R
    wr = df.get("williams_r")
    if wr is not None:
        w_clean = wr.dropna()
        if len(w_clean) > 50:
            thresholds["williams_oversold"] = round(float(np.percentile(w_clean, 10)), 1)
            thresholds["williams_overbought"] = round(float(np.percentile(w_clean, 90)), 1)

    # CCI
    cci = df.get("cci_20")
    if cci is not None:
        c_clean = cci.dropna()
        if len(c_clean) > 50:
            thresholds["cci_oversold"] = round(float(np.percentile(c_clean, 10)), 1)
            thresholds["cci_overbought"] = round(float(np.percentile(c_clean, 90)), 1)

    # MFI
    mfi = df.get("mfi_14")
    if mfi is not None:
        m_clean = mfi.dropna()
        if len(m_clean) > 50:
            thresholds["mfi_oversold"] = round(float(np.percentile(m_clean, 15)), 1)
            thresholds["mfi_overbought"] = round(float(np.percentile(m_clean, 85)), 1)

    # Bollinger %B
    bb = df.get("bb_pband")
    if bb is not None:
        b_clean = bb.dropna()
        if len(b_clean) > 50:
            thresholds["bb_low"] = round(float(np.percentile(b_clean, 10)), 3)
            thresholds["bb_high"] = round(float(np.percentile(b_clean, 90)), 3)

    # Relative Volume
    rv = df.get("relative_volume")
    if rv is not None:
        r_clean = rv.dropna()
        r_clean = r_clean[r_clean > 0]
        if len(r_clean) > 50:
            thresholds["volume_high"] = round(float(np.percentile(r_clean, 80)), 2)
            thresholds["volume_low"] = round(float(np.percentile(r_clean, 20)), 2)

    # Z-Score: usar desvio propio
    zscore = df.get("zscore_50")
    if zscore is not None:
        z_clean = zscore.dropna()
        if len(z_clean) > 50:
            thresholds["zscore_low"] = round(float(np.percentile(z_clean, 5)), 2)
            thresholds["zscore_high"] = round(float(np.percentile(z_clean, 95)), 2)

    _thresholds_cache[ticker] = thresholds
    return thresholds


def get_adaptive_thresholds(ticker: str) -> dict:
    """Retorna umbrales cacheados para un ticker."""
    return _thresholds_cache.get(ticker, {})


def get_all_cached_thresholds() -> dict:
    """Retorna todos los umbrales cacheados."""
    return _thresholds_cache.copy()
