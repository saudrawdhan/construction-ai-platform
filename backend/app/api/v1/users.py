from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession
from app.models import User
from app.schemas.common import Page
from app.schemas.user import UserAdminCreate, UserAdminUpdate, UserRead
from app.security.deps import require_roles
from app.security.roles import Role
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])

AdminOnly = Annotated[User, Depends(require_roles(Role.ADMIN))]


@router.get("", response_model=Page[UserRead])
async def list_users(
    db: DbSession,
    _: AdminOnly,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[UserRead]:
    items, total = await user_service.list_users(db, page=page, size=size)
    return Page.build([UserRead.model_validate(u) for u in items], total, page, size)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserAdminCreate, db: DbSession, _: AdminOnly) -> UserRead:
    if await user_service.get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A user with this email already exists"
        )
    user = await user_service.create_user(
        db,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role.value,
        password=payload.password,
    )
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, payload: UserAdminUpdate, db: DbSession, admin: AdminOnly
) -> UserRead:
    # Guard against an admin locking themselves out of the platform.
    if user_id == admin.id and (
        payload.is_active is False
        or (payload.role is not None and payload.role != Role.ADMIN)
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate or change the role of your own admin account",
        )
    user = await user_service.update_user(
        db,
        user_id,
        full_name=payload.full_name,
        role=payload.role.value if payload.role is not None else None,
        is_active=payload.is_active,
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)
