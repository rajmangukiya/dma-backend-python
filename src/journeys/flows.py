"""Journey use cases that combine journeys with documents and matching."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.errors import AppError
from src.document_skeletons import service as skeletons
from src.documents import service as documents
from src.documents.matching import JourneyMatcher
from src.documents.schemas import DocumentCounts, DocumentSummary
from src.integrations.storage import document_folder, get_storage, journey_folder
from src.journeys import service as journeys
from src.journeys.models import Journey, Segment
from src.journeys.schemas import (
    JourneyDetail,
    JourneyListItem,
    JourneyRead,
    JourneyStats,
    JourneyStatus,
    SegmentWithDocuments,
)


def _status(segments: int, documents_total: int, uploaded: int) -> JourneyStatus:
    if not segments:
        return "draft"
    if documents_total and uploaded == documents_total:
        return "complete"
    return "in_progress"


async def list_journeys(db: AsyncSession, company_id: UUID) -> list[JourneyListItem]:
    rows = await journeys.list_journeys(db, company_id)
    ids = [j.id for j in rows]
    segment_counts = await journeys.count_segments(db, ids)
    document_counts = await documents.count_by_journey(db, ids)
    items = []
    for journey in rows:
        segments = segment_counts.get(journey.id, 0)
        total, uploaded = document_counts.get(journey.id, (0, 0))
        items.append(
            JourneyListItem(
                **JourneyRead.model_validate(journey).model_dump(),
                segment_count=segments,
                document_count=total,
                uploaded_count=uploaded,
                status=_status(segments, total, uploaded),
            )
        )
    return items


async def journey_detail(db: AsyncSession, journey: Journey) -> JourneyDetail:
    """The journey, its segments and every document's extraction/match summary."""
    segments = await journeys.list_segments(db, journey.id)
    graph = await documents.load_journey_graph(db, journey.id)
    matcher = JourneyMatcher(graph)

    summaries = []
    for document in graph.documents:
        counts = matcher.counts(document)
        summaries.append(
            DocumentSummary(
                id=document.id,
                segment_id=document.segment_id,
                document_skeleton_id=document.document_skeleton_id,
                title=document.title,
                document_type=document.document_type,
                status=document.status,
                file_count=sum(1 for f in graph.files if f.document_id == document.id),
                counts=DocumentCounts.model_validate(counts) if counts else None,
            )
        )
    counted = [s.counts for s in summaries if s.counts]

    return JourneyDetail(
        **JourneyRead.model_validate(journey).model_dump(),
        stats=JourneyStats(
            documents=len(summaries),
            uploaded=sum(1 for s in summaries if s.file_count),
            matched=sum(c.matched for c in counted),
            not_matched=sum(c.not_matched for c in counted),
        ),
        segments=[
            SegmentWithDocuments(
                id=segment.id,
                journey_id=segment.journey_id,
                name=segment.name,
                position=segment.position,
                created_at=segment.created_at,
                documents=[s for s in summaries if s.segment_id == segment.id],
            )
            for segment in segments
        ],
    )


async def delete_journey(db: AsyncSession, journey: Journey) -> None:
    await journeys.delete_journey(db, journey)
    get_storage().remove_folder(journey_folder(journey.company_id, journey.id))


async def delete_segment(db: AsyncSession, journey: Journey, segment: Segment) -> None:
    """Removes the segment, its documents and their files on disk."""
    removed = await documents.list_segment_documents(db, segment.id)
    await journeys.delete_segment(db, segment)
    for document in removed:
        get_storage().remove_folder(document_folder(journey.company_id, journey.id, document.id))


async def add_document(
    db: AsyncSession, journey: Journey, segment: Segment, document_skeleton_id: UUID
) -> None:
    """Places a skeleton in a segment (as a snapshot of its fields and match rules)."""
    skeleton = await skeletons.get_skeleton(db, document_skeleton_id, journey.company_id)
    if not skeleton:
        raise AppError.not_found("Skeleton not found")
    if await documents.exists_in_segment(db, segment.id, skeleton.id):
        raise AppError.conflict(f"{skeleton.title} is already in this segment")
    await documents.create_from_skeleton(db, journey.id, segment.id, skeleton)
