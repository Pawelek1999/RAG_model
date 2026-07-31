---
id: configuration
sidebar_position: 6
title: Configuration
---

# Configuration

Source: `backend/api/config.py` (`ApiSettings`).

**TL;DR:** one settings object, built once from environment variables at startup, shared by every backend component — there is no per-request configuration.

A single module-level `settings = ApiSettings()` instance (built once at import time) is shared by `RagApiService` and by `backend/api/routers/rag.py` (for `DOCS_DIRECTORY`). Every field can be set via an explicit constructor argument (used in tests) or, more commonly, an environment variable — the constructor argument always wins if provided.

| `ApiSettings` field | Environment variable | Default | Notes |
|---|---|---|---|
| `chroma_directory` | `CHROMA_DIRECTORY` | `<project_root>/chroma_db` | `PROJECT_ROOT` is `backend/`'s parent directory, resolved from `config.py`'s own file location. |
| `docs_directory` | `DOCS_DIRECTORY` | `<project_root>/Docs` | Where uploaded files are saved by `POST /ingest`. |
| `collection_name` | `CHROMA_COLLECTION_NAME` | `rag_documents` | Chroma collection name. |
| `embedding_model` | `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Passed to `EmbeddingService`. |
| `llm_model` | `OLLAMA_LLM_MODEL` | `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0` | Passed to `RAGApplication`. |
| `ollama_base_url` | `OLLAMA_BASE_URL` | `None` (Ollama client default) | Shared by embedding and chat clients. |
| `default_k` | `DEFAULT_K` | `4` | Default retrieval size when a request doesn't override `k`. |
| `xlsx_loader_mode` | `XLSX_LOADER_MODE` | `auto` | Normalized (lowercased, trimmed) by `DocumentLoader`, not by `ApiSettings` itself. |
| `rag_fact_mode` | `RAG_FACT_MODE` | `hybrid` | Normalized via `_normalize_fact_mode()`; any value outside `{raw, structured, hybrid}` silently falls back to `hybrid`. |
| `rag_fact_max_items` | `RAG_FACT_MAX_ITEMS` | `120` | Clamped to a minimum of `1` via `max(1, ...)`. |
| `rag_fact_include_raw_snippets` | `RAG_FACT_INCLUDE_RAW_SNIPPETS` | `true` | Parsed by `_parse_bool_env()`: `"1"`, `"true"`, `"yes"`, `"on"` (case-insensitive) count as `True`; anything else is `False`. |

:::note Silent fallbacks — invalid values don't raise errors
Three settings are normalized rather than validated strictly, so a typo in an env var won't crash the app:

- `RAG_FACT_MODE` outside `{raw, structured, hybrid}` silently falls back to `hybrid`.
- `RAG_FACT_MAX_ITEMS` is clamped to a minimum of `1`.
- `RAG_FACT_INCLUDE_RAW_SNIPPETS` treats any value other than `"1"`/`"true"`/`"yes"`/`"on"` as `False`, including typos.
:::

## Frontend

Source: `frontend/src/api/ragApi.ts`.

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8000` | Read via `import.meta.env.VITE_API_URL`; used as the base URL for every backend request. |

## Related

- [API reference](./api-reference.md) — endpoints that consume these settings.
- [Fact processing](./fact-processing.md) — behavior controlled by `RAG_FACT_MODE`, `RAG_FACT_MAX_ITEMS`, `RAG_FACT_INCLUDE_RAW_SNIPPETS`.
- [Loading & chunking](./document-ingestion/loading-and-chunking.md) — behavior controlled by `XLSX_LOADER_MODE`.
- [Guides → Getting started](../guides/getting-started.md) — how to run the app with these variables set.
