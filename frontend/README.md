# RAG Frontend

Frontend application for document ingestion and RAG chat.

## Purpose

The frontend provides a single-screen workflow to:

- upload files for indexing,
- list indexed documents,
- delete indexed document chunks,
- ask questions against indexed content,
- display assistant answers with source references.

## Stack

- React
- TypeScript
- Vite
- Tailwind CSS

## Run locally

1. Install dependencies.
2. Start the development server.

```bash
npm install
npm run dev
```

By default, the frontend expects the backend API at:

- `http://127.0.0.1:8000`

You can override it using:

- `VITE_API_URL`

## Environment

Create an `.env` file in `frontend/` when needed:

```env
VITE_API_URL=http://127.0.0.1:8000
```

## Architecture overview

- `src/main.tsx`: application bootstrap.
- `src/App.tsx`: top-level state orchestration and feature composition.
- `src/components/*`: UI sections for chat, documents, upload, and status.
- `src/api/ragApi.ts`: backend communication and ingest progress handling.
- `src/types.ts`: shared UI message and status types.

## Data flow

1. User action in a component triggers a handler from `App.tsx`.
2. `App.tsx` calls an API function from `src/api/ragApi.ts`.
3. API response updates local state in `App.tsx`.
4. Updated state is rendered by presentational components.

## Notes

- Current architecture is intentionally simple and single-page.
- Routing, custom hooks, and context providers can be introduced when feature scope grows.
