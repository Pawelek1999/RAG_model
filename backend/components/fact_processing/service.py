"""Fact preparation workflow used to build structured and hybrid RAG context."""

from __future__ import annotations

import json
from dataclasses import dataclass

from langchain_core.documents import Document

from backend.components.RetrieverService.query_features import QueryFeatures, extract_query_features
from backend.components.fact_processing.models import FactPreparationResult, FactRef, FactRelationships, StructuredFact
from backend.components.fact_processing.parser import fact_from_document


@dataclass(frozen=True)
class PreparedContext:
    """Prepared prompt context with provenance and query analysis metadata."""

    context: str
    context_kind: str
    context_documents: list[Document]
    preparation_result: FactPreparationResult
    query_features: QueryFeatures


class FactPreparationLayer:
    """Transforms retrieved documents into context tailored to query intent."""

    def __init__(
        self,
        retriever_service,
        max_items: int = 100,
        include_raw_snippets: bool = True,
    ) -> None:
        """Initializes fact preparation policy.

        Args:
            retriever_service: Service used for contextual formatting and expansion.
            max_items: Maximum number of selected facts.
            include_raw_snippets: Whether hybrid mode should include raw snippets.
        """
        self.retriever_service = retriever_service
        self.max_items = max(1, max_items)
        self.include_raw_snippets = include_raw_snippets

    def prepare(
        self,
        question: str,
        retrieved_documents: list[Document],
        fact_mode: str,
    ) -> PreparedContext:
        """Builds context for raw, structured, or hybrid answer generation.

        Args:
            question: User question used to infer intent.
            retrieved_documents: Initial documents retrieved for the question.
            fact_mode: Context mode: raw, structured, or hybrid.

        Returns:
            Prepared context bundle used by the answering layer.
        """
        query_features = extract_query_features(question)

        if fact_mode == "raw":
            return PreparedContext(
                context=self.retriever_service.format_context(retrieved_documents),
                context_kind="raw",
                context_documents=retrieved_documents,
                preparation_result=FactPreparationResult(
                    facts=[],
                    relationships=FactRelationships(
                        bug_to_steps={},
                        test_to_steps={},
                        sequence_to_fact={},
                    ),
                ),
                query_features=query_features,
            )

        context_documents = self._expand_documents_for_traceability(
            documents=retrieved_documents,
            query_features=query_features,
        )
        result = self._prepare_facts(context_documents)
        selected_facts = self._select_facts(
            facts=result.facts,
            relationships=result.relationships,
            query_features=query_features,
        )

        if not selected_facts and result.facts:
            selected_facts = result.facts[: self.max_items]

        structured_context = self._build_structured_context(
            facts=selected_facts,
            relationships=result.relationships,
            query_features=query_features,
        )

        if fact_mode == "structured":
            return PreparedContext(
                context=structured_context,
                context_kind="structured",
                context_documents=context_documents,
                preparation_result=FactPreparationResult(
                    facts=selected_facts,
                    relationships=result.relationships,
                ),
                query_features=query_features,
            )

        include_raw = self.include_raw_snippets
        raw_snippets = ""
        if include_raw and context_documents:
            raw_documents = context_documents[: min(len(context_documents), 8)]
            raw_snippets = self.retriever_service.format_context(raw_documents)

        context = structured_context
        if raw_snippets:
            context = f"{structured_context}\n\n[RAW_SNIPPETS]\n{raw_snippets}"

        return PreparedContext(
            context=context,
            context_kind="hybrid",
            context_documents=context_documents,
            preparation_result=FactPreparationResult(
                facts=selected_facts,
                relationships=result.relationships,
            ),
            query_features=query_features,
        )

    def _prepare_facts(self, documents: list[Document]) -> FactPreparationResult:
        facts: list[StructuredFact] = []
        seen: set[tuple[str | None, str | None, int | None, int | None]] = set()

        for document in documents:
            fact = fact_from_document(document)
            if fact is None:
                continue

            key = (fact.test_sequence, fact.source, fact.row_index, fact.chunk_index)
            if key in seen:
                continue
            seen.add(key)
            facts.append(fact)

        facts.sort(
            key=lambda item: (
                item.test_number or "",
                item.step_number or "",
                item.row_index if item.row_index is not None else 999999,
                item.chunk_index if item.chunk_index is not None else 999999,
            )
        )

        return FactPreparationResult(
            facts=facts,
            relationships=self._build_relationships(facts),
        )

    def _build_relationships(self, facts: list[StructuredFact]) -> FactRelationships:
        bug_to_steps: dict[str, list[FactRef]] = {}
        test_to_steps: dict[str, list[FactRef]] = {}
        sequence_to_fact: dict[str, FactRef] = {}

        for index, fact in enumerate(facts):
            ref = FactRef(
                fact_index=index,
                bug_number=fact.bug_number,
                test_number=fact.test_number,
                step_number=fact.step_number,
                test_sequence=fact.test_sequence,
                sheet_id=fact.sheet_id,
                source=fact.source,
                sheet_name=fact.sheet_name,
                row_index=fact.row_index,
                chunk_index=fact.chunk_index,
            )

            if fact.bug_number:
                bug_to_steps.setdefault(fact.bug_number, []).append(ref)

            if fact.test_number:
                test_to_steps.setdefault(fact.test_number, []).append(ref)

            if fact.test_sequence:
                sequence_to_fact[fact.test_sequence] = ref

        return FactRelationships(
            bug_to_steps=bug_to_steps,
            test_to_steps=test_to_steps,
            sequence_to_fact=sequence_to_fact,
        )

    def _expand_documents_for_traceability(
        self,
        documents: list[Document],
        query_features: QueryFeatures,
    ) -> list[Document]:
        expanded = list(documents)
        tests_to_expand: set[str] = set()
        preparation = self._prepare_facts(documents)

        if query_features.test_number:
            tests_to_expand.add(query_features.test_number)

        if query_features.intent in {"AFFECTED_TEST_FULL", "TEST_STEPS"} and query_features.bug_numbers:
            for bug_number in query_features.bug_numbers:
                for reference in preparation.relationships.bug_to_steps.get(bug_number, []):
                    if reference.test_number:
                        tests_to_expand.add(reference.test_number)

        for test_number in sorted(tests_to_expand):
            extra_documents = self.retriever_service.retrieve_by_metadata(
                metadata_filter={"test_number": test_number},
                k=self.max_items,
            )
            expanded = self._merge_documents(expanded, extra_documents)

        return expanded

    def _select_facts(
        self,
        facts: list[StructuredFact],
        relationships: FactRelationships,
        query_features: QueryFeatures,
    ) -> list[StructuredFact]:
        if not facts:
            return []

        if query_features.intent == "LIST_BUGS":
            return [fact for fact in facts if fact.bug_number][: self.max_items]

        if query_features.intent == "BUG_LOCATION":
            if query_features.bug_numbers:
                wanted = set(query_features.bug_numbers)
                return [fact for fact in facts if fact.bug_number in wanted][: self.max_items]
            return [fact for fact in facts if fact.bug_number][: self.max_items]

        if query_features.intent == "AFFECTED_TEST_FULL":
            tests = self._resolve_target_tests(relationships, query_features)
            if tests:
                return [fact for fact in facts if fact.test_number in tests][: self.max_items]
            return facts[: self.max_items]

        if query_features.intent == "TEST_STEPS":
            tests = self._resolve_target_tests(relationships, query_features)
            if tests:
                return [fact for fact in facts if fact.test_number in tests][: self.max_items]
            if query_features.full_sequence:
                return [
                    fact
                    for fact in facts
                    if fact.test_sequence == query_features.full_sequence
                ][: self.max_items]
            return facts[: self.max_items]

        return facts[: self.max_items]

    def _resolve_target_tests(
        self,
        relationships: FactRelationships,
        query_features: QueryFeatures,
    ) -> set[str]:
        tests: set[str] = set()

        if query_features.test_number:
            tests.add(query_features.test_number)

        for bug_number in query_features.bug_numbers:
            for reference in relationships.bug_to_steps.get(bug_number, []):
                if reference.test_number:
                    tests.add(reference.test_number)

        return tests

    def _build_structured_context(
        self,
        facts: list[StructuredFact],
        relationships: FactRelationships,
        query_features: QueryFeatures,
    ) -> str:
        facts_payload = [fact.to_public_dict() for fact in facts]
        relationship_payload = {
            "bug_to_steps": {
                bug_number: [reference.to_dict() for reference in references]
                for bug_number, references in relationships.bug_to_steps.items()
            },
            "test_to_steps": {
                test_number: [reference.to_dict() for reference in references]
                for test_number, references in relationships.test_to_steps.items()
            },
            "sequence_to_fact": {
                sequence: reference.to_dict()
                for sequence, reference in relationships.sequence_to_fact.items()
            },
        }

        header = {
            "intent": query_features.intent,
            "bug_numbers": list(query_features.bug_numbers),
            "full_sequence": query_features.full_sequence,
            "test_number": query_features.test_number,
            "step_number": query_features.step_number,
            "facts_count": len(facts_payload),
        }

        return "\n".join(
            [
                "[STRUCTURED_FACTS]",
                json.dumps(header, ensure_ascii=False),
                "[FACTS_JSON]",
                json.dumps(facts_payload, ensure_ascii=False),
                "[RELATIONSHIPS_JSON]",
                json.dumps(relationship_payload, ensure_ascii=False),
            ]
        )

    def _merge_documents(self, base: list[Document], extra: list[Document]) -> list[Document]:
        merged = list(base)
        seen = {self._document_key(document) for document in merged}

        for document in extra:
            key = self._document_key(document)
            if key in seen:
                continue
            seen.add(key)
            merged.append(document)

        return merged

    def _document_key(self, document: Document) -> tuple[str | None, int | None, int | None, str]:
        metadata = document.metadata
        return (
            str(metadata.get("source") or "") or None,
            self._safe_int(metadata.get("row_index")),
            self._safe_int(metadata.get("chunk_index")),
            str(metadata.get("test_sequence_number") or ""),
        )

    def _safe_int(self, value: object) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None
