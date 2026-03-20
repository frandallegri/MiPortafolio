from sqlalchemy import Column, Integer, String, Float, Date, DateTime, func, UniqueConstraint

from app.database import Base


class MacroData(Base):
    """Stores macroeconomic indicators: dollar rates, risk, inflation, etc."""
    __tablename__ = "macro_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    indicator = Column(String(50), nullable=False, index=True)  # e.g. "dolar_mep", "riesgo_pais", "merval"
    date = Column(Date, nullable=False, index=True)
    value = Column(Float, nullable=False)
    extra = Column(String(200), nullable=True)  # Additional context if needed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("indicator", "date", name="uq_indicator_date"),
    )
