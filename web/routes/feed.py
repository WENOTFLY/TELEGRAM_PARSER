from __future__ import annotations

"""Feed retrieval endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import Message, Subscription, User
from .auth import get_current_user, get_db
from ..cache import cache_get, cache_set, cache_invalidate

router = APIRouter(prefix="/v1/feed")


def _cache_key(user_id: int, params: dict[str, Any]) -> str:
    parts = [str(user_id)]
    for key in ["date_from", "date_to", "channel_id", "type", "lang"]:
        val = params.get(key)
        if isinstance(val, datetime):
            parts.append(val.isoformat())
        else:
            parts.append(str(val))
    return "feed:" + ":".join(parts)


@router.get("")
async def get_feed(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    channel_id: int | None = None,
    type: str | None = None,
    lang: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return messages for the current user with optional filters."""

    params = {
        "date_from": date_from,
        "date_to": date_to,
        "channel_id": channel_id,
        "type": type,
        "lang": lang,
    }
    key = _cache_key(user.id, params)
    cached = await cache_get(key)
    if cached is not None:
        return cached

    q = (
        db.query(Message)
        .join(
            Subscription,
            (Subscription.channel_id == Message.channel_id)
            & (Subscription.user_id == user.id),
        )
    )
    if date_from:
        q = q.filter(Message.date >= date_from)
    if date_to:
        q = q.filter(Message.date <= date_to)
    if channel_id:
        q = q.filter(Message.channel_id == channel_id)
    if type:
        q = q.filter(Message.type == type)
    if lang:
        q = q.filter(Message.lang == lang)

    messages = q.order_by(Message.date.desc()).limit(100).all()
    result = [
        {
            "id": m.id,
            "channel_id": m.channel_id,
            "msg_id": m.msg_id,
            "date": m.date.isoformat(),
            "text": m.text,
            "author": m.author,
            "views": m.views,
            "reactions": m.reactions,
            "forwards": m.forwards,
            "comments": m.comments,
            "lang": m.lang,
            "type": m.type,
        }
        for m in messages
    ]

    await cache_set(key, result)
    return result


async def invalidate_feed_cache(user_id: int) -> None:
    """Invalidate feed cache for the given user."""
    await cache_invalidate(f"feed:{user_id}:")


__all__ = ["router", "invalidate_feed_cache"]
