"""Registry of every table. Each module owns its tables; this file only imports them.

Importing this module registers all tables on Base.metadata — Alembic and the
test setup need that to see the whole schema.
"""

from src.companies.models import Company
from src.document_skeletons.models import (
    DocumentSkeleton,
    DocumentSkeletonField,
    DocumentSkeletonFieldMatch,
)
from src.documents.models import (
    Document,
    DocumentField,
    DocumentFieldMatchRule,
    DocumentFieldValue,
    UploadedFile,
)
from src.journeys.models import Journey, Segment
from src.users.models import User

__all__ = [
    "Company",
    "Document",
    "DocumentField",
    "DocumentFieldMatchRule",
    "DocumentFieldValue",
    "DocumentSkeleton",
    "DocumentSkeletonField",
    "DocumentSkeletonFieldMatch",
    "Journey",
    "Segment",
    "UploadedFile",
    "User",
]
