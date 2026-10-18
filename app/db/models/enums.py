from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SKELETON_DESIGNER = "skeleton_designer"
    OPERATIONS = "operations"
    VIEWER = "viewer"


class FieldType(StrEnum):
    TEXT = "text"
    CODE = "code"
    NUMBER = "number"
    WEIGHT = "weight"
    CURRENCY = "currency"
    DATE = "date"
    PARTY = "party"


class DocumentStatus(StrEnum):
    PENDING = "pending"  # no files uploaded yet
    EXTRACTING = "extracting"
    READY = "ready"
    FAILED = "failed"
