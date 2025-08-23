from __future__ import annotations

"""Routes for ranking endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import Message, Ranking, Topic, User
from .auth import get_current_user, get_db
from ..cache import cache_get, cache_set, cache_invalidate

router = APIRouter(prefix="/v1/top")


@router.get("")
async def get_top(
    window: str,
    by: str = "message",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return top messages or topics for the given window."""
    if window not in {"24h", "7d"}:
        raise HTTPException(status_code=400, detail="invalid window")
    if by not in {"message", "topic"}:
        raise HTTPException(status_code=400, detail="invalid by")

    key = f"top:{by}:{window}"
    cached = await cache_get(key)
    if cached is not None:
        return cached

    q = (
        db.query(Ranking)
        .filter(Ranking.entity_kind == by, Ranking.window == window)
        .order_by(Ranking.score.desc())
        .limit(10)
    )

    results = []
    for r in q.all():
        if by == "message":
            msg = db.get(Message, r.entity_id)
            if msg:
                results.append(
                    {
                        "id": msg.id,
                        "channel_id": msg.channel_id,
                        "msg_id": msg.msg_id,
                        "date": msg.date.isoformat(),
                        "text": msg.text,
                        "score": r.score,
                    }
                )
        else:
            topic = db.get(Topic, r.entity_id)
            if topic:
                results.append(
                    {
                        "id": topic.id,
                        "title": topic.title,
                        "score": r.score,
                    }
                )

    await cache_set(key, results)
    return results


async def invalidate_top_cache(window: str | None = None, by: str | None = None) -> None:
    """Invalidate cached rankings."""
    prefix = "top:"
    if by:
        prefix += f"{by}:"
    if window:
        prefix += f"{window}"
    await cache_invalidate(prefix)


__all__ = ["router", "invalidate_top_cache"]
