from langchain_core.documents import Document

from backend.components.RetrieverService.constants import TEST_SEQUENCE_PATTERN
from backend.components.RetrieverService.query_features import QueryFeatures


def rerank_documents(
    documents: list[Document],
    top_k: int,
    query_features: QueryFeatures,
) -> list[Document]:
    if not documents:
        return []

    if not query_features.has_hint:
        return documents[:top_k]

    ranked: list[tuple[int, int, Document]] = []
    for index, document in enumerate(documents):
        score = score_document(document=document, query_features=query_features)
        ranked.append((score, index, document))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked[:top_k]]


def merge_candidates(
    dense_documents: list[Document],
    sparse_documents: list[Document],
    query_features: QueryFeatures,
) -> list[Document]:
    merged_scores: dict[str, tuple[float, int, Document]] = {}

    for index, document in enumerate(dense_documents):
        key = document_key(document)
        base_score = max(0.0, 1000.0 - index)
        merged_scores[key] = (base_score, index, document)

    for index, document in enumerate(sparse_documents):
        key = document_key(document)
        sparse_score = max(0.0, 1200.0 - index)

        if key in merged_scores:
            dense_score, dense_index, dense_document = merged_scores[key]
            merged_scores[key] = (dense_score + sparse_score + 250.0, dense_index, dense_document)
            continue

        fallback_score = score_document(document, query_features)
        merged_scores[key] = (sparse_score + fallback_score, 100000 + index, document)

    ranked = sorted(merged_scores.values(), key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked]


def document_key(document: Document) -> str:
    metadata = document.metadata
    source = str(metadata.get("source") or "")
    chunk_index = str(metadata.get("chunk_index") or "")
    row_index = str(metadata.get("row_index") or "")
    page = str(metadata.get("page") or "")
    test_sequence_number = str(metadata.get("test_sequence_number") or "")
    content = document.page_content
    return f"{source}|{chunk_index}|{row_index}|{page}|{test_sequence_number}|{content}"


def score_document(document: Document, query_features: QueryFeatures) -> int:
    metadata = document.metadata
    text_lower = document.page_content.lower()
    score = 0

    query_test_number = query_features.test_number
    query_step_number = query_features.step_number
    metadata_test_number = str(metadata.get("test_number") or "").strip()
    metadata_step_number = str(metadata.get("step_number") or "").strip()
    metadata_sequence = str(metadata.get("test_sequence_number") or "").strip().lower()
    metadata_bug_number = str(metadata.get("bug_number") or "").strip()

    if (not metadata_test_number or not metadata_step_number) and metadata_sequence:
        sequence_match = TEST_SEQUENCE_PATTERN.search(metadata_sequence)
        if sequence_match:
            metadata_test_number = metadata_test_number or sequence_match.group("test_number")
            metadata_step_number = metadata_step_number or sequence_match.group("step_number")

    if query_test_number and metadata_test_number == query_test_number:
        score += 120
    if query_step_number and metadata_step_number == query_step_number:
        score += 80
    if (
        query_test_number
        and query_step_number
        and metadata_test_number == query_test_number
        and metadata_step_number == query_step_number
    ):
        score += 100

    if metadata_sequence and metadata_sequence in query_features.query_lower:
        score += 140

    if query_features.bug_numbers and metadata_bug_number in set(query_features.bug_numbers):
        score += 160

    status = str(metadata.get("status") or "").strip().lower()
    anomaly = str(metadata.get("anomaly") or "").strip().lower()
    metadata_text = f"{status} {anomaly}"

    for keyword in query_features.keywords:
        if keyword == "ok" and "not ok" in query_features.query_lower:
            continue

        if keyword in text_lower:
            score += 24

        if keyword in metadata_text:
            score += 30

    if str(metadata.get("row_type") or "") == "test_step":
        score += 4

    return score
