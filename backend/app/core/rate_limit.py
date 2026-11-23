"""Rate Limiting Middleware and Token Bucket Limiter."""

import time
from typing import Dict, Tuple

from fastapi import Request

from backend.app.core.config import settings
from backend.app.core.exceptions import RateLimitExceededError
from backend.app.core.logging import logger

# In-memory storage for local dev / testing fallback: ip -> [(timestamp, count)]
_in_memory_buckets: Dict[str, list[float]] = {}


class RateLimiter:
    """Sliding window rate limiter with Redis support and in-memory fallback."""

    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60

    async def is_allowed(self, key: str) -> Tuple[bool, int]:
        """Check if request is allowed for key. Returns (allowed, remaining)."""
        if not settings.RATE_LIMIT_ENABLED:
            return True, self.requests_per_minute

        now = time.time()
        window_start = now - self.window_seconds

        # Fallback in-memory implementation
        records = _in_memory_buckets.get(key, [])
        # filter out entries outside the window
        valid_records = [t for t in records if t > window_start]

        if len(valid_records) >= self.requests_per_minute:
            _in_memory_buckets[key] = valid_records
            return False, 0

        valid_records.append(now)
        _in_memory_buckets[key] = valid_records
        return True, self.requests_per_minute - len(valid_records)

    async def __call__(self, request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return

        client_ip = request.client.host if request.client else "127.0.0.1"
        endpoint = request.url.path
        key = f"rate_limit:{client_ip}:{endpoint}"

        allowed, remaining = await self.is_allowed(key)
        if not allowed:
            logger.warning(f"Rate limit exceeded for {key}")
            raise RateLimitExceededError(
                message=f"Rate limit exceeded ({self.requests_per_minute} req/min). Please try again shortly.",
                details={"client_ip": client_ip, "limit": self.requests_per_minute},
            )


# Default limiter instances
auth_rate_limiter = RateLimiter(requests_per_minute=10)
agent_rate_limiter = RateLimiter(requests_per_minute=20)
general_rate_limiter = RateLimiter(requests_per_minute=100)
