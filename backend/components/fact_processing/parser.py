from __future__ import annotations

import re

from langchain_core.documents import Document

from backend.components.fact_processing.models import ALLOWED_STATUS_VALUES, StructuredFact


TEST_SEQUENCE_PATTERN = re.compile(
    r"\b(?:(?P<sheet_id>[A-Za-z0-9]+)_)?(?P<test_number>\d{5})\.(?P<step_number>\d{3})\b"
)
BUG_NUMBER_PATTERN = re.compile(r"\bBUG(?:\s*NB)?\s*[:#-]?\s*(?P<bug_number>\d+)\b", re.IGNORECASE)


def parse_test_sequence_parts(raw_sequence: object) -> tuple[str | None, str | None, str | None, str | None]:
    sequence = _clean_text(raw_sequence)
    if not sequence:
        return None, None, None, None

    match = TEST_SEQUENCE_PATTERN.search(sequence)
    if not match:
        return None, None, None, sequence

    sheet_id = _clean_text(match.group("sheet_id"))
    test_number = _clean_text(match.group("test_number"))
    step_number = _clean_text(match.group("step_number"))
    normalized_sequence = f"{test_number}.{step_number}"

    if sheet_id:
        normalized_sequence = f"{sheet_id}_{normalized_sequence}"

    return sheet_id, test_number, step_number, normalized_sequence


def extract_bug_number(*values: object) -> str | None:
    for value in values:
        text = _clean_text(value)
        if not text:
            continue

        match = BUG_NUMBER_PATTERN.search(text)
        if match:
            return _clean_text(match.group("bug_number"))

    return None


def normalize_status(raw_status: object, fallback_text: object | None = None) -> str:
    candidates = [raw_status, fallback_text]

    for candidate in candidates:
        normalized = _clean_text(candidate)
        if not normalized:
            continue

        collapsed = " ".join(normalized.upper().split())
        if collapsed in ALLOWED_STATUS_VALUES:
            return collapsed

        if collapsed in {"NOK", "NOTOK"}:
            return "NOT OK"

    return "UNKNOWN"


def fact_from_document(document: Document) -> StructuredFact | None:
    metadata = document.metadata
    content = str(document.page_content or "")

    test_sequence = (
        _clean_text(metadata.get("test_sequence_number"))
        or _extract_labeled_value(content, "test sequence number", "test sequence", "sequence")
    )

    sheet_id, test_number, step_number, normalized_sequence = parse_test_sequence_parts(test_sequence)

    procedure = _clean_text(metadata.get("procedure")) or _extract_labeled_value(
        content,
        "procedure",
    )
    expected_result = _clean_text(metadata.get("expected_result")) or _extract_labeled_value(
        content,
        "expected result",
        "expected_result",
    )
    observed_result = _clean_text(metadata.get("observed_result")) or _extract_labeled_value(
        content,
        "observed result",
        "observed_result",
        "result observed",
    )

    raw_status = _clean_text(metadata.get("status")) or _extract_labeled_value(content, "status")
    conclusion = _clean_text(metadata.get("conclusion")) or _extract_labeled_value(content, "conclusion")
    status = normalize_status(raw_status, fallback_text=conclusion)

    bug_number = extract_bug_number(
        metadata.get("bug_number"),
        observed_result,
        conclusion,
        content,
    )

    if not _looks_like_test_fact(
        row_type=metadata.get("row_type"),
        test_sequence=normalized_sequence,
        test_number=test_number,
        step_number=step_number,
        procedure=procedure,
        expected_result=expected_result,
        observed_result=observed_result,
    ):
        return None

    row_index_raw = metadata.get("row_index")
    chunk_index_raw = metadata.get("chunk_index")

    return StructuredFact(
        sheet_id=sheet_id,
        test_number=test_number,
        step_number=step_number,
        test_sequence=normalized_sequence,
        procedure=procedure,
        expected_result=expected_result,
        observed_result=observed_result,
        status=status,
        bug_number=bug_number,
        source=_clean_text(metadata.get("source")),
        sheet_name=_clean_text(metadata.get("sheet_name")),
        row_index=_safe_int(row_index_raw),
        chunk_index=_safe_int(chunk_index_raw),
        row_type=_clean_text(metadata.get("row_type")),
    )


def _extract_labeled_value(content: str, *labels: str) -> str | None:
    if not content.strip() or not labels:
        return None

    wanted = {label.strip().casefold() for label in labels if label.strip()}
    if not wanted:
        return None

    for line in content.splitlines():
        if ":" not in line:
            continue

        raw_label, raw_value = line.split(":", 1)
        if raw_label.strip().casefold() in wanted:
            value = _clean_text(raw_value)
            if value:
                return value

    return None


def _looks_like_test_fact(
    row_type: object,
    test_sequence: str | None,
    test_number: str | None,
    step_number: str | None,
    procedure: str | None,
    expected_result: str | None,
    observed_result: str | None,
) -> bool:
    normalized_row_type = _clean_text(row_type)
    if normalized_row_type in {"test_step", "test_header"}:
        return True

    if test_sequence or (test_number and step_number):
        return True

    return bool(procedure or expected_result or observed_result)


def _clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
