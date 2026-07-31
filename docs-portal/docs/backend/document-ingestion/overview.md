---
id: ingestion-overview
sidebar_position: 1
title: Overview
---

# Document ingestion: overview

**TL;DR:** an uploaded file goes load → chunk → embed → store, implemented by three separate modules that live in two different directories.

This section is split into pages that mirror the actual source layout, rather than one long page — so each page maps to one real module you'd open in an editor:

| Page | Source directory / files | Covers |
|---|---|---|
| [Loading & chunking](./loading-and-chunking.md) | `backend/components/document_loader.py`, `document_chunker.py`, `embedding_service.py` | `DocumentLoader`, `DocumentChunker`, `EmbeddingService` |
| [Vector store](./vector-store.md) | `backend/components/VectorStoreManager/` | `VectorStoreManager`, deduplication, search |
| [Excel parsing](./excel-parsing.md) | `backend/tools/Excel_tests/` | Low-level `.xlsx` cell/row parsing used by the test-oriented loader mode |

:::note Two different directories
`Excel_tests` lives under `backend/tools/`, not `backend/components/` — it's a standalone parsing toolkit that `DocumentLoader` (in `components/`) calls into, not a component in its own right.
:::

## Pipeline

```mermaid
flowchart LR
    File["Uploaded file"] --> Loader["DocumentLoader.load()\n(components/document_loader.py)"]
    Loader -->|".xlsx test-oriented"| Formatter["ExcelJsonFormatter\n(tools/Excel_tests/)"]
    Loader --> Chunker["DocumentChunker.split()\n(components/document_chunker.py)"]
    Chunker --> VSM["VectorStoreManager.add_documents()\n(components/VectorStoreManager/)"]
    VSM --> Dedup["create_document_id()\nfilter_existing_documents()"]
    Dedup --> Embed["EmbeddingService\n(components/embedding_service.py,\nvia Chroma embedding_function)"]
    Embed --> Chroma[("ChromaDB collection")]
```

For the request-level sequence (upload → progress polling → response), see [Request/response workflow](../../overview/workflow.md).
