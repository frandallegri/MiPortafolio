"""
Motor de backtesting: evalua el scoring sobre datos historicos,
llena actual_direction, y produce metricas de precision.
Luego alimenta calibracion + ML automaticamente.
"""
import logging
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.asset import Asset
from app.models.scoring import ScoringResult
from app.services.indicators import (
    get_price_dataframe, calculate_all_indicators,
    calculate_multiframe_vectorized, get_indicators_at_row,
    MIN_BARS,
)
from app.services.scoring import calculate_score
from app.services.market_regime import (
    load_market_data, calculate_relative_strength,
)

logger = logging.getLogger(__name__)

# ── Estado global del backtest ──
_backtest_status = {
    "running": False,
    "progress": 0,
    "total_tickers": 0,
    "current_ticker": "",
    "results": None,
}

FLAT_THRESHOLD = 0.5  # +/- 0.5% = flat


def get_backtest_status() -> dict:
    return _backtest_status.copy()


async def run_full_pipeline():
    """
    Pipeline completo con DOBLE PASE:
    1. Backtest inicial -> calibrar -> feature selection
    2. Segundo backtest con pesos calibrados -> re-calibrar -> ML
    3. Metricas finales
    """
    global _backtest_status
    _backtest_status["running"] = True
    _backtest_status["results"] = None

    try:
        from app.services.calibration import calibrate_weights, train_ml_model

        async with async_session() as db:
            # ═══ PASE 1: Backtest con pesos por defecto ═══
            logger.info("=== PASE 1: Backtest inicial ===")
            bt1 = await run_backtest(db)
            logger.info(f"Pase 1: {bt1['total_scores']} scores, accuracy={bt1['overall_accuracy']}%")

            # Calibrar pesos basado en pase 1
            cal1 = await calibrate_weights(db)
            logger.info(f"Calibracion 1: {len(cal1)} indicadores")

            # Feature selection: desactivar indicadores malos (<52% accuracy)
            disabled = await auto_feature_selection(db, threshold=52.0)
            logger.info(f"Feature selection: {len(disabled)} indicadores desactivados")

            # ═══ PASE 2: Re-backtest con pesos calibrados ═══
            logger.info("=== PASE 2: Backtest con pesos calibrados ===")
            bt2 = await run_backtest(db, calibrated_weights=cal1)
            logger.info(f"Pase 2: accuracy={bt2['overall_accuracy']}%")

            # Re-calibrar con datos del pase 2
            cal2 = await calibrate_weights(db)
            logger.info(f"Calibracion 2: {len(cal2)} indicadores")

            # Entrenar ML con datos calibrados
            ml_result = await train_ml_model(db)
            logger.info(f"ML: {ml_result.get('status')}")

            # Metricas finales
            metrics = await compute_accuracy_metrics(db)
            redundancy = await analyze_redundancy(db)

            improvement = bt2["overall_accuracy"] - bt1["overall_accuracy"]
            logger.info(f"Mejora pase 1->2: {improvement:+.1f}%")

            _backtest_status["results"] = {
                "pass_1": {"accuracy": bt1["overall_accuracy"], "scores": bt1["total_scores"]},
                "pass_2": {"accuracy": bt2["overall_accuracy"], "scores": bt2["total_scores"]},
                "improvement": round(improvement, 1),
                "calibration": {"indicators_calibrated": len(cal2), "weights": cal2},
                "disabled_indicators": disabled,
                "ml": ml_result,
                "accuracy": metrics,
                "redundancy": redundancy,
            }

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        _backtest_status["results"] = {"error": str(e)}
    finally:
        _backtest_status["running"] = False
        _backtest_status["progress"] = 100


async def auto_feature_selection(db: AsyncSession, threshold: float = 52.0) -> list[str]:
    """
    Desactiva automaticamente indicadores con accuracy < threshold%.
    Retorna lista de indicadores desactivados.
    """
    metrics = await compute_accuracy_metrics(db)
    ranking = metrics.get("indicator_ranking", [])

    disabled = []
    for ind in ranking:
        if ind["total"] >= 50 and ind["accuracy"] < threshold:
            disabled.append(ind["name"])
            logger.info(f"  DESACTIVADO: {ind['name']} (accuracy={ind['accuracy']}%, n={ind['total']})")

    # Guardar en cache global
    global _disabled_indicators
    _disabled_indicators = set(disabled)

    return disabled


