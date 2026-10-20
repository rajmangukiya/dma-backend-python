"""One-way field matching across the documents of a journey.

Pure logic: takes an already-loaded JourneyGraph, returns results. No database, no HTTP.
Phase one compares values ignoring whitespace and case.
"""

import re
from dataclasses import dataclass
from typing import Literal

from src.document_skeletons.enums import FieldType
from src.documents.enums import DocumentStatus
from src.documents.models import Document, DocumentField, DocumentFieldMatchRule
from src.documents.service import JourneyGraph

FieldResult = Literal["not_extracted", "no_rule", "matched", "not_matched", "waiting"]
CheckStatus = Literal[
    "absent",  # no document from the target skeleton in this journey
    "awaiting_upload",
    "extracting",
    "no_value",  # the target document has no value for the field
    "self_missing",  # this document has no value to compare
    "matched",
    "not_matched",
]


@dataclass
class MatchCheck:
    target_document_skeleton_title: str
    target_field_name: str
    target_document_id: int | None
    target_document_title: str | None
    target_segment_id: int | None
    value: str | None
    status: CheckStatus


@dataclass
class FieldRow:
    id: int
    name: str
    type: FieldType
    value: str | None
    is_manual: bool
    confidence: int | None
    source_file_id: int | None
    result: FieldResult
    checks: list[MatchCheck]


@dataclass
class DocumentCounts:
    total: int
    extracted: int
    not_extracted: int
    matched: int
    not_matched: int


def normalize(value: str) -> str:
    """ "MRKU 284119-3" and "mrku284119-3" are the same value."""
    return re.sub(r"\s+", "", value).lower()


class JourneyMatcher:
    def __init__(self, graph: JourneyGraph):
        self.graph = graph
        self.fields_by_doc: dict[int, list[DocumentField]] = {}
        for field in graph.fields:
            self.fields_by_doc.setdefault(field.document_id, []).append(field)
        self.rules_by_field: dict[int, list[DocumentFieldMatchRule]] = {}
        for rule in graph.rules:
            self.rules_by_field.setdefault(rule.document_field_id, []).append(rule)
        self.value_by_field = {v.document_field_id: v for v in graph.values}

    def rows(self, document: Document) -> list[FieldRow]:
        rows = []
        for field in self.fields_by_doc.get(document.id, []):
            stored = self.value_by_field.get(field.id)
            value = self._value_of(document, field)
            checks = [
                check
                for rule in self.rules_by_field.get(field.id, [])
                for check in self._checks_for(document, value, rule)
            ]
            rows.append(
                FieldRow(
                    id=field.id,
                    name=field.name,
                    type=field.type,
                    value=value,
                    is_manual=bool(stored and stored.is_manual and value is not None),
                    confidence=stored.confidence if stored and value is not None else None,
                    source_file_id=stored.source_file_id if stored and value is not None else None,
                    result=self._result_of(value, checks),
                    checks=checks,
                )
            )
        return rows

    def counts(self, document: Document) -> DocumentCounts | None:
        """None until the document's files have been extracted."""
        if document.status != DocumentStatus.READY:
            return None
        rows = self.rows(document)
        return DocumentCounts(
            total=len(rows),
            extracted=sum(r.value is not None for r in rows),
            not_extracted=sum(r.value is None for r in rows),
            matched=sum(r.result == "matched" for r in rows),
            not_matched=sum(r.result == "not_matched" for r in rows),
        )

    def _value_of(self, document: Document, field: DocumentField) -> str | None:
        if document.status != DocumentStatus.READY:
            return None
        stored = self.value_by_field.get(field.id)
        value = (stored.value or "").strip() if stored else ""
        return value or None

    def _checks_for(
        self, document: Document, value: str | None, rule: DocumentFieldMatchRule
    ) -> list[MatchCheck]:
        targets = (
            []
            if rule.target_document_skeleton_id is None
            else [
                d
                for d in self.graph.documents
                if d.id != document.id
                and d.document_skeleton_id == rule.target_document_skeleton_id
            ]
        )
        if not targets:
            return [
                MatchCheck(
                    target_document_skeleton_title=rule.target_document_skeleton_title,
                    target_field_name=rule.target_field_name,
                    target_document_id=None,
                    target_document_title=None,
                    target_segment_id=None,
                    value=None,
                    status="absent",
                )
            ]

        checks = []
        for target in targets:
            target_field = next(
                (
                    f
                    for f in self.fields_by_doc.get(target.id, [])
                    if f.name == rule.target_field_name
                ),
                None,
            )
            target_value = self._value_of(target, target_field) if target_field else None
            checks.append(
                MatchCheck(
                    target_document_skeleton_title=rule.target_document_skeleton_title,
                    target_field_name=rule.target_field_name,
                    target_document_id=target.id,
                    target_document_title=target.title,
                    target_segment_id=target.segment_id,
                    value=target_value,
                    status=self._check_status(target, value, target_value),
                )
            )
        return checks

    @staticmethod
    def _check_status(target: Document, value: str | None, target_value: str | None) -> CheckStatus:
        if target.status == DocumentStatus.PENDING:
            return "awaiting_upload"
        if target.status == DocumentStatus.EXTRACTING:
            return "extracting"
        if target_value is None:
            return "no_value"
        if value is None:
            return "self_missing"
        return "matched" if normalize(value) == normalize(target_value) else "not_matched"

    @staticmethod
    def _result_of(value: str | None, checks: list[MatchCheck]) -> FieldResult:
        if value is None:
            return "not_extracted"
        if not checks:
            return "no_rule"
        if any(c.status == "not_matched" for c in checks):
            return "not_matched"
        if all(c.status == "matched" for c in checks):
            return "matched"
        return "waiting"
