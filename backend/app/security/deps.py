from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.session import get_db
from app.models import User
from app.security.tokens import decode_access_token

# auto_error=False so a missing Authorization header falls through to the cookie instead of 401.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)
settings = get_settings()

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    # The SPA authenticates via an httpOnly cookie; a bearer header still works for Swagger and
    # API clients.
    raw_token = token or request.cookies.get(settings.auth_cookie_name)
    if raw_token is None:
        raise _CREDENTIALS_ERROR
    try:
        payload = decode_access_token(raw_token)
    except InvalidTokenError:
        raise _CREDENTIALS_ERROR from None
    subject = payload.get("sub")
    if subject is None:
        raise _CREDENTIALS_ERROR
    user = await db.get(User, int(subject))
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[[User], Awaitable[User]]:
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )
        return user

    return checker
