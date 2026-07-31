"""Query analysis helpers used to infer retrieval intent and filters."""

from dataclasses import dataclass
from typing import Any

from backend.components.RetrieverService.constants import (
    AFFECTED_TEST_HINTS,
    BUG_LOCATION_HINTS,
    BUG_NUMBER_PATTERN,
    ERROR_KEYWORDS,
    LIST_BUGS_HINTS,
    TEST_NUMBER_PATTERN,
    TEST_SEQUENCE_PATTERN,
    TEST_STEPS_HINTS,
)


@dataclass(frozen=True)
class QueryFeatures:
    """Structured query signals used by retrieval and reranking."""

    has_hint: bool
    query_lower: str
    full_sequence: str | None
    test_number: str | None
    step_number: str | None
    bug_numbers: tuple[str, ...]
    intent: str
    keywords: tuple[str, ...]


def extract_query_features(query: str) -> QueryFeatures:
    """Extracts intent and searchable signals from user query text.

    Args:
        query: Raw user query.

    Returns:
        Parsed query feature set consumed by retriever modules.
    """
    query_lower = query.lower()

    sequence_match = TEST_SEQUENCE_PATTERN.search(query)
    full_sequence = None
    test_number = None
    step_number = None

    if sequence_match:
        full_sequence = sequence_match.group(0)
        test_number = sequence_match.group("test_number")
        step_number = sequence_match.group("step_number")
    else:
        test_number_match = TEST_NUMBER_PATTERN.search(query)
        if test_number_match:
            test_number = test_number_match.group("test_number")

    bug_numbers = tuple(_extract_bug_numbers(query))
    keywords = tuple(keyword for keyword in ERROR_KEYWORDS if keyword in query_lower)
    intent = _detect_intent(
        query_lower=query_lower,
        bug_numbers=bug_numbers,
        test_number=test_number,
        step_number=step_number,
    )
    has_hint = bool(test_number or step_number or bug_numbers or keywords or intent != "GENERAL_QA")

    return QueryFeatures(
        has_hint=has_hint,
        query_lower=query_lower,
        full_sequence=full_sequence,
        test_number=test_number,
        step_number=step_number,
        bug_numbers=bug_numbers,
        intent=intent,
        keywords=keywords,
    )


def build_metadata_filter(query_features: QueryFeatures) -> dict[str, Any] | None:
    """Builds metadata filter constraints from extracted query features.

    Args:
        query_features: Parsed query feature set.

    Returns:
        Chroma metadata filter or None when no constraints are applicable.
    """
    test_number = str(query_features.test_number or "").strip()
    step_number = str(query_features.step_number or "").strip()

    if test_number and step_number:
        return {
            "$and": [
                {"test_number": test_number},
                {"step_number": step_number},
            ]
        }

    if query_features.bug_numbers:
        return {"bug_number": query_features.bug_numbers[0]}

    if test_number:
        return {"test_number": test_number}

    return None


def build_sparse_terms(query_features: QueryFeatures) -> list[str]:
    """Builds keyword terms used by sparse matching fallback.

    Args:
        query_features: Parsed query feature set.

    Returns:
        Deduplicated list of normalized search terms.
    """
    terms: list[str] = []
    full_sequence = str(query_features.full_sequence or "").strip().lower()
    test_number = str(query_features.test_number or "").strip().lower()
    step_number = str(query_features.step_number or "").strip().lower()

    if full_sequence:
        terms.append(full_sequence)
    if test_number:
        terms.append(test_number)
    if step_number:
        terms.append(step_number)

    for keyword in query_features.keywords:
        normalized = str(keyword).strip().lower()
        if normalized:
            terms.append(normalized)

    for bug_number in query_features.bug_numbers:
        normalized_bug = str(bug_number).strip().lower()
        if normalized_bug:
            terms.append(normalized_bug)
            terms.append(f"bug {normalized_bug}")
            terms.append(f"bug nb {normalized_bug}")

    unique_terms: list[str] = []
    seen: set[str] = set()

    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        unique_terms.append(term)

    return unique_terms


def _extract_bug_numbers(query: str) -> list[str]:
    numbers: list[str] = []
    seen: set[str] = set()

    for match in BUG_NUMBER_PATTERN.finditer(query):
        bug_number = str(match.group("bug_number") or "").strip()
        if not bug_number or bug_number in seen:
            continue
        seen.add(bug_number)
        numbers.append(bug_number)

    return numbers


def _detect_intent(
    query_lower: str,
    bug_numbers: tuple[str, ...],
    test_number: str | None,
    step_number: str | None,
) -> str:
    if _contains_any(query_lower, LIST_BUGS_HINTS):
        return "LIST_BUGS"

    if _contains_any(query_lower, AFFECTED_TEST_HINTS):
        return "AFFECTED_TEST_FULL"

    if _contains_any(query_lower, TEST_STEPS_HINTS):
        return "TEST_STEPS"

    if _contains_any(query_lower, BUG_LOCATION_HINTS):
        return "BUG_LOCATION"

    if bug_numbers and ("test" in query_lower or "step" in query_lower or "krok" in query_lower):
        return "BUG_LOCATION"

    if bug_numbers and ("all" in query_lower or "wszystkie" in query_lower):
        return "LIST_BUGS"

    if bug_numbers and ("pelny" in query_lower or "complete" in query_lower or "full" in query_lower):
        return "AFFECTED_TEST_FULL"

    if test_number and step_number:
        return "TEST_STEPS"

    if test_number and ("krok" in query_lower or "step" in query_lower):
        return "TEST_STEPS"

    return "GENERAL_QA"


def _contains_any(value: str, hints: tuple[str, ...]) -> bool:
    return any(hint in value for hint in hints)
