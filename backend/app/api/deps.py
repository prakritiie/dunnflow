from __future__ import annotations
import time
from collections import defaultdict, deque
from fastapi import Header, Request
from app.core.config import settings
from app.core.exceptions import RateLimited, Unauthorized

_HITS: dict[str, deque] = defaultdict(deque)


async def require_token(authorization: str | None = Header(default=None)) -> None:
    """Single static bearer on writes. There is no login UI, so this is the honest
    control - not an invented session system."""
    if not settings.auth_enabled:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise Unauthorized("Missing bearer token")
    if authorization.removeprefix("Bearer ").strip() != settings.DUNNFLOW_API_TOKEN:
        raise Unauthorized("Invalid bearer token")


async def rate_limit_write(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    q = _HITS[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.RATE_LIMIT_WRITES_PER_MIN:
        raise RateLimited(detail={"limit_per_min": settings.RATE_LIMIT_WRITES_PER_MIN})
    q.append(now)
