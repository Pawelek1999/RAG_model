---
id: supported-formats
sidebar_position: 2
title: Supported document formats
---

# Supported document formats

**TL;DR:** five file types are accepted for ingestion; XLSX has an extra "test report" mode on top of plain spreadsheet reading.

Enforced by `DocumentLoader.supported_extensions()` (`backend/components/document_loader.py`), returned to the frontend's upload validation indirectly via the `/ingest` endpoint's `400` error:

| Extension | Loaded as |
|---|---|
| `.docx` | One `Document` per file |
| `.pdf` | One `Document` per page |
| `.txt` | One `Document` per file |
| `.md` | One `Document` per file |
| `.xlsx` | One `Document` per sheet or per test row, depending on mode (see below) |

For loading details per format, see [Document ingestion](../backend/document-ingestion/overview.md).

## XLSX modes

Controlled by `XLSX_LOADER_MODE` (see [Configuration](../backend/configuration.md)):

| Mode | Behavior |
|---|---|
| `standard` | Classic per-sheet reading via pandas — one `Document` per non-empty sheet. |
| `test-oriented` | Maps individual test rows to semantic `Document` records with rich metadata (test/step numbers, status, bug number, etc.), used by [Fact processing](../backend/fact-processing.md). |
| `auto` (default) | Inspects each sheet's first cell; if it reads `"importance"` (or its French variants), the workbook is treated as `test-oriented`, otherwise `standard`. See `DocumentLoader._looks_like_test_workbook()`. |
