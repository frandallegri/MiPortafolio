"""
Cálculo de indicadores técnicos para cada activo.
Usa la librería `ta` (Technical Analysis) sobre DataFrames de pandas.
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

# Minimum bars needed to calculate all indicators (200-period SMA needs 200 bars)
MIN_BARS = 210


async def get_price_dataframe(
    db: AsyncSession, ticker: str, limit: int = 500
) -> Optional[pd.DataFrame]:
    """Load price history from DB into a pandas DataFrame."""
    result = await db.execute(
        select(PriceDaily)
        .where(PriceDaily.ticker == ticker)
        .order_by(PriceDaily.date.desc())
        .limit(limit)
    )
    rows = result.scalars().all()

    if len(rows) < MIN_BARS:
        logger.warning(f"{ticker}: only {len(rows)} bars, need {MIN_BARS}")
        if len(rows) < 30:
            return None

    data = [{
        "date": r.date,
        "open": r.open or r.close,
        "high": r.high or r.close,
        "low": r.low or r.close,
        "close": r.close,
        "volume": r.volume or 0,
    } for r in rows]

    df = pd.DataFrame(data)
    df = df.sort_values("date").reset_index(drop=True)
    df["open"] = pd.to_numeric(df["open"], errors="coerce")
    df["high"] = pd.to_numeric(df["high"], errors="coerce")
    df["low"] = pd.to_numeric(df["low"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)

    return df


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate ALL technical indicators on a price DataFrame.
    Returns the same DataFrame with indicator columns appended.
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # ── RSI (14) ──
    df["rsi_14"] = ta.momentum.RSIIndicator(close, window=14).rsi()

    # ── MACD (12, 26, 9) ──
    macd = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_histogram"] = macd.macd_diff()

    # ── Bollinger Bands (20, 2) ──
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_middle"] = bb.bollinger_mavg()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_pband"] = bb.bollinger_pband()  # %B (position within bands)
    df["bb_wband"] = bb.bollinger_wband()  # bandwidth

    # ── SMA (20, 50, 200) ──
    df["sma_20"] = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    df["sma_50"] = ta.trend.SMAIndicator(close, window=50).sma_indicator()
    df["sma_200"] = ta.trend.SMAIndicator(close, window=200).sma_indicator()

    # ── EMA (9, 21, 50) ──
    df["ema_9"] = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    df["ema_21"] = ta.trend.EMAIndicator(close, window=21).ema_indicator()
    df["ema_50"] = ta.trend.EMAIndicator(close, window=50).ema_indicator()

    # ── ATR (14) — Average True Range ──
    df["atr_14"] = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()

    # ── Volumen relativo (vs promedio 20 días) ──
    vol_sma_20 = volume.rolling(window=20).mean()
    df["relative_volume"] = np.where(vol_sma_20 > 0, volume / vol_sma_20, 0)

    # ── Estocástico (%K, %D) ──
    stoch = ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    # ── ADX (14) — Average Directional Index ──
    adx = ta.trend.ADXIndicator(high, low, close, window=14)
    df["adx"] = adx.adx()
    df["adx_pos"] = adx.adx_pos()  # +DI
    df["adx_neg"] = adx.adx_neg()  # -DI

    # ── OBV — On Balance Volume ──
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()

    # ── Williams %R (14) ──
    df["williams_r"] = ta.momentum.WilliamsRIndicator(high, low, close, lbp=14).williams_r()

    # ── CCI (20) — Commodity Channel Index ──
    df["cci_20"] = ta.trend.CCIIndicator(high, low, close, window=20).cci()

    # ── Ichimoku Cloud ──
    ichi = ta.trend.IchimokuIndicator(high, low, window1=9, window2=26, window3=52)
    df["ichimoku_a"] = ichi.ichimoku_a()
    df["ichimoku_b"] = ichi.ichimoku_b()
    df["ichimoku_base"] = ichi.ichimoku_base_line()
    df["ichimoku_conv"] = ichi.ichimoku_conversion_line()

    # ── VWAP approximation (daily reset) ──
    typical_price = (high + low + close) / 3
    df["vwap"] = (typical_price * volume).cumsum() / volume.cumsum()

    # ── Rate of Change (12) ──
    df["roc_12"] = ta.momentum.ROCIndicator(close, window=12).roc()

    # ── MFI — Money Flow Index (14) ──
    df["mfi_14"] = ta.volume.MFIIndicator(high, low, close, volume, window=14).money_flow_index()

    return df


def get_latest_indicators(df: pd.DataFrame) -> dict:
    """Extract the latest indicator values from a calculated DataFrame."""
    if df.empty:
        return {}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last

    indicators = {}
    indicator_cols = [
        "rsi_14", "macd", "macd_signal", "macd_histogram",
        "bb_upper", "bb_middle", "bb_lower", "bb_pband", "bb_wband",
        "sma_20", "sma_50", "sma_200",
        "ema_9", "ema_21", "ema_50",
        "atr_14", "relative_volume",
        "stoch_k", "stoch_d",
        "adx", "adx_pos", "adx_neg",
        "obv", "williams_r", "cci_20",
        "ichimoku_a", "ichimoku_b", "ichimoku_base", "ichimoku_conv",
        "vwap", "roc_12", "mfi_14",
    ]

    for col in indicator_cols:
        val = last.get(col)
        if val is not None and not pd.isna(val):
            indicators[col] = round(float(val), 4)

    # Add price context
    indicators["close"] = float(last["close"])
    indicators["prev_close"] = float(prev["close"])
    indicators["change_pct"] = round((float(last["close"]) / float(prev["close"]) - 1) * 100, 2) if float(prev["close"]) > 0 else 0

    return indicators
