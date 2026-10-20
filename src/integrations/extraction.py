"""Field extraction behind a small interface: a dummy today, an AI extractor later."""

from datetime import date, timedelta
from typing import Protocol

from src.document_skeletons.enums import FieldType
from src.documents.models import DocumentField, UploadedFile
from src.documents.service import ExtractedValue


class Extractor(Protocol):
    async def extract(
        self, fields: list[DocumentField], files: list[UploadedFile]
    ) -> list[ExtractedValue]: ...


_PARTIES = [
    "Acme Manufacturing Co",
    "Lone Star Freight LLC",
    "Northwind Distribution",
    "Blue Ridge Logistics",
    "Prairie Transport Inc",
    "Summit Retail DC",
]
_TEXTS = [
    "Palletized auto parts",
    "Dry van 53 ft",
    "Net 30",
    "Do not stack",
    "1200 W Industrial Dr, Dallas, TX",
    "Reefer at 34°F",
]
_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _fnv1a(text: str) -> int:
    """FNV-1a 32-bit hash: same input, same number (identical to the Node version)."""
    value = 0x811C9DC5
    for char in text:
        value ^= ord(char)
        value = (value * 0x01000193) & 0xFFFFFFFF
    return value


class DummyExtractor:
    """Placeholder until real (AI) extraction.

    Values come from the field name only, so the same field name gets the same value
    in every document — enough to exercise matching end to end.
    """

    async def extract(
        self, fields: list[DocumentField], files: list[UploadedFile]
    ) -> list[ExtractedValue]:
        results = []
        for field in fields:
            seed = _fnv1a(field.name.strip().lower())
            results.append(
                ExtractedValue(
                    document_field_id=field.id,
                    value=self._value_for(field.type, seed),
                    source_file_id=files[seed % len(files)].id if files else None,
                    confidence=85 + seed % 15,
                )
            )
        return results

    @staticmethod
    def _value_for(field_type: FieldType, seed: int) -> str:
        match field_type:
            case FieldType.CODE:
                prefix = "".join(_LETTERS[(seed >> (i * 5)) % 26] for i in range(4))
                return f"{prefix} {seed % 1_000_000:06d}-{seed % 10}"
            case FieldType.NUMBER:
                return str(1 + seed % 500)
            case FieldType.WEIGHT:
                return f"{1_000 + seed % 30_000:,} KG"
            case FieldType.CURRENCY:
                return f"USD {1_000 + seed % 90_000:,.2f}"
            case FieldType.DATE:
                day = date(2026, 1, 1) + timedelta(days=seed % 365)
                return f"{day.day:02d} {_MONTHS[day.month - 1]} {day.year}"
            case FieldType.PARTY:
                return _PARTIES[seed % len(_PARTIES)]
            case _:
                return _TEXTS[seed % len(_TEXTS)]
