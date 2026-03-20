import enum
from sqlalchemy import Column, Integer, String, Enum, Boolean, DateTime, func

from app.database import Base


class AssetType(str, enum.Enum):
    ACCION = "accion"
    CEDEAR = "cedear"
    BONO_SOBERANO = "bono_soberano"
    LETRA = "letra"
    ON = "obligacion_negociable"
    FUTURO = "futuro"
    OTRO = "otro"


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    asset_type = Column(Enum(AssetType), nullable=False, index=True)
    sector = Column(String(100), nullable=True)
    currency = Column(String(10), default="ARS")
    is_active = Column(Boolean, default=True)
    # For CEDEARs: underlying ticker in US market
    underlying_ticker = Column(String(20), nullable=True)
    ratio_cedear = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Asset {self.ticker} ({self.asset_type.value})>"
