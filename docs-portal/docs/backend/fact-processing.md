---
id: fact-processing
sidebar_position: 3
title: Fact processing
---

# Fact processing

Source: `backend/components/fact_processing/` (`models.py`, `parser.py`, `service.py`).

## Purpose

**TL;DR:** turns messy document chunks (mostly XLSX test-report rows) into clean, structured facts the LLM can reason about precisely, instead of just pasting raw text into the prompt.

The fact processing layer turns retrieved, loosely-structured document chunks into **normalized facts** and **traceability relationships**, then renders them into one of three context formats controlled by `RAG_FACT_MODE`: `raw`, `structured`, or `hybrid`. See [Configuration](./configuration.md) for the environment variables, and [RAG pipeline](./rag-pipeline.md) for how `context_kind` selects the prompt template.

## Domain models (`models.py`)

### `StructuredFact`

**TL;DR:** the normalized record of one test step — the canonical shape every downstream step (selection, JSON export, prompting) works with.

*Frozen dataclass.*

| Field | Type | Description |
|---|---|---|
| `sheet_id` | `str \| None` | Optional worksheet prefix parsed from the test sequence (e.g. `AA`). |
| `test_number` | `str \| None` | 5-digit test number. |
| `step_number` | `str \| None` | 3-digit step number. |
| `test_sequence` | `str \| None` | Normalized `test.step` (or `sheet_id_test.step`) string. |
| `procedure` | `str \| None` | Procedure text for the step. |
| `expected_result` | `str \| None` | Expected result text. |
| `observed_result` | `str \| None` | Observed result text. |
| `status` | `str` | One of the allowed status values (see note below). |
| `bug_number` | `str \| None` | Linked bug number, if any. |
| `source` | `str \| None` | Source file path — provenance only. |
| `sheet_name` | `str \| None` | Worksheet name — provenance only. |
| `row_index` | `int \| None` | Row index in the sheet — provenance only. |
| `chunk_index` | `int \| None` | Chunk index after splitting — provenance only. |
| `row_type` | `str \| None` | `test_step` / `test_header` / etc. — provenance only. |

:::note Allowed status values
`status` is restricted to `ALLOWED_STATUS_VALUES`: `OK`, `NOT OK`, `IMPOSSIBLE TO ACHIEVE`, `WRITING ERROR`, `UNKNOWN`.
:::

#### `to_public_dict() -> dict`

**TL;DR:** strips the provenance fields, keeping only what the LLM is allowed to see.

```python
fact.to_public_dict()
# {
#     "sheet_id": None, "test_number": "12345", "step_number": "001",
#     "test_sequence": "12345.001", "procedure": "...", "expected_result": "...",
#     "observed_result": "...", "status": "OK", "bug_number": None,
# }
```

Used to build the `[FACTS_JSON]` block sent to the model.

### `FactRef`

**TL;DR:** a lightweight pointer to one fact's position and identity, used inside relationship maps instead of embedding the full fact.

*Frozen dataclass.*

| Field | Type | Description |
|---|---|---|
| `fact_index` | `int` | Position of the referenced fact in the fact list. |
| `bug_number` | `str \| None` | Linked bug number, if any. |
| `test_number` | `str \| None` | 5-digit test number. |
| `step_number` | `str \| None` | 3-digit step number. |
| `test_sequence` | `str \| None` | Normalized `test.step` string. |
| `sheet_id` | `str \| None` | Optional worksheet prefix. |
| `source` | `str \| None` | Source file path. |
| `sheet_name` | `str \| None` | Worksheet name. |
| `row_index` | `int \| None` | Row index in the sheet. |
| `chunk_index` | `int \| None` | Chunk index after splitting. |

:::note
`FactRef` has no content fields (`procedure` / `expected_result` / etc.) — only identity and provenance. Look up the full fact via `fact_index` when content is needed.
:::

#### `to_dict() -> dict`

**TL;DR:** serializes the reference for the `[RELATIONSHIPS_JSON]` prompt block.

### `FactRelationships`

**TL;DR:** three lookup indexes that let the model (or the code) jump from a bug or test number straight to the relevant steps, without scanning the whole fact list.

*Frozen dataclass.*

| Field | Type | Description |
|---|---|---|
| `bug_to_steps` | `dict[str, list[FactRef]]` | Every step reference for a given bug number. |
| `test_to_steps` | `dict[str, list[FactRef]]` | Every step reference for a given test number. |
| `sequence_to_fact` | `dict[str, FactRef]` | Direct lookup by full `test.step` sequence. |

### `FactPreparationResult`

**TL;DR:** a simple bundle pairing the parsed facts with their computed relationships.

*Frozen dataclass.*

| Field | Type | Description |
|---|---|---|
| `facts` | `list[StructuredFact]` | All facts parsed from the (expanded) document set. |
| `relationships` | `FactRelationships` | Indexes built from `facts`. |

## Parsing a document into a fact (`parser.py`)

### `fact_from_document(document)`

**TL;DR:** tries to turn one retrieved document into a `StructuredFact`; returns `None` when the document clearly isn't a test-step row.

