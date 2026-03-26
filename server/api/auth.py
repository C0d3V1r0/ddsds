# - Middleware аутентификации API-запросов через Bearer-токен
import hmac
from fastapi import HTTPException, Request

_api_token: str = ""


def set_api_token(token: str) -> None:
    """- Устанавливает токен для проверки в middleware"""
    global _api_token
    _api_token = token


def require_auth(request: Request) -> None:
    """- Проверяет Bearer-токен в заголовке Authorization"""
    # - Пустой токен означает отключённую аутентификацию (тесты, dev без секрета)
    if not _api_token:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = auth[7:]
    if not hmac.compare_digest(token, _api_token):
        raise HTTPException(status_code=401, detail="Invalid token")
