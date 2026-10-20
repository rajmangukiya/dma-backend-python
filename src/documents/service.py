"""Documents placed in journeys: their field snapshots, values and uploaded files."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.document_skeletons import service as skeletons
from src.document_skeletons.models import DocumentSkeleton
from src.documents.enums import DocumentStatus
from src.documents.models import (
    Document,
    DocumentField,
    DocumentFieldMatchRule,
    DocumentFieldValue,
    UploadedFile,
)


@dataclass
class JourneyGraph:
    """Everything needed to compute extraction and match results for one journey."""

    documents: list[Document]
    fields: list[DocumentField]
    rules: list[DocumentFieldMatchRule]
    values: list[DocumentFieldValue]
    files: list[UploadedFile]


@dataclass
class ExtractedValue:
    document_field_id: UUID
    value: str | None
    source_file_id: UUID | None
    confidence: int | None


# --- Documents ---------------------------------------------------------------


async def get_document(db: AsyncSession, document_id: UUID) -> Document | None:
    """Not scoped to a company: callers check the document's journey belongs to theirs."""
    return await db.get(Document, document_id)


async def list_by_status(db: AsyncSession, status: DocumentStatus) -> list[Document]:
    return list(await db.scalars(select(Document).where(Document.status == status)))


async def list_segment_documents(db: AsyncSession, segment_id: UUID) -> list[Document]:
    return list(await db.scalars(select(Document).where(Document.segment_id == segment_id)))


async def exists_in_segment(db: AsyncSession, segment_id: UUID, document_skeleton_id: UUID) -> bool:
    count = await db.scalar(
        select(func.count())
        .select_from(Document)
        .where(
            Document.segment_id == segment_id, Document.document_skeleton_id == document_skeleton_id
        )
    )
    return bool(count)