| Parameter | Type | Description |
|---|---|---|
| `document` | `Document` | Retrieved LangChain document with `page_content` and `metadata`. |

**Returns:** `StructuredFact \| None`

How it resolves each field:

- Prefers structured metadata set by `DocumentLoader`'s test-oriented XLSX path (see [Loading & chunking](./document-ingestion/loading-and-chunking.md)).
- Falls back to parsing labeled lines out of raw text (e.g. a line `"Procedure: ..."`) via `_extract_labeled_value()`.
- Returns `None` when `_looks_like_test_fact()` decides the document isn't a test-step fact at all.

:::note Why this can return `None`
A document is rejected only when **all** of these are true: `row_type` isn't `test_step`/`test_header`, there's no test sequence or test+step number, and none of procedure/expected/observed result is present. This is what lets `structured`/`hybrid` mode gracefully skip non-tabular content instead of fabricating a fact from it.
:::

**Example** (traced through the actual field-resolution logic):

```python
document = Document(
    page_content=(
        "Procedure: Power on the unit\n"
        "Expected result: LED turns green\n"
        "Observed result: LED stayed red. Anomaly: LED driver fault. BUG NB: 4521"
    ),
    metadata={
        "row_type": "test_step",
        "test_sequence_number": "12345.001",
        "source": "Docs/report.xlsx",
        "sheet_name": "AA_Power",
        "row_index": 8,
        "chunk_index": 1,
    },
)

fact_from_document(document)
# StructuredFact(
#     sheet_id=None, test_number="12345", step_number="001", test_sequence="12345.001",
#     procedure="Power on the unit", expected_result="LED turns green",
#     observed_result="LED stayed red. Anomaly: LED driver fault. BUG NB: 4521",
#     status="UNKNOWN", bug_number="4521",
#     source="Docs/report.xlsx", sheet_name="AA_Power", row_index=8, chunk_index=1,
#     row_type="test_step",
# )
```

### `parse_test_sequence_parts(raw_sequence)`

**TL;DR:** splits a raw sequence string like `AA_12345.001` into its sheet/test/step parts plus a normalized form.

```python
# Matches an optional alphanumeric sheet prefix, then a 5-digit test number,
# a dot, and a 3-digit step number.
TEST_SEQUENCE_PATTERN = re.compile(
    r"\b(?:(?P<sheet_id>[A-Za-z0-9]+)_)?(?P<test_number>\d{5})\.(?P<step_number>\d{3})\b"
)
# Matches: "AA_12345.001", "12345.001"
```

| Parameter | Type | Description |
|---|---|---|
| `raw_sequence` | `object` | Raw sequence value from metadata or text (coerced to string). |

**Returns:** `tuple[sheet_id, test_number, step_number, normalized_sequence]`, each `str \| None`.

```python
parse_test_sequence_parts("AA_12345.001")
# ("AA", "12345", "001", "AA_12345.001")

parse_test_sequence_parts("12345.001")
# (None, "12345", "001", "12345.001")
```

### `extract_bug_number(*values)`

**TL;DR:** returns the first bug number found across a prioritized list of candidate text fields.

```python
# Matches "BUG", optionally followed by "NB", then an optional separator
# (: # or -) and one or more digits. Case-insensitive.
BUG_NUMBER_PATTERN = re.compile(
    r"\bBUG(?:\s*NB)?\s*[:#-]?\s*(?P<bug_number>\d+)\b", re.IGNORECASE
)
# Matches: "BUG: 4521", "bug nb 4521", "BUG-4521"
```

Looked up, in priority order, across:

- `bug_number` metadata
- `observed_result`
- `conclusion`
- raw document content

```python
extract_bug_number(None, "Observed: BUG NB: 4521", "OK")
# "4521"
```

### `normalize_status(raw_status, fallback_text=None)`

**TL;DR:** maps free-text status/conclusion values onto the fixed set of statuses used everywhere downstream.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `raw_status` | `object` | — | Primary status value (e.g. metadata `status`, or a parsed `Status:` line). |
| `fallback_text` | `object \| None` | `None` | Secondary text checked when `raw_status` doesn't resolve (typically `conclusion`). |

```python
normalize_status("not ok")        # "NOT OK"
normalize_status("NOK")           # "NOT OK"  (recognized alias)
normalize_status(None, "random")  # "UNKNOWN" (nothing recognizable)
```

:::note Default fallback
If neither `raw_status` nor `fallback_text` matches a known value or alias, the function returns `"UNKNOWN"` rather than raising an error.
:::

## Preparation workflow (`service.py`)

### `FactPreparationLayer.__init__`

**TL;DR:** configures how aggressively facts are gathered and whether raw text is kept as a fallback.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `retriever_service` | `RetrieverService` | — | Used for contextual formatting and metadata-based document expansion. |
| `max_items` | `int` | `100` | Caps how many facts are selected into context; also the per-test expansion query limit. |
| `include_raw_snippets` | `bool` | `True` | Whether `hybrid` mode appends a `[RAW_SNIPPETS]` fallback block. |

### `prepare(question, retrieved_documents, fact_mode)`

