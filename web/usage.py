from __future__ import annotations

"""Helpers for tracking AI usage and enforcing plan limits."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import AIUsage, User

# Monthly cost limits per user plan in USD. ``None`` means unlimited.
PLAN_LIMITS_USD = {
    "free": 1.0,
    "pro": 20.0,
    "enterprise": None,
}


def check_plan_limit(db: Session, user: User, *, additional_cost: float = 0.0) -> None:
    """Ensure the user has enough quota for the additional cost."""
    plan = (user.plan or "free").lower()
    limit = PLAN_LIMITS_USD.get(plan)
    if limit is None:
        return
    since = datetime.utcnow() - timedelta(days=30)
    total = (
        db.query(func.coalesce(func.sum(AIUsage.cost_usd), 0.0))
        .filter(AIUsage.user_id == user.id, AIUsage.ts >= since)
        .scalar()
        or 0.0
    )
    if total + additional_cost > limit:
        raise HTTPException(status_code=429, detail="plan limit exceeded")


def log_ai_usage(
    db: Session,
    user_id: int,
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    purpose: Optional[str] = None,
) -> None:
    """Persist an :class:`AIUsage` record."""
    usage = AIUsage(
        user_id=user_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        purpose=purpose,
    )
    db.add(usage)
    db.commit()
