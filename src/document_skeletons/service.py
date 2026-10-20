"""Document skeletons: the skeleton itself, its fields and their one-way match rules."""

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.errors import AppError
from src.document_skeletons.enums import FieldType
from src.document_skeletons.models import (
    DocumentSkeleton,
    DocumentSkeletonField,
    DocumentSkeletonFieldMatch,
)
from src.document_skeletons.schemas import (
    CandidateField,
    FieldMatch,
    MatchCandidate,
    SkeletonDetail,
    SkeletonFieldDetail,
    SkeletonRead,
)

# --- Skeletons ---------------------------------------------------------------


async def get_skeleton(
    db: AsyncSession, document_skeleton_id: int, company_id: int
) -> DocumentSkeleton | None:
    skeleton = await db.get(DocumentSkeleton, document_skeleton_id)
    return skeleton if skeleton and skeleton.company_id == company_id else None


async def list_skeletons(db: AsyncSession, company_id: int) -> list[DocumentSkeleton]:
    result = await db.scalars(
        select(DocumentSkeleton)
        .where(DocumentSkeleton.company_id == company_id)
        .order_by(DocumentSkeleton.title)
    )
    return list(result)


async def get_skeletons(db: AsyncSession, skeleton_ids: list[int]) -> list[DocumentSkeleton]:
    if not skeleton_ids:
        return []
    result = await db.scalars(select(DocumentSkeleton).where(DocumentSkeleton.id.in_(skeleton_ids)))
    return list(result)


async def count_fields_and_rules(
    db: AsyncSession, skeleton_ids: list[int]
) -> tuple[dict[int, int], dict[int, int]]:
    """({document_skeleton_id: field count}, {document_skeleton_id: match rule count})."""
    if not skeleton_ids:
        return {}, {}
    fields = await db.execute(
        select(DocumentSkeletonField.document_skeleton_id, func.count())
        .where(DocumentSkeletonField.document_skeleton_id.in_(skeleton_ids))
        .group_by(DocumentSkeletonField.document_skeleton_id)
    )
    rules = await db.execute(
        select(DocumentSkeletonField.document_skeleton_id, func.count())
        .join(
            DocumentSkeletonFieldMatch,
            DocumentSkeletonFieldMatch.field_id == DocumentSkeletonField.id,
        )
        .where(DocumentSkeletonField.document_skeleton_id.in_(skeleton_ids))
        .group_by(DocumentSkeletonField.document_skeleton_id)
    )
    return dict(fields.all()), dict(rules.all())


async def create_skeleton(
    db: AsyncSession, company_id: int, title: str, document_type: str, description: str | None
) -> DocumentSkeleton:
    skeleton = DocumentSkeleton(
        company_id=company_id, title=title, document_type=document_type, description=description
    )
    db.add(skeleton)
    await db.commit()
    await db.refresh(skeleton)
    return skeleton


async def update_skeleton(
    db: AsyncSession, skeleton: DocumentSkeleton, changes: dict[str, Any]
) -> DocumentSkeleton:
    for field, value in changes.items():
        setattr(skeleton, field, value)
    await db.commit()
    await db.refresh(skeleton)  # updated_at is set by the database
    return skeleton


async def delete_skeleton(db: AsyncSession, skeleton: DocumentSkeleton) -> None:
    """Documents already placed in journeys keep their snapshot of the fields."""
    await db.delete(skeleton)
    await db.commit()


async def get_detail(db: AsyncSession, skeleton: DocumentSkeleton) -> SkeletonDetail:
    """The skeleton with its fields, each field's match rules and how many fields match it."""
    fields = await list_fields(db, [skeleton.id])
    field_ids = [f.id for f in fields]
    outgoing_rows = await list_rules_from(db, field_ids)
    incoming_rows = await _list_rules_to(db, field_ids)

    targets = {f.id: f for f in await get_fields(db, [m.match_field_id for m in outgoing_rows])}
    titles = {
        t.id: t.title
        for t in await get_skeletons(db, list({f.document_skeleton_id for f in targets.values()}))
    }

    return SkeletonDetail(
        **SkeletonRead.model_validate(skeleton).model_dump(),
        fields=[
            SkeletonFieldDetail(
                id=field.id,
                document_skeleton_id=field.document_skeleton_id,
                name=field.name,
                type=field.type,
                position=field.position,
                matches=[
                    FieldMatch(
                        field_id=target.id,
                        field_name=target.name,
                        document_skeleton_id=target.document_skeleton_id,
                        document_skeleton_title=titles.get(target.document_skeleton_id, ""),
                    )
                    for m in outgoing_rows
                    if m.field_id == field.id and (target := targets.get(m.match_field_id))
                ],
                incoming_count=sum(1 for m in incoming_rows if m.match_field_id == field.id),
            )
            for field in fields
        ],
    )


async def match_candidates(db: AsyncSession, skeleton: DocumentSkeleton) -> list[MatchCandidate]:
    """Every other skeleton of the company, with its fields."""
    others = [t for t in await list_skeletons(db, skeleton.company_id) if t.id != skeleton.id]
    fields = await list_fields(db, [t.id for t in others])
    return [
        MatchCandidate(
            id=other.id,
            title=other.title,
            document_type=other.document_type,
            fields=[
                CandidateField(id=f.id, name=f.name, type=f.type)
                for f in fields
                if f.document_skeleton_id == other.id
            ],
        )
        for other in others
    ]


