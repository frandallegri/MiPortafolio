from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth import verify_password, create_access_token, hash_password, get_current_user
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


class HashRequest(BaseModel):
    password: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Authenticate the single admin user."""
    if req.email != settings.admin_email:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not settings.admin_password_hash:
        raise HTTPException(status_code=500, detail="Password hash no configurado en el servidor")

    if not verify_password(req.password, settings.admin_password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = create_access_token(req.email)
    return LoginResponse(access_token=token, email=req.email)


@router.post("/hash")
async def generate_hash(req: HashRequest):
    """
    Utility endpoint to generate a bcrypt hash.
    Use this once to generate ADMIN_PASSWORD_HASH for your .env.
    REMOVE or protect this in production.
    """
    return {"hash": hash_password(req.password)}
