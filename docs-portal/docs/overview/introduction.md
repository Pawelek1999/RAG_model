---
id: introduction
sidebar_position: 1
title: Introduction
slug: /
---

# RAG_model

RAG_model is a local Retrieval-Augmented Generation application for asking questions against your own documents, without sending data to an external cloud LLM. It combines a FastAPI backend, a React/Vite frontend, a local ChromaDB vector store, and local models served through [Ollama](https://ollama.com/).

## What problem it solves

Given a set of documents (DOCX, PDF, TXT, MD, or XLSX test reports), the application lets a user:

- upload and index the documents into a vector database (`POST /ingest`),
- ask natural-language questions and get answers grounded strictly in the indexed content (`POST /ask`),
- inspect exactly which document fragments (sources) were used to produce an answer,
- remove a document and all of its indexed chunks (`DELETE /documents` / `POST /documents/delete`).

The backend's `RAGApplication` is deliberately constrained to answer only from retrieved context — see [RAG pipeline](../backend/rag-pipeline.md) for the prompt rules that enforce this.

:::note No answer, no guessing
When nothing relevant is found, the backend never lets the model improvise — it returns a fixed sentence instead: "Nie wiem. Nie znalazlem odpowiedzi w dostepnych dokumentach." ("I don't know, I couldn't find the answer in the available documents.")
:::

A distinguishing feature of this project is its **Fact Processing layer**, which is specialized for QA/test-report style Excel workbooks: it can parse individual test steps, their statuses, and linked bug numbers into structured facts and traceability relationships (bug → test step, test → steps), rather than treating everything as unstructured text. See [Fact processing](../backend/fact-processing.md).

## Tech stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI (Python), served by Uvicorn |
| RAG / LLM orchestration | LangChain (`langchain-core`, `langchain-text-splitters`) |
| LLM & embeddings runtime | Ollama (`langchain-ollama`), local models |
| Vector store | ChromaDB (`langchain-chroma`) |
| Document parsing | `python-docx` (DOCX), `pypdf` (PDF), `pandas`/`openpyxl` (XLSX) |
| Frontend | React 19 + TypeScript, Vite |
| Styling | Tailwind CSS |
| Containerization | Docker Compose (frontend + backend services) |

## Where to go next

- [Architecture](./architecture.md) — components and how they fit together.
- [Request/response workflow](./workflow.md) — sequence diagrams for ingest and ask.
- [Backend](../backend/rag-pipeline.md) — RAG pipeline, retrieval, fact processing, ingestion, API reference.
- [Frontend](../frontend/component-tree.md) — component structure and data flow.
- [Guides](../guides/getting-started.md) — installation, configuration, formats, troubleshooting.
