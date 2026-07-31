---
id: rag-pipeline
sidebar_position: 1
title: RAG pipeline
---

# RAG pipeline

Source: `backend/components/rag_application.py`, orchestrated by `backend/api/services.py` (`RagApiService`).

**TL;DR:** `RAGApplication` is the last step of the pipeline — it takes a question plus an already-prepared context string, wraps them in a strict instruction template, and asks the local Ollama model to answer.

> "Answers user questions using retrieved context from indexed documents." — `RAGApplication` class docstring

It never talks to the vector store directly when invoked via `ask_with_context` — that's the job of `RetrieverService` / `FactPreparationLayer`. See [Retrieval layer](./retrieval.md) and [Fact processing](./fact-processing.md) for how the context gets built before it reaches this class.

## `RAGApplication`

### `__init__`

**TL;DR:** builds the `ChatOllama` client this class will call for every answer.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `retriever_service` | `RetrieverService` | — | Used only by the `ask()` convenience path below. |
| `model_name` | `str` | `"SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"` | Ollama chat model identifier. |
| `base_url` | `str \| None` | `None` | Ollama endpoint override, for when Ollama isn't running on the default local address. |

### `ask(question, k=None)`

**TL;DR:** a self-contained "ask a question, get an answer" shortcut that fetches its own raw context — not the path the API actually uses.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `question` | `str` | — | User question in natural language. |
| `k` | `int \| None` | `None` | Optional retrieval size override. |

**Returns:** `str` — the generated answer.

Validates the question, calls `retriever_service.retrieve_context(query=question, k=k)` to get a raw context string, then delegates to `ask_with_context`.

:::note Not used by the API
`RagApiService.ask` does **not** call this method. It calls `ask_with_context` directly with a context string already produced by `FactPreparationLayer`, so [fact processing](./fact-processing.md) mode is respected. `ask()` exists as a simpler, non-fact-aware entry point (e.g. for scripts or tests).
:::

### `ask_with_context(question, context, context_kind="raw")`

**TL;DR:** the method the API actually calls — turns a ready-made context string into a model answer, or short-circuits with a fixed "I don't know" reply if there's no context.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `question` | `str` | — | User question in natural language. |
| `context` | `str` | — | Prepared context string (see [Fact processing](./fact-processing.md)). |
| `context_kind` | `str` | `"raw"` | `raw` / `structured` / `hybrid` — selects which prompt template to build. |

**Returns:** `str` — the generated answer, or the fallback sentence below.

1. Validates the question is non-empty (raises `ValueError` otherwise).
2. If `context` is empty/blank, returns a fixed fallback **without calling the model**.
3. Otherwise builds a prompt via `_build_prompt(question, context, context_kind)` and calls `self.llm.invoke(prompt)`, returning the trimmed response content.

:::note Fixed fallback answer
When there's no context, the model is never called — the method returns this exact string:

```text
Nie wiem. Nie znalazlem odpowiedzi w dostepnych dokumentach.
```

("I don't know. I couldn't find the answer in the available documents.")
:::

### `_build_prompt(question, context, context_kind)`

**TL;DR:** picks one of three Polish-language prompt templates, all of which force the model to answer only from the given context and never invent facts.

| `context_kind` | Template method | What it adds |
|---|---|---|
| `raw` (default) | `_build_prompt` itself | Plain "answer only from KONTEKST" instructions, for context built directly from retrieved chunks. |
| `structured` | `_build_structured_prompt` | Rules to treat `[FACTS_JSON]` as the primary factual source and `[RELATIONSHIPS_JSON]` as the map for traversing Bug → Step → Test relationships. |
| `hybrid` | `_build_hybrid_prompt` | Prefer `[FACTS_JSON]`/`[RELATIONSHIPS_JSON]` first, fall back to `[RAW_SNIPPETS]` only when a fact is incomplete. |

These `context_kind` values are produced by `FactPreparationLayer.prepare()` — see [Fact processing](./fact-processing.md).

**Example** (the `raw` template, with placeholders left in):

```text
Jestes asystentem RAG. Odpowiadaj w jezyku polskim.

Zasady:
- Odpowiadaj wylacznie na podstawie sekcji KONTEKST.
- Jesli w KONTEKSCIE nie ma odpowiedzi, napisz: "Nie wiem. Nie znalazlem odpowiedzi w dostepnych dokumentach."
- Nie wymyslaj faktow spoza dokumentow.
- Odpowiedz ma byc krotka, konkretna i czytelna.

KONTEKST:
{context}

PYTANIE:
{question}

ODPOWIEDZ:
```

## Dependencies

| Dependency | Role |
|---|---|
| `RetrieverService` | Required constructor dependency; used only by the `ask()` convenience path. |
| `langchain_ollama.ChatOllama` | The actual LLM client, configured with `model_name` and optional `base_url`. |

## Where it's wired up

`RagApiService.__init__` (`backend/api/services.py`) constructs a single `RAGApplication` instance from `settings.llm_model` and `settings.ollama_base_url`, reused for every `/ask` request (see [Configuration](./configuration.md)).