**TL;DR:** the single entry point that turns a question plus retrieved documents into the final prompt context, in whichever mode is configured.

| Parameter | Type | Description |
|---|---|---|
| `question` | `str` | User question, used to infer intent via `extract_query_features()`. |
| `retrieved_documents` | `list[Document]` | Initial documents retrieved for the question. |
| `fact_mode` | `str` | One of `raw`, `structured`, `hybrid` — see `RAG_FACT_MODE` in [Configuration](./configuration.md). |

**Returns:** `PreparedContext`

| Field | Type | Description |
|---|---|---|
| `context` | `str` | Final context string embedded in the prompt. |
| `context_kind` | `str` | `raw` / `structured` / `hybrid` — selects the prompt template (see [RAG pipeline](./rag-pipeline.md)). |
| `context_documents` | `list[Document]` | Document set actually used to build context (may be wider than `retrieved_documents`). |
| `preparation_result` | `FactPreparationResult` | The parsed facts and their relationships. |
| `query_features` | `QueryFeatures` | Parsed intent and hints from the question. |

:::tip `raw` mode is the cheapest path
When `fact_mode == "raw"`, `retrieved_documents` is passed straight through `retriever_service.format_context()` — no fact parsing happens at all, and `preparation_result` is returned empty.
:::

For `structured` and `hybrid`, the shared pipeline is:

1. `_expand_documents_for_traceability()` — widen the document set (see below).
2. `_prepare_facts()` — parse every (deduplicated) expanded document into a `StructuredFact` via `fact_from_document()`, sort by `(test_number, step_number, row_index, chunk_index)`, then build `FactRelationships` via `_build_relationships()`.
3. `_select_facts()` — filter the fact list by detected intent (see below).
4. `_build_structured_context()` — serialize a `[STRUCTURED_FACTS]` header (intent, bug numbers, sequence/test/step, fact count) plus `[FACTS_JSON]` and `[RELATIONSHIPS_JSON]` blocks as JSON text.
5. **`hybrid` only** — append up to 8 documents' worth of raw context as `[RAW_SNIPPETS]`, when `include_raw_snippets` is enabled and expanded context exists.

:::note Fallback when intent filtering finds nothing
If step 3's intent-based filtering produces an empty list but facts *do* exist, `prepare()` falls back to the first `max_items` facts rather than returning an empty context.
:::

### `_expand_documents_for_traceability(documents, query_features)`

**TL;DR:** pulls in extra documents beyond what the retriever returned, so a "show me the full test" question isn't cut short by the retriever's `k`.

| Parameter | Type | Description |
|---|---|---|
| `documents` | `list[Document]` | The initially retrieved documents. |
| `query_features` | `QueryFeatures` | Parsed intent and hints from the question. |

**Returns:** `list[Document]` — the original documents plus any expansion results.

- Always expands the query's own `test_number`, if present.
- When intent is `AFFECTED_TEST_FULL` or `TEST_STEPS` and bug numbers are present, resolves every test number linked to those bugs (via relationships built from the *initial* document set) and expands those too.
- For every test number to expand, calls `retriever_service.retrieve_by_metadata({"test_number": ...}, k=max_items)` — a pure metadata fetch, bypassing similarity ranking — and merges results in via `_merge_documents()`, deduplicated by `_document_key()` (source, row index, chunk index, test sequence number).

### `_select_facts(facts, relationships, query_features)`

**TL;DR:** narrows the full fact list down to what's relevant for the detected intent, so the model isn't flooded with unrelated facts.

| Parameter | Type | Description |
|---|---|---|
| `facts` | `list[StructuredFact]` | All parsed facts, already sorted. |
| `relationships` | `FactRelationships` | Indexes built from `facts`. |
| `query_features` | `QueryFeatures` | Parsed intent and hints from the question. |

**Returns:** `list[StructuredFact]`, capped at `max_items`.

| Intent | Selection |
|---|---|
| `LIST_BUGS` | every fact that has a `bug_number` |
| `BUG_LOCATION` | facts whose `bug_number` is in the query's bug numbers (or, if none detected, any fact with a bug number) |
| `AFFECTED_TEST_FULL` | facts belonging to the resolved target test(s) via `_resolve_target_tests()`, else all facts |
| `TEST_STEPS` | facts belonging to the resolved target test(s); else facts matching the exact `full_sequence`; else all facts |
| anything else (`GENERAL_QA`) | the first `max_items` facts, in parsed order |

:::note `_resolve_target_tests()`
Unions the query's own `test_number` (if any) with every test number reachable from the query's bug numbers via `relationships.bug_to_steps`.
:::

## Where it's wired up

`RagApiService.__init__` constructs one `FactPreparationLayer` from `settings.rag_fact_max_items` and `settings.rag_fact_include_raw_snippets`. `RagApiService.ask()` calls `fact_preparation_layer.prepare(question, documents, fact_mode=settings.rag_fact_mode)`, then passes `prepared.context` / `prepared.context_kind` to `RAGApplication.ask_with_context()`, and derives the API's `sources` list from `prepared.context_documents`.
