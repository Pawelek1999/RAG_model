---
id: loading-and-chunking
sidebar_position: 2
title: Loading & chunking
---

# Loading & chunking

Source: `backend/components/document_loader.py`, `document_chunker.py`, `embedding_service.py`.

**TL;DR:** three small, single-purpose classes that live directly in `backend/components/` — turn a raw file into normalized `Document` objects, split them into overlap-aware chunks, and embed them.

## `DocumentLoader` (`document_loader.py`)

**TL;DR:** the entry point for turning any supported file into LangChain `Document` objects.

> "Loads supported file types and normalizes them into document objects."

### `__init__(xlsx_mode=None)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `xlsx_mode` | `str \| None` | `None` | Spreadsheet mode: `auto`, `standard`, or `test-oriented`. Falls back to the `XLSX_LOADER_MODE` env var, then `"auto"`. |

Registers one loader method per extension in `self._loaders`: `.docx`, `.pdf`, `.txt`, `.md`, `.xlsx`.

### `load(file_path)`

**TL;DR:** validates a file and dispatches it to the right per-format loader.

| Parameter | Type | Description |
|---|---|---|
| `file_path` | `str \| Path` | Path to a supported document file. |

**Returns:** `list[Document]`

**Raises:** `FileNotFoundError` (path doesn't exist), `ValueError` (path isn't a file, or extension unsupported).

### `supported_extensions()`

**TL;DR:** the list `RagApiService` exposes to the `/ingest` endpoint for upload validation.

**Returns:** `list[str]` — the sorted extension keys of `self._loaders`.

### Per-format loading behavior

| Format | Method | Behavior |
|---|---|---|
| `.docx` | `_load_docx` | Reads all non-empty paragraphs via `python-docx`, joins them into **one** `Document` with `file_type="docx"`. |
| `.pdf` | `_load_pdf` | Uses `pypdf.PdfReader`; creates **one `Document` per page** with non-empty extracted text, storing `page` and `total_pages` in metadata. |
| `.txt` / `.md` | `_load_text` | Reads the whole file as UTF-8 text into a single `Document`, with `file_type` set from the file's own suffix. |
| `.xlsx` | `_load_xlsx` | Resolves an effective mode via `_resolve_xlsx_mode()`, then dispatches to `_load_xlsx_standard` or `_load_xlsx_test_oriented`. |

### XLSX standard mode (`_load_xlsx_standard`)

**TL;DR:** the plain-spreadsheet path — one `Document` per non-empty sheet, as CSV text.

Reads all sheets with `pandas.read_excel(..., engine="openpyxl")`, drops fully-empty rows/columns per sheet, and converts each non-empty sheet to CSV text as one `Document` (metadata includes `sheet_name`).

### XLSX test-oriented mode (`_load_xlsx_test_oriented`)

**TL;DR:** the specialized path for QA test-report workbooks — one `Document` per test row, with rich metadata instead of raw CSV. Delegates the actual cell-level parsing to the toolkit covered in [Excel parsing](./excel-parsing.md).

Uses `ExcelJsonFormatter` (from `backend/tools/Excel_tests`) to turn the workbook into structured row dicts, then for every row:

- Skips the row if it's a detected test-header row (`_is_test_header_row`), marked `skip_from_business_flow`, or not of `row_type` `test_step`/`test_header`.
- Builds page content via `_build_test_row_content()`, preferring the formatter's own `display_fields` (label/value pairs already tailored to header vs. step rows).
- Falls back to a fixed field list when `display_fields` is empty:
  - `Test sequence number`, `Revision`, `Procedure`, `Expected result`
  - `Observed result`, `Conclusion`, `Comment`, `Status`, `Anomaly`
- Builds rich metadata via `_build_test_row_metadata()`:
  - `sheet_name`, `row_index`, `row_type`, `status`, `anomaly`, `skip_from_business_flow`, `test_sequence_number`
  - `sheet_id`, `test_number`, `step_number` — parsed out of the sequence via `_extract_test_sequence_parts()`
  - `bug_number` — extracted from `observed_result`/`conclusion` via `_extract_bug_number()`

:::note This metadata feeds the rest of the pipeline
`fact_from_document()` (see [Fact processing](../fact-processing.md)) and the [retrieval layer](../retrieval.md)'s metadata filters both rely on exactly this metadata shape.
:::

### XLSX mode auto-detection (`_resolve_xlsx_mode` / `_looks_like_test_workbook`)

**TL;DR:** when mode is `auto`, the loader peeks at each sheet's first cell to guess whether it's a test report.

When mode is `auto`, the loader opens the workbook with `ExcelWorkbook.load()` (see [Excel parsing](./excel-parsing.md)) and checks the first cell (row 1, column 1) of every sheet.

```python
# Treated as test-oriented if any sheet's first cell reads one of:
{"importance", "nb d'importance", "nb d’importance"}
```

If any sheet matches, the whole workbook is treated as `test-oriented`; otherwise `standard`.

### Shared metadata

Every loaded `Document` gets a base metadata dict from `_base_metadata()`:

| Field | Description |
|---|---|
| `source` | Full path string. |
| `file_name` | File name only. |
| `file_type` | Extension without the dot (e.g. `docx`, `pdf`). |

## `DocumentChunker` (`document_chunker.py`)

**TL;DR:** splits documents into overlapping chunks sized for embedding, and stamps each chunk with its index.

> "Splits LangChain documents into overlap-aware chunks for retrieval."

### `__init__(chunk_size=1000, chunk_overlap=200)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `chunk_size` | `int` | `1000` | Maximum characters per chunk. |
| `chunk_overlap` | `int` | `200` | Overlap size shared between adjacent chunks. |

**Raises:** `ValueError` if `chunk_size <= 0`, `chunk_overlap < 0`, or `chunk_overlap >= chunk_size`.

Wraps LangChain's `RecursiveCharacterTextSplitter` with these parameters.

### `split(documents)` / `split_one(document)`

**TL;DR:** the actual splitting call — `split_one` is just `split([document])`.

| Method | Parameter | Returns |
|---|---|---|
| `split(documents)` | `documents: list[Document]` | `list[Document]` — chunks with `chunk_index` stamped into metadata (1-based). |
| `split_one(document)` | `document: Document` | `list[Document]` — convenience wrapper around `split([document])`. |

## `EmbeddingService` (`embedding_service.py`)

**TL;DR:** wraps Ollama's embedding model behind a small, validated interface.

> "Converts text and documents into vector embeddings."

Wraps `langchain_ollama.OllamaEmbeddings`, configured from `model_name` (default `nomic-embed-text`) and an optional `base_url`.

| Method | Returns | Description |
|---|---|---|
| `embed_text(text)` | `list[float]` | Embeds one string. Raises `ValueError` on empty/blank input. |
| `embed_texts(texts)` | `list[list[float]]` | Embeds a batch; validates every entry is non-empty. |
| `embed_documents(documents)` | `list[list[float]]` | Extracts `page_content` from each `Document` and embeds them; returns `[]` for an empty input list. |
| `get_embedding_function()` | `OllamaEmbeddings` | Returns the raw LangChain-compatible embeddings object, passed directly into `Chroma(embedding_function=...)` by [`VectorStoreManager`](./vector-store.md). |
