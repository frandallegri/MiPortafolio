from sqlalchemy import Column, Integer, String, Float, Date, DateTime, BigInteger, func, UniqueConstraint

from app.database import Base


class PriceDaily(Base):
    __tablename__ = "prices_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=True)
    adjusted_close = Column(Float, nullable=True)
    change_pct = Column(Float, nullable=True)  # Variación porcentual diaria
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_ticker_date"),
    )

    def __repr__(self):
        return f"<Price {self.ticker} {self.date}: ${self.close}>"