# --- Fields ------------------------------------------------------------------


async def list_fields(db: AsyncSession, skeleton_ids: list[int]) -> list[DocumentSkeletonField]:
    if not skeleton_ids:
        return []
    result = await db.scalars(
        select(DocumentSkeletonField)
        .where(DocumentSkeletonField.document_skeleton_id.in_(skeleton_ids))
        .order_by(DocumentSkeletonField.position, DocumentSkeletonField.id)
    )
    return list(result)


async def get_fields(db: AsyncSession, field_ids: list[int]) -> list[DocumentSkeletonField]:
    if not field_ids:
        return []
    result = await db.scalars(
        select(DocumentSkeletonField).where(DocumentSkeletonField.id.in_(field_ids))
    )
    return list(result)


async def get_field(
    db: AsyncSession, document_skeleton_id: int, field_id: int
) -> DocumentSkeletonField | None:
    field = await db.get(DocumentSkeletonField, field_id)
    return field if field and field.document_skeleton_id == document_skeleton_id else None


async def _ensure_field_name_free(
    db: AsyncSession, document_skeleton_id: int, name: str, except_id: int | None = None
) -> None:
    """Field names are unique per skeleton, ignoring case."""
    existing = await db.scalar(
        select(DocumentSkeletonField).where(
            DocumentSkeletonField.document_skeleton_id == document_skeleton_id,
            func.lower(DocumentSkeletonField.name) == name.strip().lower(),
        )
    )
    if existing and existing.id != except_id:
        raise AppError.conflict(
            f"“{name}” already exists on this skeleton",
            AppError.field("name", "A field with this name already exists"),
        )


async def create_field(
    db: AsyncSession, document_skeleton_id: int, name: str, field_type: FieldType
) -> DocumentSkeletonField:
    await _ensure_field_name_free(db, document_skeleton_id, name)
    last = await db.scalar(
        select(func.max(DocumentSkeletonField.position)).where(
            DocumentSkeletonField.document_skeleton_id == document_skeleton_id
        )
    )
    field = DocumentSkeletonField(
        document_skeleton_id=document_skeleton_id,
        name=name,
        type=field_type,
        position=0 if last is None else last + 1,  # new fields go last
    )
    db.add(field)
    await db.commit()
    return field


async def update_field(
    db: AsyncSession, field: DocumentSkeletonField, changes: dict[str, Any]
) -> DocumentSkeletonField:
    if "name" in changes:
        await _ensure_field_name_free(
            db, field.document_skeleton_id, changes["name"], except_id=field.id
        )
    for key, value in changes.items():
        setattr(field, key, value)
    await db.commit()
    return field


async def delete_field(db: AsyncSession, field: DocumentSkeletonField) -> None:
    """Its match rules (both directions) are removed by the database (ON DELETE CASCADE)."""
    await db.delete(field)
    await db.commit()


# --- Match rules -------------------------------------------------------------


async def list_rules_from(
    db: AsyncSession, field_ids: list[int]
) -> list[DocumentSkeletonFieldMatch]:
    """The match rules owned by these fields."""
    if not field_ids:
        return []
    result = await db.scalars(
        select(DocumentSkeletonFieldMatch).where(DocumentSkeletonFieldMatch.field_id.in_(field_ids))
    )
    return list(result)


async def _list_rules_to(
    db: AsyncSession, field_ids: list[int]
) -> list[DocumentSkeletonFieldMatch]:
    """The match rules on other fields that point at these fields."""
    if not field_ids:
        return []
    result = await db.scalars(
        select(DocumentSkeletonFieldMatch).where(
            DocumentSkeletonFieldMatch.match_field_id.in_(field_ids)
        )
    )
    return list(result)


async def add_match(
    db: AsyncSession, field: DocumentSkeletonField, match_field_id: int, company_id: int
) -> None:
    """`field` must match `match_field_id`, a field on another skeleton of the same company."""
    target = await db.get(DocumentSkeletonField, match_field_id)
    if not target or not await get_skeleton(db, target.document_skeleton_id, company_id):
        raise AppError.not_found("Field to match with not found")
    if target.document_skeleton_id == field.document_skeleton_id:
        raise AppError.bad_request("A field can only match fields on other skeletons")
    if await db.get(DocumentSkeletonFieldMatch, (field.id, match_field_id)):
        raise AppError.conflict("This match rule already exists")

    db.add(DocumentSkeletonFieldMatch(field_id=field.id, match_field_id=match_field_id))
    await db.commit()


async def remove_match(db: AsyncSession, field: DocumentSkeletonField, match_field_id: int) -> None:
    result = await db.execute(
        delete(DocumentSkeletonFieldMatch).where(
            DocumentSkeletonFieldMatch.field_id == field.id,
            DocumentSkeletonFieldMatch.match_field_id == match_field_id,
        )
    )
    if not result.rowcount:
        raise AppError.not_found("Match rule not found")
    await db.commit()
