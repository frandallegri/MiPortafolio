"""
Análisis histórico completo para un ticker individual.
Endpoint único que devuelve precio, scores, estadísticas,
distribución de retornos, estacionalidad, soportes/resistencias y régimen.
"""
import logging
import math
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.scoring import ScoringResult
from app.services.indicators import get_price_dataframe
from app.services.market_regime import (
    load_market_data,
    get_cached_regime,
    get_cached_merval_df,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/history",
    tags=["history"],
    dependencies=[Depends(get_current_user)],
)

MESES_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


# ──────────────────────────────────────────────
# Funciones auxiliares de cálculo
# ──────────────────────────────────────────────

def _safe_float(val, decimals: int = 4) -> Optional[float]:
    """Convierte a float redondeado, devuelve None si es NaN/Inf."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, decimals)
    except (ValueError, TypeError):
        return None


def _compute_daily_returns(df: pd.DataFrame) -> pd.Series:
    """Calcula retornos diarios porcentuales a partir de la columna close."""
    return df["close"].pct_change().dropna()


def _compute_stats(df: pd.DataFrame, market_df: Optional[pd.DataFrame]) -> dict:
    """Estadísticas completas sobre el DataFrame de precios."""
    if len(df) < 2:
        return {"error": "Datos insuficientes para calcular estadísticas"}

    returns = _compute_daily_returns(df)
    if len(returns) < 2:
        return {"error": "Datos insuficientes para calcular retornos"}

    trading_days = 252

    # ── Retorno y volatilidad anualizados ──
    avg_daily = float(returns.mean())
    std_daily = float(returns.std())
    annualized_return = avg_daily * trading_days * 100
    annualized_volatility = std_daily * math.sqrt(trading_days) * 100

    # ── Sharpe Ratio (risk-free = 0 para Argentina) ──
    sharpe = (annualized_return / annualized_volatility) if annualized_volatility > 0 else 0.0

    # ── Max Drawdown ──
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_dd = float(drawdown.min()) * 100
    max_dd_idx = drawdown.idxmin()
    # El índice de drawdown es posicional; obtener la fecha
    if max_dd_idx is not None and max_dd_idx < len(df):
        max_dd_date = str(df.iloc[max_dd_idx]["date"]) if max_dd_idx < len(df) else None
    else:
        max_dd_date = None

    # ── Win rate ──
    positive_days = int((returns > 0).sum())
    negative_days = int((returns < 0).sum())
    flat_days = int((returns == 0).sum())
    total_days = len(returns)
    win_rate = (positive_days / total_days * 100) if total_days > 0 else 0

    # ── Mejor y peor día ──
    best_day_idx = returns.idxmax()
    worst_day_idx = returns.idxmin()
    best_day_ret = float(returns.iloc[best_day_idx]) * 100 if best_day_idx is not None else 0
    worst_day_ret = float(returns.iloc[worst_day_idx]) * 100 if worst_day_idx is not None else 0

    # Las fechas del mejor/peor día (offset +1 porque returns tiene un shift)
    best_day_date = str(df.iloc[best_day_idx + 1]["date"]) if best_day_idx + 1 < len(df) else None
    worst_day_date = str(df.iloc[worst_day_idx + 1]["date"]) if worst_day_idx + 1 < len(df) else None

    # ── Racha actual ──
    streak = 0
    if len(returns) > 0:
        for r in reversed(returns.values):
            if r > 0 and (streak >= 0):
                streak += 1
            elif r < 0 and (streak <= 0):
                streak -= 1
            else:
                break

    # ── Volatilidad 30d y volumen promedio 30d ──
    returns_30d = returns.tail(30)
    volatility_30d = float(returns_30d.std()) * math.sqrt(trading_days) * 100 if len(returns_30d) >= 5 else None

    vol_30d = df["volume"].tail(30)
    avg_volume_30d = float(vol_30d.mean()) if len(vol_30d) > 0 else 0

    # ── Beta y correlación vs mercado ──
    beta = None
    correlation = None
    if market_df is not None and len(market_df) >= 30:
        beta, correlation = _compute_beta_correlation(df, market_df)

    return {
        "annualized_return": _safe_float(annualized_return, 2),
        "annualized_volatility": _safe_float(annualized_volatility, 2),
        "sharpe_ratio": _safe_float(sharpe, 3),
        "max_drawdown": _safe_float(max_dd, 2),
        "max_drawdown_date": max_dd_date,
        "win_rate": _safe_float(win_rate, 2),
        "avg_daily_return": _safe_float(avg_daily * 100, 4),
        "best_day": _safe_float(best_day_ret, 2),
        "best_day_date": best_day_date,
        "worst_day": _safe_float(worst_day_ret, 2),
        "worst_day_date": worst_day_date,
        "current_streak": streak,
        "beta_vs_market": _safe_float(beta, 3),
        "correlation_with_market": _safe_float(correlation, 3),
        "volatility_30d": _safe_float(volatility_30d, 2),
        "avg_volume_30d": _safe_float(avg_volume_30d, 0),
        "days_of_data": len(df),
    }


def _compute_beta_correlation(
    ticker_df: pd.DataFrame, market_df: pd.DataFrame
) -> tuple[Optional[float], Optional[float]]:
    """Calcula beta y correlación alineando por fecha."""
    try:
        t = ticker_df[["date", "close"]].copy()
        m = market_df[["date", "close"]].copy()
        t["date"] = pd.to_datetime(t["date"])
        m["date"] = pd.to_datetime(m["date"])

        merged = pd.merge(t, m, on="date", suffixes=("_t", "_m"))
        if len(merged) < 30:
            return None, None

        merged = merged.sort_values("date")
        ret_t = merged["close_t"].pct_change().dropna()
        ret_m = merged["close_m"].pct_change().dropna()

        # Alinear índices
        common = ret_t.index.intersection(ret_m.index)
        ret_t = ret_t.loc[common]
        ret_m = ret_m.loc[common]

        if len(ret_t) < 20:
            return None, None

        cov = np.cov(ret_t.values, ret_m.values)
        var_m = cov[1, 1]
        beta = float(cov[0, 1] / var_m) if var_m > 0 else None
        correlation = float(np.corrcoef(ret_t.values, ret_m.values)[0, 1])

        return beta, correlation
    except Exception as e:
        logger.warning(f"Error calculando beta/correlación: {e}")
        return None, None


def _compute_distribution(df: pd.DataFrame) -> dict:
    """Distribución de retornos: histograma, sesgo, curtosis."""
    returns = _compute_daily_returns(df)
    if len(returns) < 10:
        return {"error": "Datos insuficientes para distribución"}

    ret_values = returns.values * 100  # Porcentaje

    # Histograma con 10 buckets
    counts, bin_edges = np.histogram(ret_values, bins=10)
    histogram = []
    for i in range(len(counts)):
        histogram.append({
            "bin_start": _safe_float(bin_edges[i], 2),
            "bin_end": _safe_float(bin_edges[i + 1], 2),
            "count": int(counts[i]),
        })

    # Sesgo y curtosis
    skewness = _safe_float(pd.Series(ret_values).skew(), 4)
    kurtosis = _safe_float(pd.Series(ret_values).kurtosis(), 4)

    total = len(ret_values)
    pct_positive = _safe_float(float(np.sum(ret_values > 0)) / total * 100, 2)
    pct_negative = _safe_float(float(np.sum(ret_values < 0)) / total * 100, 2)
    pct_flat = _safe_float(float(np.sum(ret_values == 0)) / total * 100, 2)

    return {
        "histogram": histogram,
        "skewness": skewness,
        "kurtosis": kurtosis,
        "pct_positive": pct_positive,
        "pct_negative": pct_negative,
        "pct_flat": pct_flat,
    }


def _compute_seasonality(df: pd.DataFrame) -> list[dict]:
    """Retorno promedio y win rate por mes, usando todos los datos disponibles."""
    if len(df) < 30:
        return []

    df_s = df.copy()
    df_s["date"] = pd.to_datetime(df_s["date"])
    df_s["month"] = df_s["date"].dt.month
    df_s["year"] = df_s["date"].dt.year

    # Retorno mensual: agrupar por año-mes, tomar primer y último close
    monthly = df_s.groupby(["year", "month"]).agg(
        first_close=("close", "first"),
        last_close=("close", "last"),
    ).reset_index()
    monthly["return_pct"] = ((monthly["last_close"] / monthly["first_close"]) - 1) * 100

    result = []
    for m in range(1, 13):
        month_data = monthly[monthly["month"] == m]["return_pct"]
        if len(month_data) == 0:
            continue
        avg_ret = float(month_data.mean())
        wr = float((month_data > 0).sum() / len(month_data) * 100)
        result.append({
            "month": m,
            "name": MESES_ES[m],
            "avg_return": _safe_float(avg_ret, 2),
            "win_rate": _safe_float(wr, 1),
            "count": int(len(month_data)),
        })

    return result


def _compute_support_resistance(df: pd.DataFrame, window: int = 20, num_levels: int = 5) -> dict:
    """
    Detecta soportes y resistencias usando mínimos/máximos locales
    con ventana rolling. Agrupa niveles cercanos y ordena por fuerza.
    """
    if len(df) < window * 2:
        return {"supports": [], "resistances": []}

    close = df["close"].values
    dates = df["date"].values
    low = df["low"].values if "low" in df.columns else close
    high = df["high"].values if "high" in df.columns else close

    supports_raw = []
    resistances_raw = []

    # Buscar mínimos locales (soportes)
    for i in range(window, len(low) - window):
        if low[i] == np.min(low[i - window:i + window + 1]):
            supports_raw.append({"level": float(low[i]), "date": str(dates[i])})

    # Buscar máximos locales (resistencias)
    for i in range(window, len(high) - window):
        if high[i] == np.max(high[i - window:i + window + 1]):
            resistances_raw.append({"level": float(high[i]), "date": str(dates[i])})

    # Agrupar niveles cercanos (dentro del 1.5% uno del otro)
    supports = _cluster_levels(supports_raw)
    resistances = _cluster_levels(resistances_raw)

    # Filtrar: soportes por debajo del precio actual, resistencias por encima
    current_price = float(close[-1])
    supports = [s for s in supports if s["level"] < current_price]
    resistances = [r for r in resistances if r["level"] > current_price]

    # Ordenar soportes de mayor a menor (más cercanos primero)
    supports.sort(key=lambda x: x["level"], reverse=True)
    # Ordenar resistencias de menor a mayor (más cercanas primero)
    resistances.sort(key=lambda x: x["level"])

    return {
        "supports": supports[:num_levels],
        "resistances": resistances[:num_levels],
    }


def _cluster_levels(raw_levels: list[dict], tolerance: float = 0.015) -> list[dict]:
    """
    Agrupa niveles de precios cercanos. Devuelve el nivel promedio,
    la cantidad de veces que fue testeado (strength) y última fecha.
    """
    if not raw_levels:
        return []

    # Ordenar por nivel
    sorted_levels = sorted(raw_levels, key=lambda x: x["level"])
    clusters = []
    current_cluster = [sorted_levels[0]]

    for i in range(1, len(sorted_levels)):
        ref = current_cluster[0]["level"]
        if ref > 0 and abs(sorted_levels[i]["level"] - ref) / ref <= tolerance:
            current_cluster.append(sorted_levels[i])
        else:
            clusters.append(current_cluster)
            current_cluster = [sorted_levels[i]]
    clusters.append(current_cluster)

    result = []
    for cluster in clusters:
        levels = [c["level"] for c in cluster]
        dates = [c["date"] for c in cluster]
        result.append({
            "level": _safe_float(float(np.mean(levels)), 2),
            "strength": len(cluster),
            "last_tested": max(dates),
        })

    # Ordenar por fuerza descendente
    result.sort(key=lambda x: x["strength"], reverse=True)
    return result


# ──────────────────────────────────────────────
# Endpoint principal
# ──────────────────────────────────────────────

@router.get("/{ticker}")
async def get_ticker_history(
    ticker: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Análisis histórico completo para un ticker.
    Devuelve precios, scores, estadísticas, distribución,
    estacionalidad, soportes/resistencias y régimen de mercado.
    """
    ticker = ticker.upper()

    # ── 1. Cargar todos los datos de precio ──
    df_full = await get_price_dataframe(db, ticker, limit=10000)
    if df_full is None or len(df_full) < 5:
        raise HTTPException(
            status_code=404,
            detail=f"No hay datos suficientes para {ticker}",
        )

    # ── 2. Price history (últimos 365 días) ──
    cutoff = date.today() - timedelta(days=365)
    df_full["date_dt"] = pd.to_datetime(df_full["date"])
    df_365 = df_full[df_full["date_dt"] >= pd.Timestamp(cutoff)].copy()

    if len(df_365) < 2:
        df_365 = df_full.tail(30).copy()

    price_history = []
    for _, row in df_365.iterrows():
        price_history.append({
            "date": str(row["date"]),
            "open": _safe_float(row["open"], 2),
            "high": _safe_float(row["high"], 2),
            "low": _safe_float(row["low"], 2),
            "close": _safe_float(row["close"], 2),
            "volume": int(row["volume"]) if not pd.isna(row["volume"]) else 0,
        })

    # ── 3. Score history ──
    score_rows = await db.execute(
        select(ScoringResult)
        .where(ScoringResult.ticker == ticker)
        .order_by(ScoringResult.date.asc())
    )
    scores = score_rows.scalars().all()
    score_history = [
        {
            "date": str(s.date),
            "score": _safe_float(s.score, 1),
            "signal": s.signal,
            "actual_direction": s.actual_direction,
        }
        for s in scores
    ]

    # ── 4. Datos del mercado para beta/correlación ──
    market_df = get_cached_merval_df()
    if market_df is None:
        market_df = await load_market_data(db)

    # ── 5. Estadísticas (sobre últimos 365 días) ──
    stats = _compute_stats(df_365, market_df)

    # ── 6. Distribución de retornos (últimos 365 días) ──
    distribution = _compute_distribution(df_365)

    # ── 7. Estacionalidad (todos los datos disponibles) ──
    seasonality = _compute_seasonality(df_full)

    # ── 8. Soportes y resistencias (todos los datos) ──
    support_resistance = _compute_support_resistance(df_full)

    # ── 9. Régimen de mercado ──
    regime = get_cached_regime()

    # Limpiar columna auxiliar
    df_full.drop(columns=["date_dt"], inplace=True, errors="ignore")

    return {
        "ticker": ticker,
        "last_update": str(date.today()),
        "price_history": price_history,
        "score_history": score_history,
        "stats": stats,
        "distribution": distribution,
        "seasonality": seasonality,
        "support_resistance": support_resistance,
        "regime": regime,
    }
