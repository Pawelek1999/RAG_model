"""Search helpers for similarity and keyword lookups in the vector store."""

import logging
from typing import Any

from langchain_core.documents import Document


logger = logging.getLogger(__name__)


def similarity_search(
    vector_store,
    query: str,
    k: int = 4,
    metadata_filter: dict[str, Any] | None = None,
) -> list[Document]:
    """Runs vector similarity search with optional metadata constraints.

    Args:
        vector_store: Chroma-like vector store instance.
        query: Query text for semantic search.
        k: Maximum number of results.
        metadata_filter: Optional metadata predicate.

    Returns:
        Matching documents ordered by similarity.

    Raises:
        ValueError: When query is empty or k is not positive.
    """
    if not query or not query.strip():
        raise ValueError("Zapytanie nie moze byc puste")

    if k <= 0:
        raise ValueError("k musi byc wieksze od 0")

    logger.debug(
        "vector-search-start query_len=%s k=%s filter=%s",
        len(query),
        k,
        metadata_filter,
    )

    if metadata_filter:
        documents = vector_store.similarity_search(query, k=k, filter=metadata_filter)
    else:
        documents = vector_store.similarity_search(query, k=k)

    logger.debug("vector-search-end results_count=%s", len(documents))
    return documents


def keyword_search(
    vector_store,
    query_terms: list[str],
    k: int = 20,
    metadata_filter: dict[str, Any] | None = None,
) -> list[Document]:
    """Performs keyword scoring over stored document text and metadata.

    Args:
        vector_store: Chroma-like vector store instance.
        query_terms: Query tokens used for sparse matching.
        k: Maximum number of returned documents.
        metadata_filter: Optional metadata predicate.

    Returns:
        Documents ranked by keyword overlap score.

    Raises:
        ValueError: When k is not positive.
    """
    if k <= 0:
        raise ValueError("k musi byc wieksze od 0")

    cleaned_terms = [term.strip().lower() for term in query_terms if term and term.strip()]
    if not cleaned_terms:
        return []

    logger.debug(
        "vector-keyword-search-start terms_count=%s k=%s filter=%s",
        len(cleaned_terms),
        k,
        metadata_filter,
    )

    result = vector_store.get(
        where=metadata_filter,
        include=["documents", "metadatas"],
    )
    contents = result.get("documents") or []
    metadatas = result.get("metadatas") or []

    ranked: list[tuple[int, int, Document]] = []
    for index, (content, metadata) in enumerate(zip(contents, metadatas)):
        text = str(content or "")
        metadata_dict = dict(metadata or {})
        text_lower = text.lower()
        metadata_text = " ".join(
            str(metadata_dict.get(key) or "").lower()
            for key in (
                "status",
                "anomaly",
                "test_sequence_number",
                "test_number",
                "step_number",
                "bug_number",
            )
        )

        score = 0
        for term in cleaned_terms:
            score += text_lower.count(term) * 3
            if term in metadata_text:
                score += 4

        if score <= 0:
            continue

        ranked.append((score, index, Document(page_content=text, metadata=metadata_dict)))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    documents = [item[2] for item in ranked[:k]]
    logger.debug("vector-keyword-search-end results_count=%s", len(documents))
    return documents