_disabled_indicators: set[str] = set()


def get_disabled_indicators() -> set[str]:
    return _disabled_indicators


async def run_backtest(
    db: AsyncSession,
    tickers: list[str] | None = None,
    calibrated_weights: dict | None = None,
) -> dict:
    """
    Corre el scoring sobre toda la historia de cada ticker.
    Para cada dia i, calcula score usando datos hasta dia i,
    y registra si al dia i+1 el precio subio o bajo.
    """
    global _backtest_status

    # ── Pre-filtro: solo tickers con suficientes barras (evita OOM) ──
    from app.models.price import PriceDaily
    from sqlalchemy import func as sqlfunc

    if tickers:
        result = await db.execute(
            select(Asset).where(Asset.ticker.in_([t.upper() for t in tickers]))
        )
        assets = result.scalars().all()
    else:
        # Solo tickers con >= MIN_BARS barras (evita cargar 1600 sin datos)
        bar_counts = await db.execute(
            select(PriceDaily.ticker, sqlfunc.count(PriceDaily.id).label("cnt"))
            .group_by(PriceDaily.ticker)
            .having(sqlfunc.count(PriceDaily.id) >= MIN_BARS + 10)
        )
        valid_tickers = {row.ticker for row in bar_counts.all()}
        result = await db.execute(
            select(Asset).where(Asset.is_active == True, Asset.ticker.in_(valid_tickers))
        )
        assets = result.scalars().all()
        logger.info(f"Backtest: {len(assets)} tickers con datos suficientes (de {len(valid_tickers)} con barras)")

    _backtest_status["total_tickers"] = len(assets)
    _backtest_status["progress"] = 0

    # Cargar proxy de mercado para regimen + fuerza relativa
    merval_df = await load_market_data(db)
    merval_regime_series = None
    if merval_df is not None and len(merval_df) >= 50:
        merval_df = _add_regime_columns(merval_df)

    total_scores = 0
    total_correct = 0
    ticker_results = []

    for idx, asset in enumerate(assets):
        _backtest_status["current_ticker"] = asset.ticker
        _backtest_status["progress"] = int((idx + 1) / len(assets) * 100)

        try:
            result = await _backtest_ticker(db, asset.ticker, merval_df, calibrated_weights)
            if result:
                total_scores += result["scores"]
                total_correct += result["correct"]
                ticker_results.append(result)
                logger.info(f"  [{idx+1}/{len(assets)}] {asset.ticker}: {result['scores']} scores, {result['accuracy']}%")
        except Exception as e:
            logger.warning(f"Backtest {asset.ticker} failed: {e}")

        # Liberar memoria entre tickers
        import gc
        gc.collect()

    accuracy = (total_correct / total_scores * 100) if total_scores > 0 else 0

    return {
        "total_scores": total_scores,
        "total_correct": total_correct,
        "overall_accuracy": round(accuracy, 1),
        "tickers_processed": len(ticker_results),
        "ticker_results": ticker_results,
    }


