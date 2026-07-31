"""Domain models describing normalized facts and traceability relationships."""

from __future__ import annotations

from dataclasses import dataclass


ALLOWED_STATUS_VALUES = {
    "OK",
    "NOT OK",
    "IMPOSSIBLE TO ACHIEVE",
    "WRITING ERROR",
    "UNKNOWN",
}


@dataclass(frozen=True)
class StructuredFact:
    """Normalized representation of one test-step fact extracted from context."""

    sheet_id: str | None
    test_number: str | None
    step_number: str | None
    test_sequence: str | None
    procedure: str | None
    expected_result: str | None
    observed_result: str | None
    status: str
    bug_number: str | None
    source: str | None = None
    sheet_name: str | None = None
    row_index: int | None = None
    chunk_index: int | None = None
    row_type: str | None = None

    def to_public_dict(self) -> dict[str, str | None]:
        """Serializes fact fields exposed to LLM context payload.

        Returns:
            Dictionary with selected public fields.
        """
        return {
            "sheet_id": self.sheet_id,
            "test_number": self.test_number,
            "step_number": self.step_number,
            "test_sequence": self.test_sequence,
            "procedure": self.procedure,
            "expected_result": self.expected_result,
            "observed_result": self.observed_result,
            "status": self.status,
            "bug_number": self.bug_number,
        }


@dataclass(frozen=True)
class FactRef:
    """Reference to a fact position used in relationship maps."""

    fact_index: int
    bug_number: str | None
    test_number: str | None
    step_number: str | None
    test_sequence: str | None
    sheet_id: str | None
    source: str | None
    sheet_name: str | None
    row_index: int | None
    chunk_index: int | None

    def to_dict(self) -> dict[str, str | int | None]:
        """Serializes reference metadata for JSON relationship payloads.

        Returns:
            Dictionary representation of this reference.
        """
        return {
            "fact_index": self.fact_index,
            "bug_number": self.bug_number,
            "test_number": self.test_number,
            "step_number": self.step_number,
            "test_sequence": self.test_sequence,
            "sheet_id": self.sheet_id,
            "source": self.source,
            "sheet_name": self.sheet_name,
            "row_index": self.row_index,
            "chunk_index": self.chunk_index,
        }


@dataclass(frozen=True)
class FactRelationships:
    """Indexes connecting bugs, tests, and sequences to fact references."""

    bug_to_steps: dict[str, list[FactRef]]
    test_to_steps: dict[str, list[FactRef]]
    sequence_to_fact: dict[str, FactRef]


@dataclass(frozen=True)
class FactPreparationResult:
    """Container with extracted facts and their computed relationships."""

    facts: list[StructuredFact]
    relationships: FactRelationships
