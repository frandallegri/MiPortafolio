from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Resolve .env path relative to this file (backend/.env)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/miportafolio"

    # Auth
    admin_email: str = "admin@miportafolio.com"
    admin_password_hash: str = ""
    jwt_secret: str = "dev-secret-cambiar-en-prod"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 72

    # APIs
    data912_base_url: str = "https://data912.com"
    bcra_api_base_url: str = "https://api.bcra.gob.ar"
    estadisticas_bcra_token: str = ""
    dolar_api_base_url: str = "https://dolarapi.com"

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_email: str = ""

    # App
    scoring_threshold: float = 65.0
    market_open_hour: int = 11
    market_close_hour: int = 17

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
