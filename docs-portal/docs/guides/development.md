---
id: development
sidebar_position: 3
title: Development & troubleshooting
---

# Development & troubleshooting

## Useful developer commands

Frontend:

```bash
cd frontend
npm run build
npm run lint
npm run preview
```

## Known limitations

:::warning Things to keep in mind
- The CLI works once backend dependencies are installed and Ollama is reachable; without that, ingest/chat commands return import or connection errors.
- The ingest-progress store (`_INGEST_PROGRESS` in `backend/api/routers/rag.py`) is an in-process dict, not shared across multiple backend worker processes — see the note in [API reference](../backend/api-reference.md#get-ingestprogressupload_id).
- The Excel color palette used to classify `salmon`/`gray`/`white` rows (`backend/tools/Excel_tests/config.py`) is empty by default — only `blue` (`INDEXED:44`) is configured, so those classification branches in `ExcelJsonFormatter` are effectively unused unless the palette is customized. See [Excel parsing](../backend/document-ingestion/excel-parsing.md).
:::

## Troubleshooting

| Symptom | Check |
|---|---|
| Frontend shows "API offline" | `GET /health` and the value of `VITE_API_URL`. |
| No response from the model | Ollama is running and the required models are pulled. |
| No results after ingest | The document has content and chunks were saved in `chroma_db`. |
