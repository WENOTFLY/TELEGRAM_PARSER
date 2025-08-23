from __future__ import annotations

"""Authentication routes."""

import base64
import hashlib
import hmac
import json
import time
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from ..models import Base, User

# Database setup
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(prefix="/auth")


def _verify_telegram_hash(data: Dict[str, str]) -> bool:
    """Verify Telegram login data using the bot token."""
    if settings.telegram_auth_token is None:
        return False
    received_hash = data.get("hash")
    if received_hash is None:
        return False
    data_check = {k: v for k, v in data.items() if k != "hash"}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_check.items()))
    secret_key = hashlib.sha256(settings.telegram_auth_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_hash, received_hash)


def _encode_jwt(payload: Dict[str, str], *, expires_in: int = 60 * 60 * 24) -> str:
    """Create a signed JWT using HS256."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = payload.copy()
    payload["exp"] = int(time.time()) + expires_in

    def _b64(data: Dict[str, str]) -> bytes:
        return base64.urlsafe_b64encode(
            json.dumps(data, separators=(",", ":")).encode()
        ).rstrip(b"=")

    segments = [_b64(header), _b64(payload)]
    signing_input = b".".join(segments)
    signature = base64.urlsafe_b64encode(
        hmac.new(settings.secret_key.encode(), signing_input, hashlib.sha256).digest()
    ).rstrip(b"=")
    return b".".join((*segments, signature)).decode()


@router.get("/telegram/callback")
async def telegram_callback(
    request: Request, response: Response, db: Session = Depends(get_db)
):
    """Handle Telegram login callback."""
    data = dict(request.query_params)
    if not _verify_telegram_hash(data):
        raise HTTPException(status_code=400, detail="invalid hash")

    tg_id = int(data["id"])
    stmt = select(User).where(User.tg_id == tg_id)
    user = db.execute(stmt).scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_id)
        db.add(user)

    user.username = data.get("username")
    user.first_name = data.get("first_name")
    user.last_name = data.get("last_name")
    user.photo_url = data.get("photo_url")
    db.commit()
    db.refresh(user)

    token = _encode_jwt({"sub": str(user.id)})
    res = JSONResponse({"status": "ok"})
    res.set_cookie(
        "jwt", token, httponly=True, secure=True, samesite="lax"
    )
    return res


@router.post("/logout")
async def logout() -> Response:
    """Clear authentication cookie."""
    res = JSONResponse({"status": "ok"})
    res.set_cookie(
        "jwt", "", max_age=0, httponly=True, secure=True, samesite="lax"
    )
    return res
