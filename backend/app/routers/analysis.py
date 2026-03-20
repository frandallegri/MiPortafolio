"""
Analysis endpoints: indicators, scoring, scanner.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.asset import Asset
from app.models.scoring import ScoringResult
from app.services.indicators import get_price_dataframe, calculate_all_indicators, get_latest_indicators
from app.services.scoring import calculate_score

router = APIRouter(prefix="/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])


@router.get("/indicators/{ticker}")
async def get_indicators(ticker: str, db: AsyncSession = Depends(get_db)):
    """Get all technical indicators for a specific ticker."""
    df = await get_price_dataframe(db, ticker.upper())
    if df is None:
        raise HTTPException(status_code=404, detail=f"No hay datos suficientes para {ticker}")

    df = calculate_all_indicators(df)
    indicators = get_latest_indicators(df)

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
    result = calculate_score(indicators)
    result["ticker"] = ticker.upper()
    result["date"] = str(df.iloc[-1]["date"])
    result["price"] = indicators.get("close")
    result["change_pct"] = indicators.get("change_pct")

    return result


@router.get("/scanner")
async def market_scanner(
    min_score: float = Query(default=0, ge=0, le=100),
    asset_type: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Scan all active assets, calculate scores, and return sorted by score desc.
    This is the CORE endpoint — the opportunity scanner.
    """
    query = select(Asset).where(Asset.is_active == True)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)

    result = await db.execute(query)
    assets = result.scalars().all()

    scanner_results = []

    for asset in assets:
        try:
            df = await get_price_dataframe(db, asset.ticker, limit=300)
            if df is None or len(df) < 30:
                continue

            df = calculate_all_indicators(df)
            indicators = get_latest_indicators(df)
            score_result = calculate_score(indicators)

            if score_result["score"] < min_score:
                continue

            scanner_results.append({
                "ticker": asset.ticker,
                "name": asset.name,
                "asset_type": asset.asset_type.value,
                "price": indicators.get("close"),
                "change_pct": indicators.get("change_pct"),
                "score": score_result["score"],
                "signal": score_result["signal"],
                "confidence": score_result["confidence"],
                "bullish": score_result["bullish_count"],
                "bearish": score_result["bearish_count"],
                "rsi": indicators.get("rsi_14"),
                "macd_hist": indicators.get("macd_histogram"),
                "volume_rel": indicators.get("relative_volume"),
            })
        except Exception:
            continue

    # Sort by score descending
    scanner_results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "date": date.today().isoformat(),
        "total_assets": len(scanner_results),
        "results": scanner_results,
    }


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
        }
        for r in reversed(rows)
    ]