async def _backtest_ticker(
    db: AsyncSession,
    ticker: str,
    merval_df: Optional[pd.DataFrame],
    calibrated_weights: dict | None = None,
) -> Optional[dict]:
    """Backtest un ticker individual."""

    # 1. Cargar toda la historia
    df = await get_price_dataframe(db, ticker)
    if df is None or len(df) < MIN_BARS + 10:
        return None

    # 2. Calcular todos los indicadores (vectorizado, una sola vez)
    df = calculate_all_indicators(df)
    df = calculate_multiframe_vectorized(df)

    # 3. Pre-computar fuerza relativa vs mercado
    if merval_df is not None:
        _add_relative_strength_column(df, merval_df)

    # 4. Walk-forward scoring
    start_idx = max(MIN_BARS, 210)
    end_idx = len(df) - 2  # Necesitamos dia i+1 para actual_direction

    # Solo evaluar desde 2024-01-01 (datos recientes, mercado actual)
    from datetime import date as _date
    BACKTEST_SINCE = _date(2024, 1, 1)
    for idx in range(start_idx, end_idx + 1):
        row_dt = df.iloc[idx]["date"]
        if hasattr(row_dt, "date"):
            row_dt = row_dt
        if str(row_dt) >= "2024-01-01":
            start_idx = idx
            break

    if end_idx <= start_idx:
        return None

    scores_to_insert = []
    correct = 0
    total = 0
    prev_score = None  # Para score momentum

    for i in range(start_idx, end_idx + 1):
        indicators = get_indicators_at_row(df, i)
        if not indicators or "close" not in indicators:
            continue

        # Pasar score previo para score momentum
        if prev_score is not None:
            indicators["_prev_score"] = prev_score

        # Regime simple basado en SMA del proxy
        regime = _get_regime_at_row(merval_df, df.iloc[i]["date"]) if merval_df is not None else None

        # Score con pesos calibrados si disponibles
        score_result = calculate_score(
            indicators, regime=regime, calibrated_weights=calibrated_weights
        )
        prev_score = score_result["score"]

        # Actual direction: dia siguiente
        close_today = float(df.iloc[i]["close"])
        close_tomorrow = float(df.iloc[i + 1]["close"])
        if close_today > 0:
            change = (close_tomorrow / close_today - 1) * 100
        else:
            change = 0

        # Direccion real del dia siguiente
        if change > 0:
            actual = "up"
        else:
            actual = "down"

        # Precision DIRECCIONAL: score>50 predice suba, score<50 predice baja
        total += 1
        score_val = score_result["score"]
        if (score_val >= 50 and actual == "up") or (score_val < 50 and actual == "down"):
            correct += 1

        row_date = df.iloc[i]["date"]
        if isinstance(row_date, str):
            row_date = datetime.strptime(row_date, "%Y-%m-%d").date()
        elif hasattr(row_date, "date"):
            row_date = row_date.date() if callable(getattr(row_date, "date")) else row_date

        scores_to_insert.append({
            "ticker": ticker,
            "date": row_date,
            "score": score_result["score"],
            "signal": score_result["signal"],
            "confidence": score_result["confidence"],
            "indicators_detail": score_result["signals"],
            "actual_direction": actual,
        })

    # 5. Bulk upsert en batches
    if scores_to_insert:
        await _bulk_upsert_scores(db, scores_to_insert)

    accuracy = (correct / total * 100) if total > 0 else 0
    logger.info(f"  {ticker}: {total} dias, accuracy={accuracy:.1f}%")

    return {
        "ticker": ticker,
        "scores": total,
        "correct": correct,
        "accuracy": round(accuracy, 1),
        "bars_total": len(df),
    }


async def _bulk_upsert_scores(db: AsyncSession, records: list[dict], batch_size: int = 500):
    """Upsert masivo de scoring_results."""
    from app.config import get_settings
    settings = get_settings()

    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]

        if settings.database_url.startswith("sqlite"):
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert

        stmt = insert(ScoringResult).values(batch)

        if settings.database_url.startswith("sqlite"):
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "date"],
                set_={
                    "score": stmt.excluded.score,
                    "signal": stmt.excluded.signal,
                    "confidence": stmt.excluded.confidence,
                    "indicators_detail": stmt.excluded.indicators_detail,
                    "actual_direction": stmt.excluded.actual_direction,
                }
            )
        else:
            stmt = stmt.on_conflict_do_update(
                constraint="uq_scoring_ticker_date",
                set_={
                    "score": stmt.excluded.score,
                    "signal": stmt.excluded.signal,
                    "confidence": stmt.excluded.confidence,
                    "indicators_detail": stmt.excluded.indicators_detail,
                    "actual_direction": stmt.excluded.actual_direction,
                }
            )

        await db.execute(stmt)

    await db.commit()


# ────────────────────────────────────────
# HELPERS: REGIME & RELATIVE STRENGTH
# ────────────────────────────────────────

