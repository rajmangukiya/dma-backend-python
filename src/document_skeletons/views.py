from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.auth.dependencies import CurrentCompanyId, require
from src.auth.permissions import Permission
from src.common.errors import AppError
from src.common.schemas import ApiResponse, ok
from src.database.session import DbSession
from src.document_skeletons import flows, service
from src.document_skeletons.models import DocumentSkeleton, DocumentSkeletonField
from src.document_skeletons.schemas import (
    AddMatchRequest,
    CreateFieldRequest,
    CreateSkeletonRequest,
    MatchCandidate,
    SkeletonDetail,
    SkeletonListItem,
    UpdateFieldRequest,
    UpdateSkeletonRequest,
)

# Document skeletons, their fields and one-way match rules
router = APIRouter(prefix="/document-skeletons", tags=["document skeletons"])

can_view = [Depends(require(Permission.VIEW_DOCUMENT_SKELETONS))]
can_manage = [Depends(require(Permission.MANAGE_DOCUMENT_SKELETONS))]


async def _load(db: DbSession, company_id: UUID, skeleton_id: UUID) -> DocumentSkeleton:
    skeleton = await service.get_skeleton(db, skeleton_id, company_id)
    if not skeleton:
        raise AppError.not_found("Skeleton not found")
    return skeleton


async def _load_field(db: DbSession, skeleton_id: UUID, field_id: UUID) -> DocumentSkeletonField:
    field = await service.get_field(db, skeleton_id, field_id)
    if not field:
        raise AppError.not_found("Field not found")
    return field


@router.get("", dependencies=can_view)
async def list_skeletons(
    db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[list[SkeletonListItem]]:
    return ok(await flows.list_skeletons(db, company_id))


@router.post("", dependencies=can_manage, status_code=status.HTTP_201_CREATED)
async def create_skeleton(
    body: CreateSkeletonRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[SkeletonDetail]:
    skeleton = await service.create_skeleton(
        db, company_id, body.title, body.document_type, body.description
    )
    return ok(await service.get_detail(db, skeleton), "Skeleton created")


@router.get("/{skeleton_id}", dependencies=can_view)
async def get_skeleton(
    skeleton_id: UUID, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[SkeletonDetail]:
    skeleton = await _load(db, company_id, skeleton_id)
    return ok(await service.get_detail(db, skeleton))


@router.patch("/{skeleton_id}", dependencies=can_manage)
async def update_skeleton(
    skeleton_id: UUID, body: UpdateSkeletonRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[SkeletonDetail]:
    skeleton = await _load(db, company_id, skeleton_id)
    skeleton = await service.update_skeleton(db, skeleton, body.changes())
    return ok(await service.get_detail(db, skeleton), "Skeleton saved")


# Documents already in journeys keep their snapshot of the fields
@router.delete("/{skeleton_id}", dependencies=can_manage)
async def delete_skeleton(
    skeleton_id: UUID, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[None]:
    skeleton = await _load(db, company_id, skeleton_id)
    await service.delete_skeleton(db, skeleton)
    return ok(None, "Skeleton deleted")


# Other skeletons and their fields, for the "matches with" picker
@router.get("/{skeleton_id}/match-candidates", dependencies=can_manage)
async def match_candidates(
    skeleton_id: UUID, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[list[MatchCandidate]]:
    skeleton = await _load(db, company_id, skeleton_id)
    return ok(await service.match_candidates(db, skeleton))


@router.post("/{skeleton_id}/fields", dependencies=can_manage, status_code=status.HTTP_201_CREATED)
async def add_field(
    skeleton_id: UUID, body: CreateFieldRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[SkeletonDetail]:
    skeleton = await _load(db, company_id, skeleton_id)
    await service.create_field(db, skeleton.id, body.name, body.type)
    return ok(await service.get_detail(db, skeleton), "Field added")


@router.patch("/{skeleton_id}/fields/{field_id}", dependencies=can_manage)
async def update_field(
    skeleton_id: UUID,
    field_id: UUID,
    body: UpdateFieldRequest,
    db: DbSession,
    company_id: CurrentCompanyId,
) -> ApiResponse[SkeletonDetail]:
    skeleton = await _load(db, company_id, skeleton_id)
    field = await _load_field(db, skeleton.id, field_id)
    await service.update_field(db, field, body.changes())
    return ok(await service.get_detail(db, skeleton), "Field updated")


@router.delete("/{skeleton_id}/fields/{field_id}", dependencies=can_manage)
async def delete_field(
    skeleton_id: UUID, field_id: UUID, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[SkeletonDetail]:
    skeleton = await _load(db, company_id, skeleton_id)
    field = await _load_field(db, skeleton.id, field_id)
    await service.delete_field(db, field)
    return ok(await service.get_detail(db, skeleton), "Field removed")


@router.post(
    "/{skeleton_id}/fields/{field_id}/matches",
    dependencies=can_manage,
    status_code=status.HTTP_201_CREATED,
)
async def add_match(
    skeleton_id: UUID,
    field_id: UUID,
    body: AddMatchRequest,
    db: DbSession,
    company_id: CurrentCompanyId,
) -> ApiResponse[SkeletonDetail]:
    skeleton = await _load(db, company_id, skeleton_id)
    field = await _load_field(db, skeleton.id, field_id)
    await service.add_match(db, field, body.match_field_id, company_id)
    return ok(await service.get_detail(db, skeleton), "Match rule added")


@router.delete("/{skeleton_id}/fields/{field_id}/matches/{match_field_id}", dependencies=can_manage)
async def remove_match(
    skeleton_id: UUID,
    field_id: UUID,
    match_field_id: UUID,
    db: DbSession,
    company_id: CurrentCompanyId,
) -> ApiResponse[SkeletonDetail]:
    skeleton = await _load(db, company_id, skeleton_id)
    field = await _load_field(db, skeleton.id, field_id)
    await service.remove_match(db, field, match_field_id)
    return ok(await service.get_detail(db, skeleton), "Match rule removed")
