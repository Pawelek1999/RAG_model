import hashlib

from langchain_core.documents import Document


def create_document_id(document: Document) -> str:
    source = str(document.metadata.get("source", ""))
    page = str(document.metadata.get("page", ""))
    chunk_index = str(document.metadata.get("chunk_index", ""))
    content = document.page_content

    raw_id = f"{source}|{page}|{chunk_index}|{content}"
    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()


def get_existing_ids(vector_store, ids: list[str]) -> list[str]:
    if not ids:
        return []

    result = vector_store.get(ids=ids)
    return result.get("ids", [])


def filter_existing_documents(
    vector_store,
    documents: list[Document],
    ids: list[str],
) -> tuple[list[Document], list[str]]:
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
