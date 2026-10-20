"""Documents: reads and writes. (Full API comes in steps 4-5; counts are used by admin.)"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.models import Document, UploadedFile


async def count_documents(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(Document)) or 0


async def count_files(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(UploadedFile)) or 0
