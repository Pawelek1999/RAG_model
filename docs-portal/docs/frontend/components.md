---
id: components
sidebar_position: 2
title: Key components
---

# Key components

Source: `frontend/src/components/`.

**TL;DR:** five typed, controlled React components — each one documented inline with TSDoc comments on its own `*Props` type.

All components are typed function components with an explicit `*Props` type documented inline with TSDoc comments.

## `Header`

**TL;DR:** shows the app title and a color-coded backend connectivity badge.

| Prop | Type | Description |
|---|---|---|
| `apiStatus` | `ApiStatus` | Current backend connectivity status shown to the user. |

`statusColor()` maps `ApiStatus` to a Tailwind text color:

| Status | Color |
|---|---|
| `online` | emerald |
| `offline` | rose |
| `checking` (default) | amber |

## `UploadDropzone`

**TL;DR:** the file intake widget — drag-and-drop or click-to-browse, disabled while an upload is running.

| Prop | Type | Description |
|---|---|---|
| `isIngesting` | `boolean` | Disables file input while ingestion is running. |
| `uploadProgress` | `number \| null` | Global ingest progress percentage across selected files. |
| `onFilesSelected` | `(files: FileList) => void` | Called when the user picks or drops files for ingestion. |

A `<label>` wraps a hidden (`sr-only`) `<input type="file" multiple accept=".docx,.pdf,.txt,.md,.xlsx">`, supporting both click-to-browse and drag-and-drop.

- Local `isDragging` state toggles styling on `onDragOver`/`onDragLeave`/`onDrop`.
- `handleDrop` forwards `event.dataTransfer.files` to `onFilesSelected` when non-empty.

:::note While ingesting
The input is disabled and the label text switches to `Wgrywanie: {uploadProgress}%` (uploading progress).
:::

## `DocumentsTable`

**TL;DR:** lists every indexed document with a delete button, plus a manual refresh action.

| Prop | Type | Description |
|---|---|---|
| `documentsResponse` | `DocumentsApiResponse \| null` | Cached backend response with indexed document summaries. |
| `isDeleting` | `boolean` | Disables delete actions while a delete request is running. |
| `onDelete` | `(source: string) => void` | Removes all chunks for the selected document source. |
| `onRefresh` | `() => void` | Refreshes the document list from the backend. |

Renders a table of `documentsResponse.documents` (file name, type, chunk count, delete action) plus a manual "Odswiez" (Refresh) button and a `total_chunks_count` footer line. Shows a "Brak dokumentow w ChromaDB." (no documents) placeholder row when the list is empty or `null`.

:::note Delete button can be disabled for two different reasons
The internal `DocumentRow` sub-component derives `canDelete = Boolean(document.source)`. The delete button is disabled when **either**:

- `isDeleting` is `true` globally (another delete is in flight), or
- the row has no `source` value to key the delete request on.
:::

## `AskPanel`

**TL;DR:** the chat surface — message history, question composer, and the `k` (retrieval size) control.

| Prop | Type | Description |
|---|---|---|
| `isAsking` | `boolean` | Disables inputs and submit actions while a response is in progress. |
| `messages` | `ChatMessage[]` | Full conversation history rendered in the chat area. |
| `question` | `string` | Current textarea value controlled by the parent container. |
| `topK` | `number` | Number of retrieved chunks requested from the backend. |
| `onAsk` | `() => void` | Submits the current question to the backend. |
| `onQuestionChange` | `(question: string) => void` | Updates the controlled question input in the parent state. |
| `onTopKChange` | `(topK: number) => void` | Updates retrieval depth in the parent state. |

A fully controlled chat UI: message history (`messages.map(...)` → `ChatBubble`), a `<textarea>` bound to `question`, and a `k` number input bound to `topK`.

| Key combination | Effect |
|---|---|
| `Enter` (no Shift/Ctrl/Meta) | Submits via `onAsk()` (the `onKeyDown` handler calls `event.preventDefault()`) |
| `Shift+Enter` | Left to the browser default — inserts a new line |

The submit button is disabled when the trimmed question is empty or `isAsking` is `true`, and shows "Pytam..." (Asking...) while a request is in flight. An "Odpowiadam..." (Answering...) bubble is appended to the message list while `isAsking`.

:::note `ChatBubble` (internal sub-component)
Right-aligns and dark-styles `user` messages, left-aligns `assistant` messages. Only for assistant messages with a non-empty `sources` array, it renders a "Zrodla" (Sources) list underneath the message text.
:::

## `StatusMessage`

**TL;DR:** a one-line feedback banner, or nothing at all when there's no message.

| Prop | Type | Description |
|---|---|---|
| `message` | `string` | Message content displayed to the user when not empty. |

Renders `null` when `message` is falsy/empty; otherwise renders it as a plain bordered banner. This is the generic feedback surface `App` uses for both success and error text (see [State and data flow](./state-and-data-flow.md)).
