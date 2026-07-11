from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.security.passwords import hash_password, verify_password


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email))


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def list_users(
    db: AsyncSession, *, page: int, size: int
) -> tuple[list[User], int]:
    total = await db.scalar(select(func.count()).select_from(User))
    rows = await db.scalars(
        select(User).order_by(User.id).offset((page - 1) * size).limit(size)
    )
    return list(rows), int(total or 0)


async def update_user(
    db: AsyncSession,
    user_id: int,
    *,
    full_name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> User | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    if full_name is not None:
        user.full_name = full_name
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    await db.flush()
    return user


async def create_user(
    db: AsyncSession, *, email: str, full_name: str, role: str, password: str
) -> User:
    user = User(
        email=email,
        full_name=full_name,
        role=role,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if user and user.is_active and verify_password(password, user.hashed_password):
        return user
    return None
