from __future__ import annotations

"""Routes for managing user channel subscriptions."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import settings
from ..crypto import decrypt_string_session
from ..models import Channel, Subscription, TGAccount, User, Visibility
from .auth import get_current_user, get_db

router = APIRouter(prefix="/v1/channels")


def _normalize_identifier(value: str) -> str:
    """Normalize various channel identifiers to a simple token."""
    ident = value.strip()
    if ident.startswith("http://") or ident.startswith("https://"):
        ident = ident.split("/")[-1]
    if ident.startswith("@"):
        ident = ident[1:]
    return ident


@router.post("/subscribe")
async def subscribe(
    channel: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Subscribe the current user to a Telegram channel."""

    if settings.telegram_api_id is None or settings.telegram_api_hash is None:
        raise HTTPException(status_code=500, detail="telegram api not configured")

    account = (
        db.query(TGAccount)
        .filter(TGAccount.user_id == user.id, TGAccount.is_active.is_(True))
        .first()
    )
    if account is None:
        raise HTTPException(status_code=400, detail="no active account")

    session = decrypt_string_session(account.session_cipher, account.kver)
    identifier = _normalize_identifier(channel)
    try:
        async with TelegramClient(
            StringSession(session), settings.telegram_api_id, settings.telegram_api_hash
        ) as client:
            entity = await client.get_entity(identifier)
    except Exception as exc:  # noqa: BLE001 - broad to map Telethon errors
        raise HTTPException(status_code=400, detail="channel not accessible") from exc

    username = getattr(entity, "username", None)
    title = getattr(entity, "title", None)
    visibility = Visibility.PUBLIC if username else Visibility.PRIVATE

    existing = None
    if username:
        existing = db.query(Channel).filter_by(username=username).one_or_none()
    if existing is None:
        existing = Channel(
            username=username,
            title=title,
            visibility=visibility,
            owner_account_id=account.id,
        )
        db.add(existing)
        db.flush()

    if (
        db.query(Subscription)
        .filter_by(user_id=user.id, channel_id=existing.id)
        .first()
        is None
    ):
        db.add(Subscription(user_id=user.id, channel_id=existing.id))

    db.commit()
    return {"status": "ok"}


@router.delete("/unsubscribe")
async def unsubscribe(
    channel_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a subscription for the current user."""

    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="not found")

    sub = (
        db.query(Subscription)
        .filter_by(user_id=user.id, channel_id=channel_id)
        .one_or_none()
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="not subscribed")

    db.delete(sub)
    db.commit()
    return {"status": "ok"}


@router.get("/my")
async def my_channels(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List channels subscribed by the current user."""

    subs = (
        db.query(Subscription)
        .join(Channel, Subscription.channel_id == Channel.id)
        .filter(Subscription.user_id == user.id)
        .all()
    )
    return [
        {
            "id": s.channel.id,
            "username": s.channel.username,
            "title": s.channel.title,
            "status": s.channel.visibility.value,
        }
        for s in subs
    ]


__all__ = ["router"]

