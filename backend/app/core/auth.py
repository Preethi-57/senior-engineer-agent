from fastapi import Header, HTTPException
from .settings import settings

def require_api_key(x_api_key: str | None = Header(default=None)):
    if settings.app_env == "development" and not settings.api_key:
        return
    if not settings.api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Valid X-API-Key required")
