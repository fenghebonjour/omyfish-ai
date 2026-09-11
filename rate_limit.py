"""
rate_limit.py
-------------
Simple in-memory per-IP fixed-window rate limiter — no Redis, matching a
single-instance deployment (mirrors omyfish-java's api-gateway RateLimitFilter).

This service is called directly, with no gateway in front of it, by omyfish-ios
and the public Hugging Face Space (see README.md) — so it's the only thing
standing between the public internet and both a compute-bound model and a
per-token-billed Groq API call. Every enterprise sibling's own gateway also
rate-limits /identify and /bite-score/*, but that can't be relied on here
(BACKLOG.md item G, WEAKNESS_AUDIT.md §1.2).
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
        self._lock = Lock()

    def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self._lock:
            window_start, count = self._hits[client_ip]
            if now - window_start >= self.window_seconds:
                window_start, count = now, 0
            count += 1
            self._hits[client_ip] = (window_start, count)

        if count > self.limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again shortly.")
