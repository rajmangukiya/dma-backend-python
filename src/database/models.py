"""Registry of every table. Each module owns its tables; this file only imports them.

Importing this module registers all tables on Base.metadata — Alembic and the
test setup need that to see the whole schema.
"""

from src.companies.models import Company
from src.documents.models import (
    Document,
    DocumentField,
    DocumentFieldMatchRule,
    DocumentFieldValue,
    UploadedFile,
)
from src.journeys.models import Journey, Segment
from src.templates.models import (
    DocumentTemplate,
    DocumentTemplateField,
    DocumentTemplateFieldMatch,
)
from src.users.models import User

__all__ = [
    "Company",
    "Document",
    "DocumentField",
    "DocumentFieldMatchRule",
    "DocumentFieldValue",
    "DocumentTemplate",
    "DocumentTemplateField",
    "DocumentTemplateFieldMatch",
    "Journey",
    "Segment",
    "UploadedFile",
    "User",
]
