"""All table models. Importing this package registers every table on Base.metadata."""

from app.db.models.company import Company
from app.db.models.document import (
    Document,
    DocumentField,
    DocumentFieldMatchRule,
    DocumentFieldValue,
    UploadedFile,
)
from app.db.models.enums import DocumentStatus, FieldType, UserRole
from app.db.models.journey import Journey, Segment
from app.db.models.template import (
    DocumentTemplate,
    DocumentTemplateField,
    DocumentTemplateFieldMatch,
)
from app.db.models.user import User

__all__ = [
    "Company",
    "Document",
    "DocumentField",
    "DocumentFieldMatchRule",
    "DocumentFieldValue",
    "DocumentStatus",
    "DocumentTemplate",
    "DocumentTemplateField",
    "DocumentTemplateFieldMatch",
    "FieldType",
    "Journey",
    "Segment",
    "UploadedFile",
    "User",
    "UserRole",
]
