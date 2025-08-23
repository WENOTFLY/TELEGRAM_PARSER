from __future__ import annotations

"""Routes exposing AI usage statistics."""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import AIUsage, User
from .auth import get_current_user, get_db

router = APIRouter(prefix="/v1")


class UsageItem(BaseModel):
    ts: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    purpose: Optional[str] = None


class UsageResponse(BaseModel):
    window: str
    items: List[UsageItem]
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    window: str = "30d",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return AI usage for the given time window (default 30 days)."""
    days = 30
    if window.endswith("d"):
        try:
            days = int(window[:-1])
        except ValueError:  # pragma: no cover - invalid handled by default
            pass
    since = datetime.utcnow() - timedelta(days=days)

    entries = (
        db.query(AIUsage)
        .filter(AIUsage.user_id == user.id, AIUsage.ts >= since)
        .order_by(AIUsage.ts.desc())
        .all()
    )
    items = [
        UsageItem(
            ts=e.ts,
            model=e.model,
            input_tokens=e.input_tokens,
            output_tokens=e.output_tokens,
            cost_usd=e.cost_usd,
            purpose=e.purpose,
        )
        for e in entries
    ]
    totals = (
        db.query(
            func.coalesce(func.sum(AIUsage.input_tokens), 0),
            func.coalesce(func.sum(AIUsage.output_tokens), 0),
            func.coalesce(func.sum(AIUsage.cost_usd), 0.0),
        )
        .filter(AIUsage.user_id == user.id, AIUsage.ts >= since)
        .one()
    )
    return UsageResponse(
        window=window,
        items=items,
        total_input_tokens=int(totals[0]),
        total_output_tokens=int(totals[1]),
        total_cost_usd=float(totals[2]),
    )
