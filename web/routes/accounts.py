from __future__ import annotations

"""Telegram account management routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import TGAccount
from .auth import get_db

router = APIRouter(prefix="/v1/accounts")


@router.get("/")
async def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(TGAccount).all()
    return [
        {
            "id": a.id,
            "phone": a.phone,
            "is_active": a.is_active,
            "kver": a.kver,
        }
        for a in accounts
    ]


@router.delete("/{account_id}")
async def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(TGAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(account)
    db.commit()
    return {"status": "ok"}
