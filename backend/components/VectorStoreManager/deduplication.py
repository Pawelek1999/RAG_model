"""Deduplication helpers for stable document identifiers in vector storage."""

import hashlib

from langchain_core.documents import Document


def create_document_id(document: Document) -> str:
    """Generates deterministic identifier for a document chunk.

    Args:
        document: Document for which identifier should be created.

    Returns:
        SHA-256 hash derived from source metadata and chunk content.
    """
    source = str(document.metadata.get("source", ""))
    page = str(document.metadata.get("page", ""))
    chunk_index = str(document.metadata.get("chunk_index", ""))
    content = document.page_content

    raw_id = f"{source}|{page}|{chunk_index}|{content}"
    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()


def get_existing_ids(vector_store, ids: list[str]) -> list[str]:
    """Checks which candidate identifiers already exist in vector store.

    Args:
        vector_store: Chroma-like vector store instance.
        ids: Candidate document identifiers.

    Returns:
        Existing identifiers found in persistence layer.
    """
    if not ids:
        return []

    result = vector_store.get(ids=ids)
    return result.get("ids", [])


def filter_existing_documents(
    vector_store,
    documents: list[Document],
    ids: list[str],
) -> tuple[list[Document], list[str]]:
    """Filters out documents that are already present in vector storage.

    Args:
        vector_store: Chroma-like vector store instance.
        documents: Candidate documents to insert.
        ids: Candidate identifiers aligned with documents.

    Returns:
        Tuple with only new documents and their corresponding identifiers.
    """
    existing_ids = set(get_existing_ids(vector_store, ids))
    new_documents: list[Document] = []
    new_ids: list[str] = []

    for document, document_id in zip(documents, ids):
        if document_id in existing_ids:
            continue

        document.metadata["document_id"] = document_id
        new_documents.append(document)
        new_ids.append(document_id)

    return new_documents, new_ids
