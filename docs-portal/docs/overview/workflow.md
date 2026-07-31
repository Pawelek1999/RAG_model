---
id: workflow
sidebar_position: 3
title: Request/response workflow
---

# Request/response workflow

## Ingest: from file upload to indexed chunks

Implemented by `ingest_document` in [`backend/api/routers/rag.py`](../backend/api-reference.md) and `RagApiService.ingest_file` in `backend/api/services.py`.

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as POST /ingest
    participant Loader as DocumentLoader
    participant Chunker as DocumentChunker
    participant VSM as VectorStoreManager
    participant Chroma as ChromaDB

    FE->>API: multipart/form-data file + X-Upload-Id header
    API->>API: validate file name & extension
    API->>API: save file to DOCS_DIRECTORY (unique path on collision)
    API->>Loader: load(file_path)
    Loader-->>API: list[Document]
    API->>Chunker: split(documents)
    Chunker-->>API: list[Document] chunks (chunk_index in metadata)
    API->>VSM: add_documents(chunks)
    VSM->>VSM: create_document_id() + filter_existing_documents() (dedup)
    VSM->>Chroma: add_documents(new_documents, new_ids)
    VSM-->>API: added_chunks_count
    API-->>FE: IngestResponse (documents_count, chunks_count, added_chunks_count, total_chunks_count)
    Note over FE,API: FE polls GET /ingest/progress/{upload_id}<br/>in parallel while the request is in flight
```

:::note How progress is tracked
Progress reporting is implemented with an in-process dictionary (`_INGEST_PROGRESS` in `rag.py`), guarded by a `Lock` and expired after `_INGEST_PROGRESS_TTL_SECONDS` (3600s). `RagApiService.ingest_file` accepts an `on_progress` callback invoked at each pipeline stage (20% loading, 45% chunking, 70% storing, 90% finalizing, 100% done), which the router maps into overall percentages via `report_service_progress`.
:::

## Ask: from question to grounded answer

Implemented by `ask_question` in `backend/api/routers/rag.py` and `RagApiService.ask` in `backend/api/services.py`.

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as POST /ask
    participant QF as extract_query_features
    participant Retriever as RetrieverService
    participant VSM as VectorStoreManager
    participant Facts as FactPreparationLayer
    participant RAGApp as RAGApplication
    participant Ollama as Ollama (chat model)

    FE->>API: { question, k }
    API->>QF: extract_query_features(question)
    QF-->>API: QueryFeatures (intent, test/bug numbers, keywords)
    API->>Retriever: retrieve(query, retrieval_k)
    Retriever->>VSM: similarity_search() + keyword_search()
    VSM-->>Retriever: dense_candidates, sparse_candidates
    Retriever->>Retriever: merge_candidates() + rerank_documents()
    Retriever-->>API: ranked list[Document]
    API->>Facts: prepare(question, documents, fact_mode)
    Facts-->>API: PreparedContext (context, context_kind, sources)
    API->>RAGApp: ask_with_context(question, context, context_kind)
    RAGApp->>Ollama: invoke(prompt)
    Ollama-->>RAGApp: generated answer
    RAGApp-->>API: answer text
    API-->>FE: AskResponse { answer, sources[] }
```

:::note Three behaviors worth knowing about, from `RagApiService.ask`
- If `RAG_FACT_MODE` is not `raw` and the detected intent is `LIST_BUGS` or `AFFECTED_TEST_FULL`, the retrieval size is widened (`max(k, min(rag_fact_max_items, 80))`) so the fact layer has enough candidates to resolve full traceability, not just the top-`k` chunks.
- The list of `sources` returned to the frontend is built from `prepared.context_documents` — i.e. the (possibly expanded-for-traceability) document set used to build context, not the raw top-`k` retrieval result.
- If no context is found, `RAGApplication.ask_with_context` short-circuits and returns a fixed fallback string instead of calling the model.
:::

## Delete: removing a document

Implemented by `_delete_document_by_source` in `backend/api/routers/documents.py` and `RagApiService.delete_document`.

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as DELETE /documents or POST /documents/delete
    participant VSM as VectorStoreManager
    participant Chroma as ChromaDB

    FE->>API: source
    API->>VSM: delete_by_source(source)
    VSM->>Chroma: get(where={"source": source})
    Chroma-->>VSM: matching ids
    VSM->>Chroma: delete(ids)
    VSM-->>API: deleted_chunks_count
    API-->>FE: DeleteDocumentResponse (or 404 if deleted_chunks_count == 0)
```
