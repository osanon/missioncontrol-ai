"""Rate limits and the daily AI budget, so a public demo URL cannot be used to guess tokens or spend credits.

Limits are kept in memory per client IP, which is correct for the single backend process this app runs.
The client IP comes from X-Real-IP, set by the bundled Nginx; the backend is not exposed directly.
"""
import os
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from sqlalchemy import func, select


class Limiter:
    def __init__(self):
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key, limit, window):
        now = time.monotonic()
        with self.lock:
            hits = self.hits[key]
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                raise HTTPException(429, 'Too many requests. Please wait a moment and try again.',
                                    headers={'Retry-After': str(max(1, int(window - (now - hits[0]))))})
            hits.append(now)

    def reset(self):
        with self.lock:
            self.hits.clear()


limiter = Limiter()


def client_ip(request: Request):
    return request.headers.get('x-real-ip') or (request.client.host if request.client else 'unknown')


def env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def login_limit(request: Request):
    limiter.check(('login', client_ip(request)), env_int('LOGIN_RATE_PER_MINUTE', 10), 60)


def ai_limit(request: Request):
    # Demo mode makes no model calls, so only live AI requests are limited.
    if os.getenv('AGENT_MODE', 'demo') == 'live':
        limiter.check(('ai', client_ip(request)), env_int('AI_RATE_PER_HOUR', 30), 3600)


class BudgetExceeded(ValueError):
    """The daily AI token budget is used up. Maps to HTTP 429."""


def check_ai_budget():
    """Refuse new live AI runs once today's recorded token use reaches AI_DAILY_TOKEN_BUDGET (0 or unset: no cap)."""
    budget = env_int('AI_DAILY_TOKEN_BUDGET', 0)
    if budget <= 0:
        return
    from backend.db import engine, runs
    today = datetime.now(timezone.utc).date().isoformat()
    with engine.connect() as c:
        used = c.scalar(select(func.coalesce(func.sum(func.coalesce(runs.c.input_tokens, 0) + func.coalesce(runs.c.output_tokens, 0)), 0))
                        .where(runs.c.created_at >= today)) or 0
    if used >= budget:
        raise BudgetExceeded("Today's AI budget is used up. Demo mode still works; live AI resumes tomorrow (UTC).")
