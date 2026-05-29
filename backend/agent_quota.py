"""
Agent usage quota — gates the AI writing agent behind the Author Pro plan.

Rules
-----
- Active subscribers (any plan): unlimited.
- Everyone else: FREE_DAILY_LIMIT agent messages per UTC day (chat + Cmd-K combined).

Single source of truth: the `agent_usage` collection, one document per
(user_id, date_utc). Counter increments via $inc on a successful agent call.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

FREE_DAILY_LIMIT = 5


def utc_date_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def get_today_usage(db, user_id: str) -> int:
    """Return how many agent calls the user has made today (UTC)."""
    doc = await db.agent_usage.find_one(
        {"user_id": user_id, "date": utc_date_key()},
        {"_id": 0, "count": 1},
    )
    return int((doc or {}).get("count", 0))


async def increment_usage(db, user_id: str) -> int:
    """Atomically increment today's counter and return the new value."""
    result = await db.agent_usage.find_one_and_update(
        {"user_id": user_id, "date": utc_date_key()},
        {
            "$inc": {"count": 1},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {"user_id": user_id, "date": utc_date_key()},
        },
        upsert=True,
        return_document=True,
    )
    return int((result or {}).get("count", 1))


async def check_and_charge(
    db,
    *,
    user_id: str,
    subscription_active: bool,
) -> Tuple[Optional[int], Optional[int]]:
    """Atomically gate + charge a single agent call.

    Returns (remaining_after, daily_limit). For subscribers, returns (None, None)
    to signal "unlimited". For free users:
      - If they're already at/over the limit, raises a quota-exceeded sentinel
        by returning (-1, FREE_DAILY_LIMIT) so the caller can 402.
      - Otherwise, increments the counter and returns (remaining_after, limit).
    """
    if subscription_active:
        return None, None

    used = await get_today_usage(db, user_id)
    if used >= FREE_DAILY_LIMIT:
        return -1, FREE_DAILY_LIMIT

    new_count = await increment_usage(db, user_id)
    remaining = max(0, FREE_DAILY_LIMIT - new_count)
    return remaining, FREE_DAILY_LIMIT


async def quota_snapshot(
    db, *, user_id: str, subscription_active: bool
) -> dict:
    """Read-only quota state for the frontend to display a counter."""
    if subscription_active:
        return {"unlimited": True}
    used = await get_today_usage(db, user_id)
    return {
        "unlimited": False,
        "used": used,
        "limit": FREE_DAILY_LIMIT,
        "remaining": max(0, FREE_DAILY_LIMIT - used),
    }
