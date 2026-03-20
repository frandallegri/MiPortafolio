"""
Analysis endpoints: indicators, scoring, scanner, calibration, backtesting.
"""
import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.asset import Asset
from app.models.scoring import ScoringResult
from app.services.indicators import (
    get_price_dataframe, calculate_all_indicators,
    get_latest_indicators, calculate_multiframe_indicators,
)
from app.services.scoring import calculate_score
from app.services.market_regime import (
    load_market_data, detect_regime, calculate_relative_strength,
    get_cached_regime, get_cached_merval_df,
)
from app.services.calibration import (
    calibrate_weights, get_calibrated_weights,
    train_ml_model,
)
from app.services.adaptive_thresholds import (
    compute_adaptive_thresholds, get_adaptive_thresholds,
)
from app.services.backtesting import get_disabled_indicators
from app.services.macro_signals import load_macro_signals, get_cached_macro_signals

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])


@router.get("/indicators/{ticker}")
async def get_indicators(ticker: str, db: AsyncSession = Depends(get_db)):
    """Get all technical indicators for a specific ticker."""
    df = await get_price_dataframe(db, ticker.upper())
    if df is None:
        raise HTTPException(status_code=404, detail=f"No hay datos suficientes para {ticker}")

    df = calculate_all_indicators(df)
    indicators = get_latest_indicators(df)

    # Multi-timeframe
    mf = calculate_multiframe_indicators(df)
    indicators.update(mf)

    return {
        "ticker": ticker.upper(),
        "date": str(df.iloc[-1]["date"]),
        "indicators": indicators,
    }


@router.get("/score/{ticker}")
async def get_score(ticker: str, db: AsyncSession = Depends(get_db)):
    """Calculate the probability score for a specific ticker."""
    df = await get_price_dataframe(db, ticker.upper())
    if df is None:
        raise HTTPException(status_code=404, detail=f"No hay datos suficientes para {ticker}")

    df = calculate_all_indicators(df)
    indicators = get_latest_indicators(df)

    # Multi-timeframe indicators
    mf = calculate_multiframe_indicators(df)
    indicators.update(mf)

    # Relative strength vs market
    merval_df = get_cached_merval_df()
    if merval_df is None:
        merval_df = await load_market_data(db)
    if merval_df is not None:
        rs = calculate_relative_strength(df, merval_df)
        indicators.update(rs)

    # Regime
    regime = get_cached_regime()
    if regime.get("regime") == "sideways" and merval_df is not None:
        regime = detect_regime(merval_df)

    result = calculate_score(
        indicators,
        regime=regime,
        calibrated_weights=get_calibrated_weights(),
    )
    result["ticker"] = ticker.upper()
    result["date"] = str(df.iloc[-1]["date"])
    result["price"] = indicators.get("close")
    result["change_pct"] = indicators.get("change_pct")

    return result


# ── Cache del scanner (evita recalcular en cada request) ──
_scanner_cache: dict = {"data": None, "timestamp": 0}
SCANNER_CACHE_TTL = 300  # 5 minutos


@router.get("/scanner")
async def market_scanner(
    min_score: float = Query(default=0, ge=0, le=100),
    asset_type: str = Query(default=None),
    refresh: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    """
    Scan all active assets with enhanced scoring.
    Results are cached for 5 minutes. Use refresh=true to force recalculation.
    """
    import time as _time

    # Servir desde cache si es valido y no se piden filtros especificos
    if (not refresh and not asset_type and min_score == 0
            and _scanner_cache["data"]
            and _time.time() - _scanner_cache["timestamp"] < SCANNER_CACHE_TTL):
        return _scanner_cache["data"]
    query = select(Asset).where(Asset.is_active == True)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)

    result = await db.execute(query)
    assets = result.scalars().all()

    # ── 1. Cargar datos de mercado y detectar regimen ──
    merval_df = await load_market_data(db)
    regime = detect_regime(merval_df) if merval_df is not None else None

    # ── 2. Obtener pesos calibrados ──
    cal_weights = get_calibrated_weights()

    # ── 3. Cargar senales macro + S&P 500 ──
    macro = await load_macro_signals(db)

    scanner_results = []

    for asset in assets:
        try:
            df = await get_price_dataframe(db, asset.ticker)
            if df is None or len(df) < 30:
                continue

            df = calculate_all_indicators(df)
            indicators = get_latest_indicators(df)

            # Multi-timeframe
            mf = calculate_multiframe_indicators(df)
            indicators.update(mf)

            # Fuerza relativa vs mercado
            if merval_df is not None:
                rs = calculate_relative_strength(df, merval_df)
                indicators.update(rs)

            # Macro + S&P 500
            if macro:
                indicators.update(macro)
            indicators["_asset_type"] = asset.asset_type.value

            # Umbrales adaptativos para este ticker
            ticker_thresholds = get_adaptive_thresholds(asset.ticker)
            if not ticker_thresholds and len(df) >= 100:
                ticker_thresholds = compute_adaptive_thresholds(df, asset.ticker)

            # Score con todas las mejoras
            score_result = calculate_score(
                indicators,
                regime=regime,
                calibrated_weights=cal_weights,
                thresholds=ticker_thresholds,
            )

            if score_result["score"] < min_score:
                continue

            scanner_results.append({
                "ticker": asset.ticker,
                "name": asset.name,
                "asset_type": asset.asset_type.value,
                "price": indicators.get("close"),
                "change_pct": indicators.get("change_pct"),
                "score": score_result["score"],
                "rule_score": score_result.get("rule_score"),
                "signal": score_result["signal"],
                "confidence": score_result["confidence"],
                "bullish": score_result["bullish_count"],
                "bearish": score_result["bearish_count"],
                "rsi": indicators.get("rsi_14"),
                "macd_hist": indicators.get("macd_histogram"),
                "volume_rel": indicators.get("relative_volume"),
                "rs_vs_merval": indicators.get("rs_vs_merval"),
                "ml_score": score_result.get("ml_score"),
                "ensemble_score": score_result.get("ensemble_score"),
            })
        except Exception as e:
            logger.warning(f"Error scoring {asset.ticker}: {e}")
            continue

    # Sort by score descending
    scanner_results.sort(key=lambda x: x["score"], reverse=True)

    response = {
        "date": date.today().isoformat(),
        "total_assets": len(scanner_results),
        "regime": regime or {"regime": "unknown"},
        "results": scanner_results,
    }

    # Guardar en cache (solo si no hay filtros)
    if not asset_type and min_score == 0:
        _scanner_cache["data"] = response
        _scanner_cache["timestamp"] = _time.time()

    return response