def _add_regime_columns(merval_df: pd.DataFrame) -> pd.DataFrame:
    """Pre-computa columnas de regimen en el proxy de mercado."""
    close = merval_df["close"]
    merval_df["_sma50"] = close.rolling(50).mean()
    merval_df["_sma200"] = close.rolling(200).mean()
    merval_df["_ret20"] = close.pct_change(20) * 100
    return merval_df


def _get_regime_at_row(merval_df: pd.DataFrame, target_date) -> Optional[dict]:
    """Obtiene regimen de mercado para una fecha especifica."""
    if merval_df is None or "_sma50" not in merval_df.columns:
        return None

    # Buscar fila mas cercana por fecha
    mask = merval_df["date"] <= target_date
    if not mask.any():
        return None

    row = merval_df.loc[mask].iloc[-1]
    close = float(row["close"])
    sma50 = row.get("_sma50")
    sma200 = row.get("_sma200")
    ret20 = row.get("_ret20", 0)

    if pd.isna(sma50):
        return None

    bull_pts = 0
    total = 2

    if close > float(sma50):
        bull_pts += 1
    if not pd.isna(sma200) and close > float(sma200):
        bull_pts += 1
        total += 1
    if not pd.isna(ret20) and float(ret20) > 0:
        bull_pts += 0.5

    ratio = bull_pts / total

    if ratio >= 0.65:
        return {"regime": "bull", "weight_modifier": 1.15}
    elif ratio <= 0.35:
        return {"regime": "bear", "weight_modifier": 0.80}
    else:
        return {"regime": "sideways", "weight_modifier": 1.0}


def _add_relative_strength_column(ticker_df: pd.DataFrame, merval_df: pd.DataFrame):
    """Pre-computa fuerza relativa como columna del DataFrame del ticker."""
    if len(ticker_df) < 20 or len(merval_df) < 20:
        ticker_df["rs_vs_merval"] = np.nan
        return

    # Merge por fecha
    t = ticker_df[["date", "close"]].copy()
    t["date"] = pd.to_datetime(t["date"])
    m = merval_df[["date", "close"]].copy()
    m["date"] = pd.to_datetime(m["date"])
    m = m.rename(columns={"close": "merval_close"})

    merged = t.merge(m, on="date", how="left")
    merged["merval_close"] = merged["merval_close"].ffill()

    t_ret = merged["close"].pct_change(20)
    m_ret = merged["merval_close"].pct_change(20)
    rs = (t_ret - m_ret) * 100

    ticker_df["rs_vs_merval"] = rs.values


# ────────────────────────────────────────
# METRICAS DE PRECISION
# ────────────────────────────────────────

