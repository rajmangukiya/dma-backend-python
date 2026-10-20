"""Runs field extraction in the background, inside this process (Celery comes later).

Queuing a document marks it "extracting" and starts a background task after a
short delay. Queuing it again (e.g. another upload) cancels the earlier run; a
version number makes sure a stale run can never overwrite a newer result.
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import get_settings
from src.database.session import SessionLocal
from src.documents import service as documents
from src.documents.enums import DocumentStatus
from src.integrations.extraction import DummyExtractor, Extractor

logger = logging.getLogger(__name__)


class ExtractionRunner:
    def __init__(self, extractor: Extractor):
        self.extractor = extractor
        self.tasks: dict[UUID, asyncio.Task] = {}  # kept so tasks aren't garbage-collected
        self.versions: dict[UUID, int] = {}

    async def queue(self, db: AsyncSession, document_id: UUID) -> None:
        version = self.versions.get(document_id, 0) + 1
        self.versions[document_id] = version
        if previous := self.tasks.get(document_id):
            previous.cancel()

        document = await documents.get_document(db, document_id)
        if document:
            await documents.set_status(db, document, DocumentStatus.EXTRACTING)
        self.tasks[document_id] = asyncio.create_task(self._run(document_id, version))

    async def resume_interrupted(self) -> None:
        """Restarts documents left "extracting" when the server stopped."""
        async with SessionLocal() as db:
            for document in await documents.list_by_status(db, DocumentStatus.EXTRACTING):
                await self.queue(db, document.id)

    async def wait(self) -> None:
        """Waits for every queued run to finish (used by tests)."""
        while pending := [t for t in self.tasks.values() if not t.done()]:
            await asyncio.gather(*pending, return_exceptions=True)

    async def shutdown(self) -> None:
        for task in self.tasks.values():
            task.cancel()

    def _is_current(self, document_id: UUID, version: int) -> bool:
        return self.versions.get(document_id) == version

    async def _run(self, document_id: UUID, version: int) -> None:
        await asyncio.sleep(get_settings().extraction_delay_ms / 1000)
        # A background task outlives the request, so it opens its own session
        async with SessionLocal() as db:
            try:
                document = await documents.get_document(db, document_id)
                if not document or not self._is_current(document_id, version):
                    return

                files = await documents.list_files(db, document_id)
                if not files:
                    await documents.clear_extracted_values(db, document_id)
                    if self._is_current(document_id, version):
                        await documents.set_status(db, document, DocumentStatus.PENDING)
                    return

                fields = await documents.list_fields(db, document_id)
                extracted = await self.extractor.extract(fields, files)
                if not self._is_current(document_id, version):
                    return
                await documents.replace_extracted_values(db, document_id, extracted)
                if self._is_current(document_id, version):
                    await documents.set_status(db, document, DocumentStatus.READY)
            except Exception:
                logger.exception("Extraction failed for document %s", document_id)
                await db.rollback()
                if self._is_current(document_id, version) and (
                    document := await documents.get_document(db, document_id)
                ):
                    await documents.set_status(db, document, DocumentStatus.FAILED)
            finally:
                if self._is_current(document_id, version):
                    self.tasks.pop(document_id, None)


# One runner per process
extraction_runner = ExtractionRunner(DummyExtractor())
