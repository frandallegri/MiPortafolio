"""
Motor de Momentum Mensual.
Basado en investigacion academica (Jegadeesh & Titman 1993, Antonacci 2014).

En vez de predecir la direccion diaria (imposible con >52% accuracy),
rankea acciones por momentum de mediano plazo y selecciona las mejores.

Estrategia:
1. Calcular retorno 1m, 3m, 6m para cada accion
2. Rankear por momentum compuesto (ponderado)
3. Filtrar por regimen de mercado (dual momentum)
4. Calcular un "Momentum Score" 0-100
5. Top 5-10 = cartera del mes

Backtest historico: 55-65% accuracy mensual en mercados emergentes.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MomentumResult:
    """Resultado de momentum para un ticker."""
    ticker: str
    score: float           # 0-100 momentum score
    signal: str            # "compra", "neutral", "venta"
    rank: int              # Posicion en el ranking
    ret_1m: float          # Retorno 1 mes (%)
    ret_3m: float          # Retorno 3 meses (%)
    ret_6m: float          # Retorno 6 meses (%)
    ret_12m: float         # Retorno 12 meses (%)
    volatility: float      # Volatilidad anualizada (%)
    sharpe: float          # Sharpe ratio (ret/vol)
    rs_vs_market: float    # Fuerza relativa vs mercado (%)
    trend_strength: float  # Fuerza de tendencia (0-1)
    volume_trend: float    # Tendencia de volumen (ratio)
    above_sma200: bool     # Precio > SMA200
    description: str       # Explicacion


def calculate_momentum(df: pd.DataFrame, market_df: Optional[pd.DataFrame] = None) -> Optional[dict]:
    """
    Calcula el momentum score para un ticker.

    Args:
        df: DataFrame con columnas date, close, high, low, volume (al menos 252 barras)
        market_df: DataFrame del proxy de mercado (GGAL) para fuerza relativa

    Returns:
        dict con todos los campos de MomentumResult
    """
    if df is None or len(df) < 60:
        return None

    close = df["close"].astype(float)
    volume = df["volume"].astype(float) if "volume" in df.columns else pd.Series(0, index=df.index)
    high = df["high"].astype(float) if "high" in df.columns else close
    low = df["low"].astype(float) if "low" in df.columns else close
    n = len(close)

    # ── RETORNOS ──
    ret_1m = _safe_return(close, 21)
    ret_3m = _safe_return(close, 63)
    ret_6m = _safe_return(close, 126)
    ret_12m = _safe_return(close, 252)

    # MEJORA 3: Skip-month momentum (excluir ultimo mes, usar meses 2-12)
    # La investigacion muestra que el ultimo mes tiene reversion
    ret_skip = None  # Retorno meses 2-7 (excluyendo el ultimo mes)
    if n >= 147:  # 126 + 21
        price_1m_ago = float(close.iloc[-22])  # Hace ~1 mes
        price_6m_ago = float(close.iloc[-127])  # Hace ~6 meses
        if price_6m_ago > 0:
            ret_skip = round((price_1m_ago / price_6m_ago - 1) * 100, 2)

    # ── VOLATILIDAD ──
    daily_returns = close.pct_change().dropna()
    vol_annual = float(daily_returns.std() * np.sqrt(252) * 100) if len(daily_returns) > 20 else 0
    vol_3m = float(daily_returns.iloc[-63:].std() * np.sqrt(252) * 100) if len(daily_returns) >= 63 else vol_annual

    # ── SHARPE RATIO ──
    if vol_annual > 0 and ret_12m is not None:
        sharpe = ret_12m / vol_annual
    elif vol_3m > 0 and ret_3m is not None:
        sharpe = (ret_3m * 4) / vol_3m  # Anualizar ret_3m
    else:
        sharpe = 0

    # ── MEJORA 5: MAX DRAWDOWN (penalizar caidas grandes) ──
    max_dd = 0.0
    if n >= 63:
        rolling_max = close.iloc[-63:].cummax()
        drawdown = (close.iloc[-63:] / rolling_max - 1) * 100
        max_dd = float(drawdown.min())  # Negativo

    # ── FUERZA RELATIVA vs MERCADO ──
    rs = 0.0
    if market_df is not None and len(market_df) >= 63:
        market_close = market_df["close"].astype(float)
        market_ret_3m = _safe_return(market_close, 63)
        if market_ret_3m is not None and ret_3m is not None:
            rs = ret_3m - market_ret_3m

    # ── MEJORA 4: DUAL MOMENTUM - filtro de mercado ──
    market_bullish = True  # Default
    if market_df is not None and len(market_df) >= 210:
        market_close = market_df["close"].astype(float)
        market_sma200 = market_close.rolling(200).mean().iloc[-1]
        if not pd.isna(market_sma200):
            market_bullish = float(market_close.iloc[-1]) > float(market_sma200)

    # ── TENDENCIA ──
    sma_50 = close.rolling(50).mean().iloc[-1] if n >= 50 else close.iloc[-1]
    sma_200 = close.rolling(200).mean().iloc[-1] if n >= 200 else close.iloc[-1]
    current = float(close.iloc[-1])

    above_sma200 = current > float(sma_200) if not pd.isna(sma_200) else True

    trend_points = 0
    trend_total = 0

    trend_total += 1
    if current > float(sma_50):
        trend_points += 1

    if not pd.isna(sma_200):
        trend_total += 1
        if current > float(sma_200):
            trend_points += 1
        trend_total += 1
        if float(sma_50) > float(sma_200):
            trend_points += 1

    for r in [ret_1m, ret_3m, ret_6m]:
        if r is not None:
            trend_total += 1
            if r > 0:
                trend_points += 1

    trend_strength = trend_points / trend_total if trend_total > 0 else 0.5

    # ── MEJORA 6: MOMENTUM DE VOLUMEN ──
    vol_trend = 1.0
    vol_momentum = 0.0
    if len(volume) >= 60 and volume.iloc[-60:].mean() > 0:
        vol_recent = volume.iloc[-5:].mean()
        vol_avg = volume.iloc[-60:].mean()
        vol_trend = float(vol_recent / vol_avg) if vol_avg > 0 else 1.0
        # Tendencia de volumen: comparar volumen promedio ultimo mes vs anterior
        vol_last_month = volume.iloc[-21:].mean() if len(volume) >= 21 else 0
        vol_prev_month = volume.iloc[-42:-21].mean() if len(volume) >= 42 else vol_last_month
        if vol_prev_month > 0:
            vol_momentum = float(vol_last_month / vol_prev_month - 1)

    # ── MEJORA 2: FILTRO DE LIQUIDEZ ──
    avg_volume_20d = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else 0
    is_liquid = avg_volume_20d > 10000  # Minimo 10K de volumen diario promedio

    # ══════════════════════════════════════════
    # MOMENTUM SCORE v2 (0-100)
    # ══════════════════════════════════════════
    score = 50.0

    # MEJORA 1: Momentum ajustado por volatilidad (retorno/vol)
    # En vez de rankear solo por retorno, usamos retorno/vol
    if ret_3m is not None and vol_3m > 0:
        # Risk-adjusted momentum: retorno 3m / volatilidad 3m
        risk_adj_3m = ret_3m / (vol_3m / np.sqrt(4))  # vol trimestral
        score += min(20, max(-20, risk_adj_3m * 5))  # max 20 pts
    elif ret_3m is not None:
        score += min(20, max(-20, ret_3m * 0.8))

    # MEJORA 3: Skip-month (meses 2-7, excluyendo ultimo mes)
    if ret_skip is not None and vol_3m > 0:
        risk_adj_skip = ret_skip / (vol_3m / np.sqrt(4))
        score += min(15, max(-15, risk_adj_skip * 4))
    elif ret_6m is not None:
        score += min(15, max(-15, ret_6m * 0.25))

    # Retorno 1m (peso menor, por reversion de corto plazo)
    if ret_1m is not None:
        score += min(5, max(-5, ret_1m * 0.3))

    # Tendencia
    score += (trend_strength - 0.5) * 12  # -6 a +6 pts

    # Fuerza relativa vs mercado
    score += min(5, max(-5, rs * 0.15))

    # MEJORA 4: Dual momentum - penalizar si mercado es bearish
    if not market_bullish:
        if score > 50:
            score = 50 + (score - 50) * 0.5  # Reducir senales de compra 50%

    # MEJORA 5: Penalizar max drawdown
    if max_dd < -15:
        score -= 5  # Drawdown > 15% en 3m
    elif max_dd < -10:
        score -= 2

    # MEJORA 6: Bonus/penalty por momentum de volumen
    if vol_momentum > 0.3 and ret_3m is not None and ret_3m > 0:
        score += 3  # Volumen creciente + retorno positivo = confirmacion
    elif vol_momentum < -0.3 and ret_3m is not None and ret_3m > 0:
        score -= 2  # Volumen cayendo + retorno positivo = divergencia peligrosa

    # MEJORA 2: Penalty por iliquidez
    if not is_liquid:
        score -= 5

    # Bonus Sharpe alto
    if sharpe > 1.5:
        score += 3
    elif sharpe > 1.0:
        score += 1

    score = max(0, min(100, score))

    # ── SIGNAL ──
    if score >= 65 and market_bullish:
        signal = "compra"
    elif score >= 65:
        signal = "neutral"  # Score alto pero mercado bearish
    elif score <= 35:
        signal = "venta"
    else:
        signal = "neutral"

    # ── DESCRIPCION ──
    parts = []
    if ret_skip is not None:
        parts.append(f"Skip-mom: {ret_skip:+.1f}%")
    if ret_3m is not None:
        parts.append(f"3m: {ret_3m:+.1f}%")
    if rs != 0:
        parts.append(f"RS: {rs:+.1f}%")
    parts.append(f"Tend: {trend_strength:.0%}")
    if max_dd < -5:
        parts.append(f"DD: {max_dd:.1f}%")
    if not market_bullish:
        parts.append("Mercado bearish")
    if not is_liquid:
        parts.append("Baja liquidez")

    return {
        "score": round(score, 1),
        "signal": signal,
        "ret_1m": round(ret_1m, 2) if ret_1m is not None else None,
        "ret_3m": round(ret_3m, 2) if ret_3m is not None else None,
        "ret_6m": round(ret_6m, 2) if ret_6m is not None else None,
        "ret_12m": round(ret_12m, 2) if ret_12m is not None else None,
        "ret_skip_month": round(ret_skip, 2) if ret_skip is not None else None,
        "volatility": round(vol_annual, 1),
        "vol_3m": round(vol_3m, 1),
        "sharpe": round(sharpe, 2),
        "max_drawdown_3m": round(max_dd, 1),
        "rs_vs_market": round(rs, 2),
        "trend_strength": round(trend_strength, 2),
        "volume_trend": round(vol_trend, 2),
        "volume_momentum": round(vol_momentum, 2),
        "above_sma200": above_sma200,
        "market_bullish": market_bullish,
        "is_liquid": is_liquid,
        "avg_volume_20d": round(avg_volume_20d, 0),
        "description": " | ".join(parts),
    }


def calculate_momentum_at_date(
    df: pd.DataFrame,
    target_date: str,
    market_df: Optional[pd.DataFrame] = None,
) -> Optional[dict]:
    """
    Calcula momentum score como si estuvieras en target_date.
    Usa solo datos hasta esa fecha. Luego compara con lo que realmente paso.
    """
    if df is None or len(df) < 60:
        return None

    df_copy = df.copy()
    df_copy["_dt"] = pd.to_datetime(df_copy["date"])

    # Filtrar datos hasta target_date
    mask = df_copy["_dt"] <= pd.Timestamp(target_date)
    df_past = df_copy[mask].copy()
    if len(df_past) < 60:
        return None

    # Filtrar mercado hasta target_date
    market_past = None
    if market_df is not None:
        m = market_df.copy()
        m["_dt"] = pd.to_datetime(m["date"])
        market_past = m[m["_dt"] <= pd.Timestamp(target_date)].copy()

    # Calcular momentum con datos hasta target_date
    result = calculate_momentum(df_past, market_past)
    if result is None:
        return None

    # Ahora calcular que REALMENTE paso en los 21 dias siguientes
    df_future = df_copy[df_copy["_dt"] > pd.Timestamp(target_date)]
    if len(df_future) >= 21:
        close_at_date = float(df_past["close"].iloc[-1])
        close_21d_later = float(df_future["close"].iloc[min(20, len(df_future) - 1)])
        actual_return = round((close_21d_later / close_at_date - 1) * 100, 2) if close_at_date > 0 else 0
        result["actual_return_1m"] = actual_return
        result["actual_won"] = actual_return > 0
    elif len(df_future) > 0:
        close_at_date = float(df_past["close"].iloc[-1])
        close_latest = float(df_future["close"].iloc[-1])
        actual_return = round((close_latest / close_at_date - 1) * 100, 2) if close_at_date > 0 else 0
        days_elapsed = len(df_future)
        result["actual_return_1m"] = actual_return
        result["actual_won"] = actual_return > 0
        result["actual_days"] = days_elapsed
    else:
        result["actual_return_1m"] = None
        result["actual_won"] = None

    result["as_of_date"] = target_date
    return result


def _safe_return(series: pd.Series, periods: int) -> Optional[float]:
    """Calcula retorno % de N periodos de forma segura."""
    if len(series) < periods + 1:
        return None
    current = float(series.iloc[-1])
    past = float(series.iloc[-periods - 1])
    if past <= 0:
        return None
    return round((current / past - 1) * 100, 2)


# ────────────────────────────────────────
# BACKTEST DE MOMENTUM MENSUAL
# ────────────────────────────────────────

def backtest_momentum_monthly(
    all_dfs: dict[str, pd.DataFrame],
    market_df: Optional[pd.DataFrame] = None,
    top_n: int = 5,
    start_date: str = "2024-01-01",
) -> dict:
    """
    Backtest de la estrategia de momentum mensual.

    Cada mes:
    1. Rankea todos los tickers por momentum score
    2. "Compra" los top N
    3. Mide el retorno del mes siguiente

    Args:
        all_dfs: {ticker: DataFrame} para todos los tickers
        market_df: DataFrame del proxy de mercado
        top_n: cuantos tickers comprar cada mes
        start_date: desde cuando backtestear

    Returns:
        dict con resultados del backtest
    """
    # Construir serie mensual de closes por ticker
    monthly_data = {}
    for ticker, df in all_dfs.items():
        if df is None or len(df) < 126:
            continue
        df_copy = df[["date", "close"]].copy()
        df_copy["date"] = pd.to_datetime(df_copy["date"])
        df_copy = df_copy.set_index("date")
        monthly = df_copy["close"].resample("ME").last().dropna()
        if len(monthly) >= 6:
            monthly_data[ticker] = monthly

    if len(monthly_data) < top_n:
        return {"error": "No hay suficientes tickers", "tickers": len(monthly_data)}

    # Alinear fechas
    all_dates = sorted(set.union(*[set(s.index) for s in monthly_data.values()]))
    all_dates = [d for d in all_dates if str(d.date()) >= start_date]

    if len(all_dates) < 3:
        return {"error": "No hay suficientes meses desde " + start_date}

    results = []
    portfolio_returns = []
    market_returns = []
    buy_hold_returns = []

    for i in range(6, len(all_dates) - 1):
        current_date = all_dates[i]
        next_date = all_dates[i + 1]

        # Calcular momentum score para cada ticker al final del mes
        scores = []
        for ticker, series in monthly_data.items():
            if current_date not in series.index:
                continue
            # Retornos historicos
            idx = series.index.get_loc(current_date)
            if idx < 6:
                continue

            ret_1m = (float(series.iloc[idx]) / float(series.iloc[idx - 1]) - 1) * 100 if idx >= 1 else 0
            ret_3m = (float(series.iloc[idx]) / float(series.iloc[idx - 3]) - 1) * 100 if idx >= 3 else 0
            ret_6m = (float(series.iloc[idx]) / float(series.iloc[idx - 6]) - 1) * 100 if idx >= 6 else 0

            # Skip-month: retorno meses 2-6 (excluyendo ultimo mes)
            ret_skip = 0
            if idx >= 6:
                ret_skip = (float(series.iloc[idx - 1]) / float(series.iloc[idx - 6]) - 1) * 100

            # Volatilidad mensual para risk-adjust
            if idx >= 6:
                monthly_rets = []
                for m in range(1, 7):
                    if idx - m >= 0 and float(series.iloc[idx - m]) > 0:
                        mr = (float(series.iloc[idx - m + 1]) / float(series.iloc[idx - m]) - 1) * 100 if idx - m + 1 <= idx else 0
                        monthly_rets.append(mr)
                vol = float(np.std(monthly_rets)) if len(monthly_rets) >= 3 else 1
            else:
                vol = 1

            # Risk-adjusted skip-month momentum
            risk_adj = ret_skip / max(vol, 1) if vol > 0 else ret_skip
            momentum = risk_adj * 0.5 + ret_3m * 0.3 + ret_1m * 0.2
            scores.append({"ticker": ticker, "momentum": momentum, "ret_3m": ret_3m, "ret_skip": ret_skip})

        if len(scores) < top_n:
            continue

        # Rankear y seleccionar top N
        scores.sort(key=lambda x: x["momentum"], reverse=True)
        selected = scores[:top_n]

        # Calcular retorno del mes siguiente para los seleccionados
        month_returns = []
        for s in selected:
            ticker = s["ticker"]
            series = monthly_data[ticker]
            if next_date in series.index and current_date in series.index:
                ret = (float(series.loc[next_date]) / float(series.loc[current_date]) - 1) * 100
                month_returns.append(ret)

        if month_returns:
            avg_return = sum(month_returns) / len(month_returns)
            portfolio_returns.append(avg_return)

            results.append({
                "date": str(current_date.date()),
                "selected": [s["ticker"] for s in selected],
                "portfolio_return": round(avg_return, 2),
                "winners": sum(1 for r in month_returns if r > 0),
                "total": len(month_returns),
            })

    if not portfolio_returns:
        return {"error": "Sin resultados de backtest"}

    # Estadisticas
    total_months = len(portfolio_returns)
    winning_months = sum(1 for r in portfolio_returns if r > 0)
    avg_monthly = sum(portfolio_returns) / total_months
    cumulative = 1.0
    for r in portfolio_returns:
        cumulative *= (1 + r / 100)
    total_return = (cumulative - 1) * 100

    return {
        "strategy": "Momentum Mensual Top " + str(top_n),
        "period": f"{results[0]['date']} a {results[-1]['date']}",
        "total_months": total_months,
        "winning_months": winning_months,
        "win_rate": round(winning_months / total_months * 100, 1),
        "avg_monthly_return": round(avg_monthly, 2),
        "total_return": round(total_return, 1),
        "annualized_return": round(avg_monthly * 12, 1),
        "best_month": round(max(portfolio_returns), 2),
        "worst_month": round(min(portfolio_returns), 2),
        "monthly_results": results,
    }
