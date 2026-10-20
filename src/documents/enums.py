from enum import StrEnum


class DocumentStatus(StrEnum):
    PENDING = "pending"  # no files uploaded yet
    EXTRACTING = "extracting"
    READY = "ready"
    FAILED = "failed"
