from fastapi import APIRouter, Depends, status

from src.auth.dependencies import CurrentCompanyId, require
from src.auth.permissions import Permission
from src.common.errors import AppError
from src.common.schemas import ApiResponse, ok
from src.database.session import DbSession
from src.journeys import flows, service
from src.journeys.models import Journey, Segment
from src.journeys.schemas import (
    AddDocumentRequest,
    CreateJourneyRequest,
    JourneyDetail,
    JourneyListItem,
    SegmentNameRequest,
    UpdateJourneyRequest,
)

router = APIRouter(prefix="/journeys", tags=["journeys"])
# Segments have their own URLs (/segments/{id}) but belong to this module
segments_router = APIRouter(
    prefix="/segments",
    tags=["journeys"],
    dependencies=[Depends(require(Permission.MANAGE_JOURNEYS))],
)

can_view = [Depends(require(Permission.VIEW_JOURNEYS))]
can_manage = [Depends(require(Permission.MANAGE_JOURNEYS))]


async def load_journey(db: DbSession, company_id: int, journey_id: int) -> Journey:
    journey = await service.get_journey(db, journey_id, company_id)
    if not journey:
        raise AppError.not_found("Journey not found")
    return journey


async def _load_segment(db: DbSession, company_id: int, segment_id: int) -> tuple[Segment, Journey]:
    segment = await service.get_segment(db, segment_id, company_id)
    if not segment:
        raise AppError.not_found("Segment not found")
    return segment, await load_journey(db, company_id, segment.journey_id)


# --- /journeys ---------------------------------------------------------------


@router.get("", dependencies=can_view)
async def list_journeys(
    db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[list[JourneyListItem]]:
    return ok(await flows.list_journeys(db, company_id))


@router.post("", dependencies=can_manage, status_code=status.HTTP_201_CREATED)
async def create_journey(
    body: CreateJourneyRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[JourneyDetail]:
    journey = await service.create_journey(db, company_id, body.title, body.description)
    return ok(await flows.journey_detail(db, journey), "Journey created")


@router.get("/{journey_id}", dependencies=can_view)
async def get_journey(
    journey_id: int, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[JourneyDetail]:
    journey = await load_journey(db, company_id, journey_id)
    return ok(await flows.journey_detail(db, journey))


@router.patch("/{journey_id}", dependencies=can_manage)
async def update_journey(
    journey_id: int, body: UpdateJourneyRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[JourneyDetail]:
    journey = await load_journey(db, company_id, journey_id)
    journey = await service.update_journey(db, journey, body.changes())
    return ok(await flows.journey_detail(db, journey), "Journey updated")


@router.delete("/{journey_id}", dependencies=can_manage)
async def delete_journey(
    journey_id: int, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[None]:
    journey = await load_journey(db, company_id, journey_id)
    await flows.delete_journey(db, journey)
    return ok(None, "Journey deleted")


@router.post("/{journey_id}/segments", dependencies=can_manage, status_code=status.HTTP_201_CREATED)
async def add_segment(
    journey_id: int, body: SegmentNameRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[JourneyDetail]:
    journey = await load_journey(db, company_id, journey_id)
    await service.create_segment(db, journey.id, body.name)
    return ok(await flows.journey_detail(db, journey), "Segment added")


# --- /segments ---------------------------------------------------------------


@segments_router.patch("/{segment_id}")
async def rename_segment(
    segment_id: int, body: SegmentNameRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[JourneyDetail]:
    segment, journey = await _load_segment(db, company_id, segment_id)
    await service.rename_segment(db, segment, body.name)
    return ok(await flows.journey_detail(db, journey), "Segment renamed")


# Also removes the segment's documents and their uploaded files
@segments_router.delete("/{segment_id}")
async def delete_segment(
    segment_id: int, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[JourneyDetail]:
    segment, journey = await _load_segment(db, company_id, segment_id)
    await flows.delete_segment(db, journey, segment)
    return ok(await flows.journey_detail(db, journey), "Segment removed")


@segments_router.post("/{segment_id}/documents", status_code=status.HTTP_201_CREATED)
async def add_document(
    segment_id: int, body: AddDocumentRequest, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[JourneyDetail]:
    segment, journey = await _load_segment(db, company_id, segment_id)
    await flows.add_document(db, journey, segment, body.document_skeleton_id)
    return ok(await flows.journey_detail(db, journey), "Document added")
