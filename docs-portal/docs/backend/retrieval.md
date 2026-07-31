---
id: retrieval
sidebar_position: 2
title: Retrieval layer
---

# Retrieval layer

Source: `backend/components/RetrieverService/` (`service.py`, `query_features.py`, `ranking.py`, `constants.py`).

**TL;DR:** finds the document chunks most relevant to a question by combining semantic (embedding) search with keyword search, then reranking everything using signals parsed from the question itself — test numbers, step numbers, bug numbers, and intent.

`RetrieverService` "retrieves and formats context documents for downstream RAG generation." It implements **hybrid retrieval**: dense (embedding similarity) search combined with sparse (keyword) search, merged and reranked using query-intent-aware scoring. This matters for the test-report use case, where an exact test number, step number, or bug number is often more relevant than semantic similarity alone.

## `RetrieverService`

### `__init__(vector_store_manager, k=4)`

**TL;DR:** stores the default retrieval size and the storage dependency.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `vector_store_manager` | `VectorStoreManager` | — | Dependency used for the actual Chroma queries. |
| `k` | `int` | `4` | Default number of results returned per query. |

### `retrieve(query, k=None)`

**TL;DR:** the main hybrid retrieval entry point — dense + sparse search, merged and reranked.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | — | User query. |
| `k` | `int \| None` | `None` | Optional retrieval size override. |

**Returns:** `list[Document]` — ranked, ready for context building.

**Raises:** `ValueError` on empty query or non-positive `k`.

