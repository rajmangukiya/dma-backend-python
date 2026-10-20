from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.auth.dependencies import CurrentCompanyId, CurrentUser, require
from src.auth.permissions import Permission
from src.common.errors import AppError
from src.common.schemas import ApiResponse, ok
from src.database.session import DbSession
from src.users import service
from src.users.models import User
from src.users.schemas import (
    CreateUserRequest,
    PublicUser,
    ResetPasswordRequest,
    UpdateUserRequest,
)

# Company admin: users of their own company
router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[Depends(require(Permission.MANAGE_USERS))]
)


async def _load(db: DbSession, company_id: UUID, user_id: UUID) -> User:
    user = await service.get_company_user(db, company_id, user_id)
    if not user:
        raise AppError.not_found("User not found")
    return user


@router.get("")
async def list_users(db: DbSession, company_id: CurrentCompanyId) -> ApiResponse[list[PublicUser]]:
    users = await service.list_company_users(db, company_id)
    return ok([PublicUser.model_validate(user) for user in users])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[PublicUser]:
    user = await service.create_user(db, company_id, body.username, body.password, body.role)
    return ok(PublicUser.model_validate(user), "User created")


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    body: UpdateUserRequest,
    db: DbSession,
    company_id: CurrentCompanyId,
    actor: CurrentUser,
) -> ApiResponse[PublicUser]:
    user = await _load(db, company_id, user_id)
    user = await service.update_user(db, user, body.changes(), actor_id=actor.id)
    return ok(PublicUser.model_validate(user), "User updated")


@router.put("/{user_id}/password")
async def reset_password(
    user_id: UUID, body: ResetPasswordRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[None]:
    user = await _load(db, company_id, user_id)
    await service.reset_password(db, user, body.password)
    return ok(None, "Password updated")


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID, db: DbSession, company_id: CurrentCompanyId, actor: CurrentUser
) -> ApiResponse[None]:
    user = await _load(db, company_id, user_id)
    await service.delete_user(db, user, actor_id=actor.id)
    return ok(None, "User deleted")