@router.get("/regime")
async def get_market_regime(db: AsyncSession = Depends(get_db)):
    """Get current market regime detection."""
    merval_df = await load_market_data(db)
    regime = detect_regime(merval_df) if merval_df is not None else {"regime": "unknown", "description": "Sin datos de mercado"}
    return regime


@router.post("/calibrate")
async def trigger_calibration(db: AsyncSession = Depends(get_db)):
    """Run weight calibration based on historical accuracy."""
    weights = await calibrate_weights(db)
    return {
        "calibrated_indicators": len(weights),
        "weights": weights,
        "message": "Calibracion ejecutada" if weights else "Datos insuficientes para calibrar",
    }


@router.post("/train-ml")
async def trigger_ml_training(db: AsyncSession = Depends(get_db)):
    """Train ML ensemble model on historical scoring data."""
    result = await train_ml_model(db)
    return result


@router.post("/backtest/{ticker}")
async def backtest_single_ticker(ticker: str, db: AsyncSession = Depends(get_db)):
    """Backtest a single ticker (memory-safe for Render free tier)."""
    from app.services.backtesting import _backtest_ticker
    from app.services.market_regime import load_market_data
    import gc

    merval_df = await load_market_data(db)
    if merval_df is not None and len(merval_df) >= 50:
        from app.services.backtesting import _add_regime_columns
        merval_df = _add_regime_columns(merval_df)

    result = await _backtest_ticker(db, ticker.upper(), merval_df)
    gc.collect()

    if result is None:
        return {"ticker": ticker.upper(), "error": "Datos insuficientes"}
    return result


# ──────────────────────────────────────────────
# BACKTESTING ENDPOINTS
# ──────────────────────────────────────────────

@router.post("/backtest")
async def trigger_backtest(background_tasks: BackgroundTasks):
    """Run full backtest + calibrate + train ML pipeline in background."""
    from app.services.backtesting import run_full_pipeline, get_backtest_status
    status = get_backtest_status()
    if status["running"]:
        return {"message": "Backtest already running", "progress": status["progress"]}

    background_tasks.add_task(run_full_pipeline)
    return {"message": "Pipeline started: backtest -> calibrate -> ML -> metrics"}


@router.get("/backtest/status")
async def backtest_status():
    """Check backtest progress."""
    from app.services.backtesting import get_backtest_status
    return get_backtest_status()


@router.get("/accuracy")
async def accuracy_metrics(
    ticker: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Get accuracy metrics from backtest results."""
    from app.services.backtesting import compute_accuracy_metrics
    return await compute_accuracy_metrics(db, ticker)


@router.get("/redundancy")
async def indicator_redundancy(db: AsyncSession = Depends(get_db)):
    """Analyze indicator redundancy/correlation."""
    from app.services.backtesting import analyze_redundancy
    return await analyze_redundancy(db)


@router.post("/full-pipeline")
async def trigger_full_pipeline(background_tasks: BackgroundTasks):
    """Full pipeline: backtest -> calibrate -> ML -> accuracy -> redundancy."""
    from app.services.backtesting import run_full_pipeline, get_backtest_status
    status = get_backtest_status()
    if status["running"]:
        return {"message": "Pipeline already running", "progress": status["progress"]}

    background_tasks.add_task(run_full_pipeline)
    return {"message": "Full pipeline started in background. Check /analysis/backtest/status for progress."}


@router.get("/scoring-history/{ticker}")
async def get_scoring_history(
    ticker: str,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get historical scoring results for a ticker."""
    result = await db.execute(
        select(ScoringResult)
        .where(ScoringResult.ticker == ticker.upper())
        .order_by(ScoringResult.date.desc())
        .limit(days)
    )
    rows = result.scalars().all()

    return [
        {
            "date": r.date.isoformat(),
            "score": r.score,
            "signal": r.signal,
            "confidence": r.confidence,
            "actual_direction": r.actual_direction,
            "ml_score": r.ml_score,
            "ensemble_score": r.ensemble_score,
        }
        for r in reversed(rows)
    ]