async def create_from_skeleton(
    db: AsyncSession, journey_id: UUID, segment_id: UUID, skeleton: DocumentSkeleton
) -> Document:
    """Places a skeleton in a segment.

    Copies the skeleton's fields and match rules onto the new document, so later
    edits to the skeleton don't change documents already in journeys.
    """
    fields = await skeletons.list_fields(db, [skeleton.id])
    rules = await skeletons.list_rules_from(db, [f.id for f in fields])
    targets = {f.id: f for f in await skeletons.get_fields(db, [r.match_field_id for r in rules])}
    owners = {
        t.id: t
        for t in await skeletons.get_skeletons(
            db, list({f.document_skeleton_id for f in targets.values()})
        )
    }

    last = await db.scalar(
        select(func.max(Document.position)).where(Document.segment_id == segment_id)
    )
    document = Document(
        journey_id=journey_id,
        segment_id=segment_id,
        document_skeleton_id=skeleton.id,
        title=skeleton.title,
        document_type=skeleton.document_type,
        position=0 if last is None else last + 1,
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    await db.flush()  # INSERT now so document.id exists; committed below with everything else

    for field in fields:
        doc_field = DocumentField(
            document_id=document.id,
            document_skeleton_field_id=field.id,
            name=field.name,
            type=field.type,
            position=field.position,
        )
        db.add(doc_field)
        await db.flush()
        for rule in rules:
            target = targets.get(rule.match_field_id)
            owner = target and owners.get(target.document_skeleton_id)
            if rule.field_id == field.id and target and owner:
                db.add(
                    DocumentFieldMatchRule(
                        document_field_id=doc_field.id,
                        target_document_skeleton_id=owner.id,
                        target_document_skeleton_title=owner.title,
                        target_field_name=target.name,
                    )
                )

    await db.commit()  # one transaction: the document is created with all its fields or not at all
    await db.refresh(document)
    return document


async def set_status(db: AsyncSession, document: Document, status: DocumentStatus) -> None:
    document.status = status
    await db.commit()


async def delete_document(db: AsyncSession, document: Document) -> None:
    """Fields, values and file rows go with it (ON DELETE CASCADE); files on disk are separate."""
    await db.delete(document)
    await db.commit()


async def count_by_journey(
    db: AsyncSession, journey_ids: list[UUID]
) -> dict[UUID, tuple[int, int]]:
    """{journey_id: (documents, documents with at least one file)}."""
    if not journey_ids:
        return {}
    has_file = select(UploadedFile.id).where(UploadedFile.document_id == Document.id).exists()
    result = await db.execute(
        select(
            Document.journey_id,
            func.count(),
            func.count().filter(has_file),
        )
        .where(Document.journey_id.in_(journey_ids))
        .group_by(Document.journey_id)
    )
    return {journey_id: (total, uploaded) for journey_id, total, uploaded in result.all()}


async def journey_count_by_skeleton(db: AsyncSession, skeleton_ids: list[UUID]) -> dict[UUID, int]:
    """{document_skeleton_id: number of journeys using it}."""
    if not skeleton_ids:
        return {}
    result = await db.execute(
        select(Document.document_skeleton_id, func.count(func.distinct(Document.journey_id)))
        .where(Document.document_skeleton_id.in_(skeleton_ids))
        .group_by(Document.document_skeleton_id)
    )
    return dict(result.all())


async def count_documents(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(Document)) or 0


async def count_files(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(UploadedFile)) or 0


async def load_journey_graph(db: AsyncSession, journey_id: UUID) -> JourneyGraph:
    documents = list(
        await db.scalars(
            select(Document)
            .where(Document.journey_id == journey_id)
            .order_by(Document.position, Document.id)
        )
    )
    document_ids = [d.id for d in documents]
    if not document_ids:
        return JourneyGraph(documents, [], [], [], [])

    fields = list(
        await db.scalars(
            select(DocumentField)
            .where(DocumentField.document_id.in_(document_ids))
            .order_by(DocumentField.position, DocumentField.id)
        )
    )
    files = list(
        await db.scalars(
            select(UploadedFile)
            .where(UploadedFile.document_id.in_(document_ids))
            .order_by(UploadedFile.created_at, UploadedFile.id)
        )
    )
    field_ids = [f.id for f in fields]
    rules = list(
        await db.scalars(
            select(DocumentFieldMatchRule)
            .where(DocumentFieldMatchRule.document_field_id.in_(field_ids))
            .order_by(DocumentFieldMatchRule.id)
        )
    )
    values = list(
        await db.scalars(
            select(DocumentFieldValue).where(DocumentFieldValue.document_field_id.in_(field_ids))
        )
    )
    return JourneyGraph(documents, fields, rules, values, files)


# --- Fields and values -------------------------------------------------------


async def list_fields(db: AsyncSession, document_id: UUID) -> list[DocumentField]:
    return list(
        await db.scalars(
            select(DocumentField)
            .where(DocumentField.document_id == document_id)
            .order_by(DocumentField.position, DocumentField.id)
        )
    )


async def get_field(db: AsyncSession, document_id: UUID, field_id: UUID) -> DocumentField | None:
    field = await db.get(DocumentField, field_id)
    return field if field and field.document_id == document_id else None


async def replace_extracted_values(
    db: AsyncSession, document_id: UUID, extracted: list[ExtractedValue]
) -> None:
    """Swaps in a new set of extracted values. Values entered by hand are kept."""
    field_ids = [f.id for f in await list_fields(db, document_id)]
    if not field_ids:
        return
    manual_ids = set(
        await db.scalars(
            select(DocumentFieldValue.document_field_id).where(
                DocumentFieldValue.document_field_id.in_(field_ids), DocumentFieldValue.is_manual
            )
        )
    )
    await db.execute(
        delete(DocumentFieldValue).where(
            DocumentFieldValue.document_field_id.in_(field_ids), ~DocumentFieldValue.is_manual
        )
    )
    db.add_all(
        DocumentFieldValue(
            document_field_id=e.document_field_id,
            value=e.value,
            source_file_id=e.source_file_id,
            confidence=e.confidence,
            is_manual=False,
        )
        for e in extracted
        if e.document_field_id in field_ids and e.document_field_id not in manual_ids
    )
    await db.commit()


async def clear_extracted_values(db: AsyncSession, document_id: UUID) -> None:
    field_ids = [f.id for f in await list_fields(db, document_id)]
    if field_ids:
        await db.execute(
            delete(DocumentFieldValue).where(
                DocumentFieldValue.document_field_id.in_(field_ids), ~DocumentFieldValue.is_manual
            )
        )
        await db.commit()


async def set_manual_value(db: AsyncSession, field: DocumentField, value: str) -> None:
    """Insert or overwrite the field's value (one value row per field)."""
    statement = insert(DocumentFieldValue).values(
        document_field_id=field.id,
        value=value,
        is_manual=True,
        confidence=None,
        source_file_id=None,
    )
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[DocumentFieldValue.document_field_id],
            set_={"value": value, "is_manual": True, "confidence": None, "source_file_id": None},
        )
    )
    await db.commit()


async def clear_manual_value(db: AsyncSession, field: DocumentField) -> None:
    await db.execute(
        delete(DocumentFieldValue).where(
            DocumentFieldValue.document_field_id == field.id, DocumentFieldValue.is_manual
        )
    )
    await db.commit()


# --- Uploaded files ----------------------------------------------------------


async def list_files(db: AsyncSession, document_id: UUID) -> list[UploadedFile]:
    return list(
        await db.scalars(
            select(UploadedFile)
            .where(UploadedFile.document_id == document_id)
            .order_by(UploadedFile.created_at, UploadedFile.id)
        )
    )


async def get_file(db: AsyncSession, document_id: UUID, file_id: UUID) -> UploadedFile | None:
    file = await db.get(UploadedFile, file_id)
    return file if file and file.document_id == document_id else None


async def add_files(db: AsyncSession, files: list[UploadedFile]) -> None:
    db.add_all(files)
    await db.commit()


async def delete_file(db: AsyncSession, file: UploadedFile) -> None:
    await db.delete(file)
    await db.commit()
