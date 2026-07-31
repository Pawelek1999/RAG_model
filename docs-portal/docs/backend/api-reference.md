---
id: api-reference
sidebar_position: 5
title: API reference
---

# API reference

Generated from the FastAPI route docstrings in `backend/api/routers/` and the Pydantic schemas in `backend/api/schemas.py`. Default local address: `http://127.0.0.1:8000`. Interactive Swagger UI is available at `/docs` (FastAPI default) once the backend is running.

All routers are mounted with no path prefix (`app.include_router(health.router)`, `rag.router`, `documents.router` in `backend/api/app.py`) — there is no `/api/v1` versioning prefix in the current implementation.

:::note Every request is logged and tagged
A middleware in `backend/api/app.py` assigns a short request id, logs start/end with duration, and returns it in the `X-Request-ID` response header. CORS is restricted to `http://localhost:5173` / `http://127.0.0.1:5173` (and the `517x` port range via regex) — see `allow_origin_regex` in `create_app()`.
:::

## `GET /health`

**TL;DR:** liveness probe — always returns a fixed "ok" payload.

**Router:** `backend/api/routers/health.py`

> "Reports a minimal service health status."

No parameters. Response `200` (`HealthResponse`):

```json
{
  "status": "ok",
  "service": "rag-api"
}
```

## `GET /documents`

**TL;DR:** lists every distinct source currently indexed, with a chunk count per document.

**Router:** `backend/api/routers/documents.py`

> "Lists documents currently represented in the vector store."

Calls `RagApiService.list_documents()`, which groups all stored chunk metadata by `source` (falling back to `file_name` as the grouping key if `source` is empty) and counts chunks per group.

No parameters. Response `200` (`DocumentsResponse`):

```json
{
  "documents": [
    {
      "file_name": "report.xlsx",
      "file_type": "xlsx",
      "source": "D:\\...\\Docs\\report.xlsx",
      "chunks_count": 42
    }
  ],
  "total_chunks_count": 42
}
```

## `DELETE /documents`

**TL;DR:** removes one document and all of its chunks, identified via a query parameter.

> "Deletes one document by source identifier passed as query parameter."

| Parameter | Location | Type | Required | Description |
|---|---|---|---|---|
| `source` | query | `string` | yes (min length 1) | Source identifier, as returned by `GET /documents`. |

Response `200` (`DeleteDocumentResponse`):

```json
{
  "source": "string",
  "deleted_chunks_count": 0,
  "total_chunks_count": 0
}
```

:::note Errors
`404` — no document found for the given `source`. Raised by the shared `_delete_document_by_source()` helper whenever `deleted_chunks_count == 0`.
:::

## `POST /documents/delete`

**TL;DR:** same deletion as above, but as a JSON body — for clients that can't easily send a `DELETE` with a query string.

> "Deletes one document by source identifier sent in request body."

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | `string` | yes (min length 1) | Source identifier to delete. |

Response `200` / errors: identical to `DELETE /documents`.

## `POST /ask`

**TL;DR:** the main endpoint — ask a question, get an answer grounded in the indexed documents plus the sources behind it.

**Router:** `backend/api/routers/rag.py`

> "Returns an answer and source references for a user question."

**Request body** (`AskRequest`):

| Field | Type | Default | Description |
|---|---|---|---|
| `question` | `string` | — | Required, min length 1. |
| `k` | `int` | `4` | Optional, must be `> 0`. |

Calls `RagApiService.ask()`, which runs the full [retrieval](./retrieval.md) → [fact processing](./fact-processing.md) → [generation](./rag-pipeline.md) pipeline.

Response `200` (`AskResponse`):

```json
{
  "answer": "string",
  "sources": [
    {
      "file_name": "string | null",
      "file_type": "string | null",
      "source": "string | null",
      "page": "int | null",
      "sheet_name": "string | null",
      "row_index": "int | null",
      "row_type": "string | null",
      "status": "string | null",
      "anomaly": "string | null",
      "skip_from_business_flow": "bool | null",
      "test_sequence_number": "string | null",
      "revision": "string | null",
      "chunk_index": "int | null"
    }
  ]
}
```

:::note Errors
`400` — raised when `RagApiService.ask()` raises `ValueError` (e.g. empty question after validation, invalid retrieval size).
:::

## `POST /ingest`

**TL;DR:** upload a file and index it into ChromaDB; progress can be polled separately via the endpoint below.

> "Uploads and indexes a document in the vector store."

**Request:** `multipart/form-data`

| Part | Location | Required | Description |
|---|---|---|---|
| `file` | form field | yes | The uploaded file. |
| `X-Upload-Id` | header | no | Correlates this upload with the progress-polling endpoint below. |

Validation, in order:

1. File name non-empty — `400` `"Brak nazwy pliku."` if missing.
2. Extension is one of `RagApiService.supported_extensions()` — `400` `"Nieobslugiwany format pliku: {extension}"` if not.

The file is then saved under `DOCS_DIRECTORY`, using `_build_unique_path()` to append `_1`, `_2`, ... on a name collision so an existing file is never overwritten. Then `RagApiService.ingest_file()` is called with a progress callback.

Response `200` (`IngestResponse`):

```json
{
  "file_name": "string",
  "documents_count": "int",
  "chunks_count": "int",
  "added_chunks_count": "int",
  "total_chunks_count": "int"
}
```

:::note Errors
`500` — any exception during save/indexing is caught, progress is marked `failed`, and the exception message is returned as `detail`.
:::

## `GET /ingest/progress/{upload_id}`

**TL;DR:** poll this to show a progress bar for an in-flight `/ingest` request.

> "Returns current ingestion progress for a previously started upload."

| Parameter | Location | Type | Description |
|---|---|---|---|
| `upload_id` | path | `string` | The `X-Upload-Id` value sent with the original `/ingest` request. |

Reads from the in-process `_INGEST_PROGRESS` dict (see [Request/response workflow](../overview/workflow.md#ingest-from-file-upload-to-indexed-chunks) for the update sequence).

Response `200` (`IngestProgressResponse`):

```json
{
  "upload_id": "string",
  "progress_percent": "int (0-100)",
  "stage": "string",
  "status": "string",
  "message": "string"
}
```

:::note Errors
`404` — no progress found for the given `upload_id`, when the id is unknown or has expired. Entries older than `_INGEST_PROGRESS_TTL_SECONDS` (3600s) are pruned lazily on read/write.
:::

:::warning TODO: single-process only
The progress store is an in-process Python dict guarded by a `threading.Lock` — it is not shared across multiple backend worker processes. If the API is ever run with multiple Uvicorn/Gunicorn workers, progress polling would need a shared store (e.g. Redis) instead; this isn't addressed in the current code.
:::
