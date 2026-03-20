"""
MiPortafolio — API de análisis cuantitativo de inversiones.
Mercado argentino (BYMA/Merval).
"""
import logging
from contextlib import asynccontextmanager
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import init_db, async_session
from app.routers import auth, market, analysis, portfolio

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()
scheduler = AsyncIOScheduler(timezone="America/Argentina/Buenos_Aires")


# ── Cron Jobs ──────────────────────────────────

async def job_pre_close_analysis():
    """16:30 AR — Run full scoring model, generate buy signals."""
    from app.services.data_ingestion import fetch_live_prices
    from app.services.indicators import get_price_dataframe, calculate_all_indicators, get_latest_indicators
    from app.services.scoring import calculate_score
    from app.models.asset import Asset
    from app.models.scoring import ScoringResult
    from sqlalchemy import select
    from app.services.data_ingestion import db_insert

    logger.info("=== CRON: Pre-close analysis (16:30) ===")

    async with async_session() as db:
        # Update live prices first
        await fetch_live_prices(db)

        # Score all active assets
        result = await db.execute(select(Asset).where(Asset.is_active == True))
        assets = result.scalars().all()

        opportunities = []
        today = date.today()

        for asset in assets:
            try:
                df = await get_price_dataframe(db, asset.ticker, limit=300)
                if df is None or len(df) < 30:
                    continue

                df = calculate_all_indicators(df)
                indicators = get_latest_indicators(df)
                score_result = calculate_score(indicators)

                # Store scoring result
                stmt = db_insert(ScoringResult).values(
                    ticker=asset.ticker,
                    date=today,
                    score=score_result["score"],
                    signal=score_result["signal"],
                    confidence=score_result["confidence"],
                    indicators_detail=score_result["signals"],
                ).on_conflict_do_update(
                    index_elements=["ticker", "date"],
                    set_={
                        "score": score_result["score"],
                        "signal": score_result["signal"],
                        "confidence": score_result["confidence"],
                        "indicators_detail": score_result["signals"],
                    },
                )
                await db.execute(stmt)

                if score_result["score"] >= settings.scoring_threshold:
                    opportunities.append({
                        "ticker": asset.ticker,
                        "score": score_result["score"],
                        "signal": score_result["signal"],
                        "confidence": score_result["confidence"],
                    })
            except Exception as e:
                logger.error(f"Error scoring {asset.ticker}: {e}")

        await db.commit()

        logger.info(f"Scored {len(assets)} assets. {len(opportunities)} opportunities found.")
        for opp in sorted(opportunities, key=lambda x: x["score"], reverse=True)[:10]:
            logger.info(f"  🔥 {opp['ticker']}: score={opp['score']}, confidence={opp['confidence']}%")


async def job_post_close_sync():
    """17:15 AR — Download definitive closing data."""
    from app.services.data_ingestion import run_full_daily_sync

    logger.info("=== CRON: Post-close sync (17:15) ===")
    async with async_session() as db:
        results = await run_full_daily_sync(db)
        logger.info(f"Post-close sync results: {results}")


async def job_morning_report():
    """10:00 AR — Morning report: macro overview, watchlist."""
    from app.services.data_ingestion import fetch_dolar_rates, fetch_riesgo_pais

    logger.info("=== CRON: Morning report (10:00) ===")
    async with async_session() as db:
        rates = await fetch_dolar_rates(db)
        riesgo = await fetch_riesgo_pais(db)
        logger.info(f"Morning macro: dolar_mep={rates.get('dolar_mep')}, riesgo_pais={riesgo}")


# ── App Lifecycle ──────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting MiPortafolio API...")
    await init_db()

    # Schedule cron jobs (Argentina timezone)
    scheduler.add_job(job_pre_close_analysis, CronTrigger(hour=16, minute=30, day_of_week="mon-fri"))
    scheduler.add_job(job_post_close_sync, CronTrigger(hour=17, minute=15, day_of_week="mon-fri"))
    scheduler.add_job(job_morning_report, CronTrigger(hour=10, minute=0, day_of_week="mon-fri"))
    scheduler.start()
    logger.info("Scheduler started with 3 cron jobs (10:00, 16:30, 17:15 AR)")

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("MiPortafolio API stopped.")


# ── FastAPI App ────────────────────────────────

app = FastAPI(
    title="MiPortafolio API",
    description="Plataforma de análisis cuantitativo de inversiones — Mercado argentino",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(market.router)
app.include_router(analysis.router)
app.include_router(portfolio.router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/admin/sync", tags=["admin"])
async def trigger_sync(db=Depends(lambda: async_session())):
    """Manually trigger a full data sync. Protected by auth in production."""
    from app.services.data_ingestion import run_full_daily_sync
    async with async_session() as session:
        results = await run_full_daily_sync(session)
    return {"message": "Sync complete", "results": results}


async def _run_historical_sync(since_date):
    """Background task: sync assets + download all historical bars."""
    from app.services.data_ingestion import sync_assets_from_live, fetch_all_historical
    try:
        async with async_session() as db:
            await sync_assets_from_live(db)
        async with async_session() as db:
            total = await fetch_all_historical(db, since=since_date)
        logger.info(f"Historical sync complete: {total} bars loaded")
    except Exception as e:
        logger.error(f"Historical sync failed: {e}")


@app.post("/admin/sync-historical", tags=["admin"])
async def trigger_historical_sync(background_tasks: BackgroundTasks, since: str = None):
    """Manually trigger historical data download. Runs in background to avoid timeout."""
    from datetime import datetime

    since_date = datetime.strptime(since, "%Y-%m-%d").date() if since else None
    background_tasks.add_task(_run_historical_sync, since_date)
    return {"message": "Historical sync started in background. Check server logs for progress."}


@app.post("/admin/sync-ticker/{ticker}", tags=["admin"])
async def sync_single_ticker(ticker: str):
    """Sync historical data for a single ticker. Fast, no timeout issues."""
    from app.services.data_ingestion import fetch_historical_prices
    from app.models.asset import Asset, AssetType
    from sqlalchemy import select

    ticker = ticker.upper()
    async with async_session() as db:
        result = await db.execute(select(Asset).where(Asset.ticker == ticker))
        asset = result.scalar_one_or_none()
        if not asset:
            return {"ticker": ticker, "bars": 0, "error": "Asset not found"}
        n = await fetch_historical_prices(db, ticker, asset.asset_type)
    return {"ticker": ticker, "bars": n}


@app.post("/admin/run-scoring", tags=["admin"])
async def trigger_scoring():
    """Manually trigger the scoring engine for all assets."""
    await job_pre_close_analysis()
    return {"message": "Scoring complete"}
