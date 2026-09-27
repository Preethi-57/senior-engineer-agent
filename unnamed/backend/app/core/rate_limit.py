from collections import defaultdict, deque
from time import monotonic
from threading import Lock
from fastapi import HTTPException, Request
from .settings import settings

class RateLimiter:
    def __init__(self): self._hits=defaultdict(deque); self._lock=Lock()
    def check(self, key:str):
        now=monotonic(); cutoff=now-60
        with self._lock:
            q=self._hits[key]
            while q and q[0] < cutoff: q.popleft()
            if len(q) >= settings.rate_limit_per_minute: raise HTTPException(429,"Rate limit exceeded")
            q.append(now)

limiter=RateLimiter()

def rate_limit(request: Request):
    limiter.check(request.client.host if request.client else "unknown")