1. Validates `query` and `k`.
2. Calls `extract_query_features(query)` to detect **intent** and structured hints (test number, step number, bug numbers, keywords) — see [Query feature extraction](#query-feature-extraction-query_featurespy) below.
3. Builds an optional Chroma `metadata_filter` via `build_metadata_filter(query_features)` and a list of sparse search terms via `build_sparse_terms(query_features)`.
4. Widens the candidate pool: `candidates_k = max(search_k, search_k * 6)`, further widened to at least 60 when intent is `LIST_BUGS` or `AFFECTED_TEST_FULL`.
5. Runs `vector_store_manager.similarity_search()` (dense) and `vector_store_manager.keyword_search()` (sparse), each with the metadata filter applied.
6. Merges dense and sparse candidates with `merge_candidates()` and reranks the merged set with `rerank_documents()`, returning the top `search_k` documents.

:::note Filter fallback
If a metadata filter is set but returns zero candidates on either the dense or sparse path, that search is retried *without* the filter. This means an over-specific filter (e.g. a wrong test number) never causes a hard miss — it just falls back to unfiltered results.
:::

### `retrieve_context(query, k=None)`

**TL;DR:** convenience wrapper — retrieval plus formatting in one call.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | — | User query. |
| `k` | `int \| None` | `None` | Optional retrieval size override. |

**Returns:** `str` — calls `retrieve()` then `format_context()`, returning a ready-to-embed context string rather than raw `Document` objects.

### `retrieve_by_metadata(metadata_filter, k=None)`

**TL;DR:** a pure metadata lookup with no semantic scoring — used to pull in extra documents for traceability, not to answer a question directly.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `metadata_filter` | `dict[str, object]` | — | Chroma metadata predicate. |
| `k` | `int \| None` | `None` | Optional result limit. |

**Returns:** `list[Document]` — delegates to `vector_store_manager.get_documents_by_metadata()`.

:::note Used by fact processing
This is how `FactPreparationLayer` expands context for full test traceability — see [Fact processing](./fact-processing.md).
:::

### `format_context(documents)`

**TL;DR:** turns a list of documents into the plain-text block that gets embedded in the LLM prompt.

| Parameter | Type | Description |
|---|---|---|
| `documents` | `list[Document]` | Documents to format. |

**Returns:** `str` — each document becomes a `[Fragment N | zrodlo: <source>]` header followed by its page content, joined with blank lines.

```python
format_context(documents)
# [Fragment 1 | zrodlo: Docs/report.pdf | strona: 3]
# LED turns green when the unit is powered on...
#
# [Fragment 2 | zrodlo: Docs/report.xlsx]
# Procedure: Power on the unit
# Expected result: LED turns green
```

:::note
The `| strona: <page>` (page) segment is only included when the document's metadata has a `page` value — i.e. mainly for PDF-sourced chunks.
:::

### `get_retriever(k=None)`

**TL;DR:** an escape hatch for interop with generic LangChain chains that expect a standard retriever object.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `k` | `int \| None` | `None` | Optional retrieval size override. |

**Returns:** the underlying LangChain-compatible retriever from `VectorStoreManager.get_retriever()`.

## Query feature extraction (`query_features.py`)

### `QueryFeatures`

**TL;DR:** the structured signals parsed out of a raw question — what everything else in this layer scores and filters against.

*Frozen dataclass.*

| Field | Type | Description |
|---|---|---|
| `has_hint` | `bool` | `True` if any structured signal was found — gates whether reranking runs at all. |
| `query_lower` | `str` | Lowercased query text. |
| `full_sequence` | `str \| None` | Full `test.step` sequence, if matched. |
| `test_number` | `str \| None` | 5-digit test number, if matched. |
| `step_number` | `str \| None` | 3-digit step number, if matched. |
| `bug_numbers` | `tuple[str, ...]` | All bug numbers found in the query. |
| `intent` | `str` | One of `LIST_BUGS`, `AFFECTED_TEST_FULL`, `TEST_STEPS`, `BUG_LOCATION`, `GENERAL_QA`. |
| `keywords` | `tuple[str, ...]` | Matched entries from `ERROR_KEYWORDS`. |

### `extract_query_features(query)`

**TL;DR:** parses a raw question into test/step/bug identifiers, error keywords, and a classified intent.

| Parameter | Type | Description |
|---|---|---|
| `query` | `str` | Raw user query. |

**Returns:** `QueryFeatures`

```python
# Full test.step sequence, optionally prefixed with a sheet id.
TEST_SEQUENCE_PATTERN = re.compile(
    r"\b(?:[A-Za-z0-9]+_)?(?P<test_number>\d{5})\.(?P<step_number>\d{3})\b"
)
# Matches: "12345.001", "AA_12345.001"

# Bare 5-digit test number (fallback when no full sequence is present).
TEST_NUMBER_PATTERN = re.compile(r"\b(?P<test_number>\d{5})\b")
# Matches: "12345"

# "BUG", optionally "BUG NB", optional separator, then digits. Case-insensitive.
BUG_NUMBER_PATTERN = re.compile(
    r"\bBUG(?:\s*NB)?\s*[:#-]?\s*(?P<bug_number>\d+)\b", re.IGNORECASE
)
# Matches: "BUG: 4521", "bug nb 4521", "BUG-4521"
```

- Tries `TEST_SEQUENCE_PATTERN` first; falls back to `TEST_NUMBER_PATTERN` for a bare test number.
- Extracts every bug number matched by `BUG_NUMBER_PATTERN`.
- Extracts matched `ERROR_KEYWORDS`: `"not ok"`, `"nok"`, `"bug"`, `"failed"`, `"fail"`, `"error"`, `"ok"`.
- Classifies intent via `_detect_intent()`:

  | Intent | Triggered by |
  |---|---|
  | `LIST_BUGS` | phrases like "list bugs", "wypisz bug", "all bugs", or a bug number plus "all"/"wszystkie" |
  | `AFFECTED_TEST_FULL` | phrases like "show complete test", "pelny test", "full sequence", or a bug number plus "pelny"/"complete"/"full" |
  | `TEST_STEPS` | phrases like "show test steps", "kroki testu", a `test_number` + `step_number` pair, or a test number plus "krok"/"step" |
  | `BUG_LOCATION` | phrases like "where bug", "gdzie bug", "w ktorym tescie", or a bug number plus "test"/"step"/"krok" |
  | `GENERAL_QA` | fallback when nothing else matches |

:::note `has_hint`
`True` when any structured signal was found: a test/step/bug number, a matched keyword, or an intent other than `GENERAL_QA`. This single flag decides whether `rerank_documents()` does any work at all — see below.
:::

### `build_metadata_filter(query_features)`

**TL;DR:** turns detected identifiers into a Chroma metadata filter, most specific first.

| Parameter | Type | Description |
|---|---|---|
| `query_features` | `QueryFeatures` | Parsed query feature set. |

**Returns:** `dict | None`

| Priority | Condition | Filter produced |
|---|---|---|
| 1 | `test_number` **and** `step_number` present | `{"$and": [{"test_number": ...}, {"step_number": ...}]}` |
| 2 | first `bug_numbers` entry present | `{"bug_number": ...}` |
| 3 | `test_number` alone present | `{"test_number": ...}` |
| 4 | none of the above | `None` (no filter) |

### `build_sparse_terms(query_features)`

**TL;DR:** builds the keyword list used for sparse (keyword) matching.

| Parameter | Type | Description |
|---|---|---|
| `query_features` | `QueryFeatures` | Parsed query feature set. |

**Returns:** `list[str]` — deduplicated terms from the full sequence, test number, step number, matched keywords, and bug numbers.

:::note Bug number expansion
Each bug number is expanded into three term variants to match how bug references actually appear in source text: `"123"`, `"bug 123"`, `"bug nb 123"`.
:::

## Ranking (`ranking.py`)

### `rerank_documents(documents, top_k, query_features)`

**TL;DR:** reorders candidates by relevance — but only when the query actually gave us something specific to score against.

| Parameter | Type | Description |
|---|---|---|
| `documents` | `list[Document]` | Candidate documents from retrieval. |
| `top_k` | `int` | Maximum number of documents to return. |
| `query_features` | `QueryFeatures` | Parsed query intent and hints. |

**Returns:** `list[Document]`, capped at `top_k`.

:::note Reranking is skipped for generic questions
If `query_features.has_hint` is `False`, reranking is skipped entirely and the first `top_k` documents are returned as-is (preserving merge order). Otherwise every document is scored with `score_document()` and sorted descending (ties broken by original index).
:::

### `merge_candidates(dense_documents, sparse_documents, query_features)`

**TL;DR:** combines the dense and sparse candidate lists into one ranked, deduplicated list, boosting documents both methods agree on.

| Parameter | Type | Description |
|---|---|---|
| `dense_documents` | `list[Document]` | Candidates from semantic similarity search. |
| `sparse_documents` | `list[Document]` | Candidates from keyword search. |
| `query_features` | `QueryFeatures` | Parsed query intent and hints. |

**Returns:** `list[Document]`, sorted descending by combined score.

| Case | Score |
|---|---|
| Dense candidate at position `index` | `1000 - index` |
| Sparse candidate at position `index` | `1200 - index` |
| Appears in **both** lists | `dense_score + sparse_score + 250` |
| Sparse-only | `sparse_score + score_document(document, query_features)` |

Deduplication key: `document_key()` — a composite of source, chunk index, row index, page, test sequence number, and content.

### `score_document(document, query_features)`

**TL;DR:** the relevance heuristic used both as a merge fallback score and for final reranking — rewards exact identifier matches over fuzzy similarity.

| Parameter | Type | Description |
|---|---|---|
| `document` | `Document` | Document to score. |
| `query_features` | `QueryFeatures` | Parsed query intent and hints. |

**Returns:** `int` — higher is more relevant.

| Signal | Points |
|---|---|
| Document's `test_number` metadata matches the query's | `+120` |
| Document's `step_number` metadata matches the query's | `+80` |
| *Both* `test_number` and `step_number` match together | `+100` bonus |
| Document's `test_sequence_number` literally appears in the lowercased query text | `+140` |
| Document's `bug_number` is among the query's detected bug numbers | `+160` |
| Matched keyword found in the document's page content (per keyword) | `+24` |
| Matched keyword found in `status`/`anomaly` metadata (per keyword) | `+30` |
| `row_type == "test_step"` | `+4` |

:::note `"ok"` vs `"not ok"`
The keyword `"ok"` is skipped when the query also contains `"not ok"`, so a `"not ok"` question doesn't over-match plain `"ok"` documents.
:::

## Dependency graph

`RetrieverService` depends only on `VectorStoreManager` for actual storage access. `query_features.py` and `ranking.py` have no storage dependency and are pure functions over `Document` objects, which makes them independently testable. `FactPreparationLayer` and `RagApiService` both call `extract_query_features()` directly, in addition to going through `RetrieverService.retrieve()`.
