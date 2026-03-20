from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, func

from app.database import Base


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    entry_date = Column(Date, nullable=False)
    exit_price = Column(Float, nullable=True)
    exit_date = Column(Date, nullable=True)
    commission = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    is_open = Column(Integer, default=1)  # 1=open, 0=closed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def invested_amount(self) -> float:
        return self.quantity * self.entry_price + self.commission

    def __repr__(self):
        status = "OPEN" if self.is_open else "CLOSED"
        return f"<Position {self.ticker} x{self.quantity} @ ${self.entry_price} [{status}]>"
