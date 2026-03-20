from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON, func, UniqueConstraint

from app.database import Base


class ScoringResult(Base):
    """Stores daily scoring results for each asset."""
    __tablename__ = "scoring_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    score = Column(Float, nullable=False)  # 0-100 probability score
    signal = Column(String(10), nullable=False)  # "compra", "venta", "neutral"
    confidence = Column(Float, nullable=False)  # 0-100 confidence level
    # Detailed breakdown of each indicator's contribution
    indicators_detail = Column(JSON, nullable=True)
    # ML model score (Phase 4)
    ml_score = Column(Float, nullable=True)
    # Ensemble score (rule-based + ML)
    ensemble_score = Column(Float, nullable=True)
    # Was the prediction correct? (filled next day)
    actual_direction = Column(String(10), nullable=True)  # "up", "down", "flat"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_scoring_ticker_date"),
    )
