---
id: getting-started
sidebar_position: 1
title: Getting started
---

# Getting started

## Requirements

- Python 3.12+
- Node.js 22+
- npm
- A running Ollama instance (locally, or reachable via `OLLAMA_BASE_URL`, see [Configuration](../backend/configuration.md))
- Optional: Docker + Docker Compose

## Installation and running

### Option A: Docker Compose (simplest)

```bash
docker compose up --build
```

Default addresses:

| Service | Address |
|---|---|
| Frontend | http://127.0.0.1:5173 |
| API | http://127.0.0.1:8000 |
| Swagger | http://127.0.0.1:8000/docs |

:::note Docker Compose specifics
- The `chroma_db` volume is persisted.
- The `Docs` folder is **not** mounted as a volume in the current `docker-compose.yml`.
- The containers assume Ollama is reachable at `host.docker.internal:11434`.
:::

### Option B: local (without Docker)

1. Clone the repository and go to the project directory.
2. Create and activate a virtual environment for the backend.
3. Install backend dependencies.
4. Run the FastAPI API.
5. Install frontend dependencies and run Vite.

Backend (PowerShell):

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
pip install -r backend/requirements.txt
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Backend (bash):

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Ollama models

Minimum required embedding model:

```bash
ollama pull nomic-embed-text
```

The LLM model depends on your configuration (see [Configuration](../backend/configuration.md)):

| Run mode | Default LLM model |
|---|---|
| Local (`OLLAMA_LLM_MODEL` unset) | `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0` |
| `docker-compose.yml` | `qwen2.5:7b` |

:::tip Pull both
Since the local default and the Docker Compose default differ, it's worth pulling both up front so switching between the two run modes doesn't hit a missing-model error:

```bash
ollama pull SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
ollama pull qwen2.5:7b
```
:::