async def compute_accuracy_metrics(db: AsyncSession, ticker: str = None) -> dict:
    """Calcula metricas de precision del backtest."""
    query = (
        select(ScoringResult)
        .where(ScoringResult.actual_direction.isnot(None))
        .order_by(ScoringResult.date.desc())
        .limit(20000)  # Limitar para performance en Render free tier
    )
    if ticker:
        query = query.where(ScoringResult.ticker == ticker.upper())

    result = await db.execute(query)
    rows = result.scalars().all()

    if not rows:
        return {"error": "No backtest data", "total": 0}

    # DIRECTIONAL accuracy: score>=50 predice suba, score<50 predice baja
    total = len(rows)
    correct = sum(1 for r in rows if _is_directionally_correct(r.score, r.actual_direction))
    overall_acc = correct / total * 100

    # Per-signal precision: cuando dice "compra", cuantas veces subio?
    signal_stats = {}
    for r in rows:
        sig = r.signal
        if sig not in signal_stats:
            signal_stats[sig] = {"total": 0, "correct": 0}
        signal_stats[sig]["total"] += 1
        actual_up = r.actual_direction == "up"
        if (sig == "compra" and actual_up) or (sig == "venta" and not actual_up):
            signal_stats[sig]["correct"] += 1
        elif sig == "neutral":
            # Neutral: correcto si score > 50 y subio, o score < 50 y bajo
            if _is_directionally_correct(r.score, r.actual_direction):
                signal_stats[sig]["correct"] += 1

    for k, v in signal_stats.items():
        v["accuracy"] = round(v["correct"] / v["total"] * 100, 1) if v["total"] > 0 else 0

    # Score bucket accuracy
    buckets = {"0-20": [], "20-40": [], "40-60": [], "60-80": [], "80-100": []}
    for r in rows:
        s = r.score
        if s < 20: b = "0-20"
        elif s < 40: b = "20-40"
        elif s < 60: b = "40-60"
        elif s < 80: b = "60-80"
        else: b = "80-100"
        buckets[b].append(1 if r.actual_direction == "up" else 0)

    bucket_stats = {}
    for b, vals in buckets.items():
        if vals:
            bucket_stats[b] = {
                "count": len(vals),
                "pct_up": round(sum(vals) / len(vals) * 100, 1),
            }

    # Per-indicator accuracy
    indicator_acc = {}
    for r in rows:
        if not r.indicators_detail:
            continue
        for sig in r.indicators_detail:
            name = sig.get("name", "")
            signal_val = sig.get("signal", 0)
            if signal_val == 0:
                continue

            if name not in indicator_acc:
                indicator_acc[name] = {"correct": 0, "total": 0}
            indicator_acc[name]["total"] += 1

            actual_up = r.actual_direction == "up"
            if (signal_val > 0 and actual_up) or (signal_val < 0 and not actual_up):
                indicator_acc[name]["correct"] += 1

    for k, v in indicator_acc.items():
        v["accuracy"] = round(v["correct"] / v["total"] * 100, 1) if v["total"] > 0 else 0

    # Ordenar por accuracy
    indicator_ranking = sorted(
        [{"name": k, **v} for k, v in indicator_acc.items()],
        key=lambda x: x["accuracy"],
        reverse=True,
    )

    return {
        "total_predictions": total,
        "overall_accuracy": round(overall_acc, 1),
        "signal_accuracy": signal_stats,
        "score_buckets": bucket_stats,
        "indicator_ranking": indicator_ranking,
    }


def _is_directionally_correct(score: float, actual: str) -> bool:
    """Score >= 50 predice suba, score < 50 predice baja."""
    actual_up = actual == "up"
    return (score >= 50 and actual_up) or (score < 50 and not actual_up)


# ────────────────────────────────────────
# ANALISIS DE REDUNDANCIA
# ────────────────────────────────────────

async def analyze_redundancy(db: AsyncSession) -> dict:
    """Analiza correlacion entre indicadores para detectar redundancia."""
    result = await db.execute(
        select(ScoringResult)
        .where(ScoringResult.indicators_detail.isnot(None))
        .where(ScoringResult.actual_direction.isnot(None))
        .limit(5000)
    )
    rows = result.scalars().all()

    if len(rows) < 100:
        return {"error": "Insufficient data", "records": len(rows)}

    # Construir matriz de senales
    records = []
    for r in rows:
        if not r.indicators_detail:
            continue
        row_data = {}
        for sig in r.indicators_detail:
            name = sig.get("name", "")
            row_data[name] = sig.get("signal", 0)
        records.append(row_data)

    df = pd.DataFrame(records).fillna(0)
    if df.empty or len(df.columns) < 2:
        return {"error": "Not enough indicators"}

    # Correlacion entre indicadores
    corr = df.corr()

    # Grupos de alta correlacion (>0.6)
    groups = []
    seen = set()
    for col1 in corr.columns:
        if col1 in seen:
            continue
        group = [col1]
        for col2 in corr.columns:
            if col2 != col1 and col2 not in seen and abs(corr.loc[col1, col2]) > 0.6:
                group.append(col2)
        if len(group) > 1:
            groups.append(group)
            seen.update(group)

    return {
        "total_records": len(records),
        "high_correlation_groups": groups,
        "correlation_matrix": {
            col: {
                col2: round(float(corr.loc[col, col2]), 3)
                for col2 in corr.columns
                if col != col2 and abs(corr.loc[col, col2]) > 0.4
            }
            for col in corr.columns
        },
    }
