---
id: vector-store
sidebar_position: 3
title: Vector store
---

# Vector store

Source: `backend/components/VectorStoreManager/` (`service.py`, `deduplication.py`, `search.py`).

**TL;DR:** the only module that talks to ChromaDB directly — add (with dedup), similarity search, keyword search, metadata lookup, delete, count. Everything else in the backend goes through it rather than touching Chroma itself.

## `VectorStoreManager` (`service.py`)

Wraps a persistent `langchain_chroma.Chroma` collection.

### `__init__(embedding_function, persist_directory="chroma_db", collection_name="rag_documents")`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `embedding_function` | `Embeddings` | — | Embedding function required by Chroma (see [`EmbeddingService`](./loading-and-chunking.md)). |
| `persist_directory` | `str \| Path` | `"chroma_db"` | Directory used to persist vector data. |
| `collection_name` | `str` | `"rag_documents"` | Collection name used for document storage. |

Ensures `persist_directory` exists and opens/creates the named Chroma collection (`_load_vector_store`).

### `add_documents(documents)`

**TL;DR:** the ingestion write path — deduplicates before writing, so re-ingesting the same file is a safe no-op for unchanged chunks.

| Parameter | Type | Description |
|---|---|---|
| `documents` | `list[Document]` | Documents to index. |

**Returns:** `int` — number of newly added documents.

1. Computes a deterministic id per document via `create_document_id()` (see below).
2. Filters out documents whose id already exists via `filter_existing_documents()`.
3. Adds only the new documents/ids to Chroma; returns the count actually added.

## Deduplication (`deduplication.py`)

**TL;DR:** a same-content-same-id scheme, so the same file re-ingested doesn't create duplicate chunks.

```python
# backend/components/VectorStoreManager/deduplication.py
raw_id = f"{source}|{page}|{chunk_index}|{content}"
document_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
```

`create_document_id(document) -> str` builds a SHA-256 hash from source, page, chunk index, and content — meaning the *same* file re-ingested produces the *same* ids for unchanged chunks, so `add_documents` naturally skips them. `filter_existing_documents()` also stamps the computed `document_id` back onto each surviving document's metadata.

## Search (`search.py`)

| Function | Description |
|---|---|
| `similarity_search(vector_store, query, k, metadata_filter=None)` | Thin wrapper over `vector_store.similarity_search()`, with or without a `filter=`. Validates non-empty query and `k > 0`. |
| `keyword_search(vector_store, query_terms, k, metadata_filter=None)` | **Not** a Chroma full-text feature — see scoring below. Validates `k > 0`. |

:::note `keyword_search` is implemented in Python, not in Chroma
It fetches all documents/metadata matching `metadata_filter` (or everything, if none) via `vector_store.get()`, then scores each document in Python:

| Match | Points |
|---|---|
| Term found as a substring in the lowercased content (per occurrence) | `+3` |
| Term found in a concatenation of `status`/`anomaly`/`test_sequence_number`/`test_number`/`step_number`/`bug_number` metadata | `+4` |

Documents scoring `0` are dropped; the rest are sorted descending and truncated to `k`.
:::

This is consumed by the [retrieval layer](../retrieval.md)'s hybrid search, not called directly by the ingestion pipeline.

## Other `VectorStoreManager` methods

| Method | Description |
|---|---|
| `get_retriever(k=4)` | Returns `vector_store.as_retriever(search_kwargs={"k": k})`. |
| `get_documents_by_metadata(metadata_filter, k=100)` | Pure metadata fetch (no scoring), reconstructing `Document` objects from Chroma's raw `get()` result. Returns `[]` if `metadata_filter` is falsy. |
| `count_documents()` | Returns `int` — `vector_store._collection.count()`. |
| `delete_by_source(source)` | Returns `int` — deletes all chunks where `metadata.source == source`. Raises `ValueError` on empty `source`. |
