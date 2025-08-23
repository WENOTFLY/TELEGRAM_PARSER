from __future__ import annotations

"""QR authentication routes."""

import base64
import time
import uuid
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..models import TGAccount
from ..crypto import encrypt_string_session
from .auth import get_db

router = APIRouter(prefix="/v1/auth")

# In-memory store for QR login sessions
_qr_logins: Dict[str, Dict[str, Any]] = {}

# Minimal 1x1 PNG used as placeholder for QR codes
_ONE_PX_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@router.post("/qr")
async def create_qr() -> Dict[str, str]:
    """Generate a new login id and placeholder QR code."""
    login_id = uuid.uuid4().hex
    _qr_logins[login_id] = {"status": "PENDING", "ts": time.time()}
    qr_png_b64 = base64.b64encode(_ONE_PX_PNG).decode()
    return {"login_id": login_id, "qr_png_b64": qr_png_b64}


@router.get("/qr/{login_id}")
async def check_qr(login_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Check login status for a given id."""
    rec = _qr_logins.get(login_id)
    if rec is None:
        return {"status": "EXPIRED"}
    if time.time() - rec["ts"] > 300:
        rec["status"] = "EXPIRED"
        return {"status": "EXPIRED"}
    status = rec["status"]
    if status == "AUTHORIZED" and rec.get("session") and not rec.get("stored"):
        cipher, kver = encrypt_string_session(rec["session"])
        acct = TGAccount(
            user_id=rec.get("user_id", 1),
            session_cipher=cipher,
            kver=kver,
            phone=rec.get("phone"),
            is_active=True,
        )
        db.add(acct)
        db.commit()
        rec["stored"] = True
    return {"status": status}
