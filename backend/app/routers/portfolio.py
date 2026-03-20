"""
Portfolio management: CRUD de posiciones, P&L.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.portfolio import Position
from app.models.price import PriceDaily

router = APIRouter(prefix="/portfolio", tags=["portfolio"], dependencies=[Depends(get_current_user)])


class PositionCreate(BaseModel):
    ticker: str
    quantity: float
    entry_price: float
    entry_date: str  # yyyy-mm-dd
    commission: float = 0.0
    notes: Optional[str] = None


class PositionClose(BaseModel):
    exit_price: float
    exit_date: str


@router.get("/positions")
async def list_positions(
    open_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all portfolio positions with current P&L."""
    query = select(Position)
    if open_only:
        query = query.where(Position.is_open == 1)
    query = query.order_by(Position.entry_date.desc())

    result = await db.execute(query)
    positions = result.scalars().all()

    # Get latest prices for open positions
    response = []
    for pos in positions:
        item = {
            "id": pos.id,
            "ticker": pos.ticker,
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "entry_date": pos.entry_date.isoformat(),
            "commission": pos.commission,
            "notes": pos.notes,
            "is_open": bool(pos.is_open),
            "invested": pos.quantity * pos.entry_price + pos.commission,
        }

        if pos.is_open:
            # Get latest price
            price_result = await db.execute(
                select(PriceDaily.close)
                .where(PriceDaily.ticker == pos.ticker)
                .order_by(PriceDaily.date.desc())
                .limit(1)
            )
            latest_price = price_result.scalar()

            if latest_price:
                current_value = pos.quantity * latest_price
                invested = pos.quantity * pos.entry_price + pos.commission
                pnl = current_value - invested
                pnl_pct = (pnl / invested * 100) if invested > 0 else 0

                item["current_price"] = latest_price
                item["current_value"] = round(current_value, 2)
                item["pnl"] = round(pnl, 2)
                item["pnl_pct"] = round(pnl_pct, 2)
        else:
            if pos.exit_price:
                exit_value = pos.quantity * pos.exit_price
                invested = pos.quantity * pos.entry_price + pos.commission
                pnl = exit_value - invested
                item["exit_price"] = pos.exit_price
                item["exit_date"] = pos.exit_date.isoformat() if pos.exit_date else None
                item["pnl"] = round(pnl, 2)
                item["pnl_pct"] = round((pnl / invested * 100) if invested > 0 else 0, 2)

        response.append(item)

    return response


@router.post("/positions")
async def create_position(pos: PositionCreate, db: AsyncSession = Depends(get_db)):
    """Add a new position to the portfolio."""
    new_pos = Position(
        ticker=pos.ticker.upper(),
        quantity=pos.quantity,
        entry_price=pos.entry_price,
        entry_date=date.fromisoformat(pos.entry_date),
        commission=pos.commission,
        notes=pos.notes,
    )
    db.add(new_pos)
    await db.commit()
    await db.refresh(new_pos)
    return {"id": new_pos.id, "ticker": new_pos.ticker, "message": "Posición creada"}


@router.put("/positions/{position_id}/close")
async def close_position(
    position_id: int,
    data: PositionClose,
    db: AsyncSession = Depends(get_db),
):
    """Close an open position."""
    result = await db.execute(select(Position).where(Position.id == position_id))
    pos = result.scalar_one_or_none()

    if not pos:
        raise HTTPException(status_code=404, detail="Posición no encontrada")
    if not pos.is_open:
        raise HTTPException(status_code=400, detail="La posición ya está cerrada")

    pos.exit_price = data.exit_price
    pos.exit_date = date.fromisoformat(data.exit_date)
    pos.is_open = 0
    await db.commit()

    pnl = (data.exit_price - pos.entry_price) * pos.quantity - pos.commission
    return {"message": "Posición cerrada", "pnl": round(pnl, 2)}


@router.delete("/positions/{position_id}")
async def delete_position(position_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a position."""
    result = await db.execute(select(Position).where(Position.id == position_id))
    pos = result.scalar_one_or_none()
    if not pos:
        raise HTTPException(status_code=404, detail="Posición no encontrada")

    await db.delete(pos)
    await db.commit()
    return {"message": "Posición eliminada"}


@router.get("/summary")
async def portfolio_summary(db: AsyncSession = Depends(get_db)):
    """Get portfolio summary: total invested, current value, total P&L."""
    result = await db.execute(select(Position).where(Position.is_open == 1))
    positions = result.scalars().all()

    total_invested = 0.0
    total_current = 0.0
    by_type = {}

    for pos in positions:
        invested = pos.quantity * pos.entry_price + pos.commission
        total_invested += invested

        price_result = await db.execute(
            select(PriceDaily.close)
            .where(PriceDaily.ticker == pos.ticker)
            .order_by(PriceDaily.date.desc())
            .limit(1)
        )
        latest = price_result.scalar()
        current_value = pos.quantity * (latest or pos.entry_price)
        total_current += current_value

        # Group by ticker for allocation
        if pos.ticker not in by_type:
            by_type[pos.ticker] = 0.0
        by_type[pos.ticker] += current_value

    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    # Allocation percentages
    allocation = {}
    for ticker, value in by_type.items():
        allocation[ticker] = round(value / total_current * 100, 1) if total_current > 0 else 0

    return {
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "open_positions": len(positions),
        "allocation": allocation,
    }
