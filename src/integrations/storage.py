"""File storage behind a small interface: local disk today, S3 later.

Callers only use `get_storage()` and the FileStorage methods, so swapping the
implementation doesn't change them.
"""

import shutil
import uuid
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import UUID

from src.common.config import get_settings


class FileStorage(Protocol):
    def save(self, folder: str, original_name: str, content: bytes) -> str:
        """Stores the file and returns its storage key."""
        ...

    def remove(self, storage_key: str) -> None: ...

    def remove_folder(self, folder: str) -> None: ...

    def path_of(self, storage_key: str) -> Path | None:
        """A local path to stream the file from; None if it is missing."""
        ...


# Folder layout: company-<id>/journey-<id>/document-<id>/<uuid>.<ext>
def journey_folder(company_id: UUID, journey_id: UUID) -> str:
    return f"company-{company_id}/journey-{journey_id}"


def document_folder(company_id: UUID, journey_id: UUID, document_id: UUID) -> str:
    return f"{journey_folder(company_id, journey_id)}/document-{document_id}"


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def save(self, folder: str, original_name: str, content: bytes) -> str:
        # A random name avoids clashes and never trusts the uploaded file name
        storage_key = str(
            PurePosixPath(folder) / f"{uuid.uuid4()}{Path(original_name).suffix.lower()}"
        )
        path = self._resolve(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return storage_key

    def remove(self, storage_key: str) -> None:
        self._resolve(storage_key).unlink(missing_ok=True)

    def remove_folder(self, folder: str) -> None:
        shutil.rmtree(self._resolve(folder), ignore_errors=True)

    def path_of(self, storage_key: str) -> Path | None:
        path = self._resolve(storage_key)
        return path if path.is_file() else None

    def _resolve(self, storage_key: str) -> Path:
        """Guards against keys escaping the upload folder (e.g. "../../etc")."""
        path = (self.root / storage_key).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Invalid storage key")
        return path


@lru_cache
def get_storage() -> FileStorage:
    return LocalStorage(get_settings().upload_dir)
