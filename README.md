# RAG_model

Lokalna aplikacja RAG z backendem Python/FastAPI i frontendem React.

Projekt pozwala:
- wrzucac dokumenty do indeksu,
- zadawac pytania do czatu RAG,
- przegladac dokumenty i zrodla odpowiedzi,
- usuwac dokumenty z bazy wektorowej.

## Struktura repo

```text
RAG_model/
|- docker-compose.yml
|- README.md
|- AI/
|- Docs/
|- chroma_db/
|- backend/
|  |- main.py
|  |- requirements.txt
|  |- api/
|  |  |- app.py
|  |  |- config.py
|  |  |- dependencies.py
|  |  |- schemas.py
|  |  |- services.py
|  |  |- routers/
|  |     |- health.py
|  |     |- rag.py
|  |     |- documents.py
|  |- components/
|  |  |- __init__.py
|  |  |- document_loader.py
|  |  |- document_chunker.py
|  |  |- embedding_service.py
|  |  |- rag_application.py
|  |  |- RetrieverService/
|  |  |  |- __init__.py
|  |  |  |- service.py
|  |  |  |- constants.py
|  |  |  |- query_features.py
|  |  |  |- ranking.py
|  |  |- VectorStoreManager/
|  |     |- __init__.py
|  |     |- service.py
|  |     |- search.py
|  |     |- deduplication.py
|  |- tools/
|- frontend/
	|- src/
		|- api/ragApi.ts
		|- components/
```

## Stack

Backend:
- FastAPI
- LangChain
- Ollama
- ChromaDB
- python-docx, pypdf, pandas, openpyxl

Frontend:
- Vite
- React
- TypeScript

## Architektura backendu

Kluczowe klasy:
- `DocumentLoader`: laduje dokumenty (`.docx`, `.pdf`, `.txt`, `.md`, `.xlsx`) i mapuje je na `Document` (LangChain).
- `DocumentChunker`: dzieli dokumenty na chunki.
- `EmbeddingService`: dostarcza embedding function dla Chroma.
- `VectorStoreManager`: zapis, deduplikacja, dense search, keyword search, usuwanie.
- `RetrieverService`: hybrydowy retrieval (dense + sparse) + rerank pod sygnaly testowe.
- `RAGApplication`: buduje prompt i odpytuje model LLM.
- `RagApiService`: spina flow API z komponentami RAG.

### Refaktor components

Po refaktorze logika zostala podzielona na dwa pakiety:
- `backend/components/RetrieverService/`: ekstrakcja cech zapytania, budowanie filtrow, merge kandydatow i reranking.
- `backend/components/VectorStoreManager/`: operacje wyszukiwania (dense/sparse), deduplikacja ID i warstwa serwisowa Chroma.

Aktualnie importy sa juz przepiete bezposrednio na nowe pakiety (`...RetrieverService.service` i `...VectorStoreManager.service`), bez warstwy aliasow.

## Workflow

### 1) Ingest dokumentu

1. Frontend wysyla plik na `POST /ingest`.
2. Frontend przekazuje `X-Upload-Id` i odpytuje `GET /ingest/progress/{upload_id}`.
3. Backend zapisuje plik do `Docs/` (z unikalna nazwa przy kolizji).
4. `DocumentLoader` laduje zawartosc.
5. `DocumentChunker` dzieli na chunki.
6. `VectorStoreManager` zapisuje nowe chunki do ChromaDB.
7. Frontend dostaje finalny status i odswieza liste dokumentow.

### 2) Ask (chat RAG)

1. Frontend wysyla `POST /ask` z `question` i `k`.
2. `RetrieverService` pobiera kandydatow (dense + keyword) i robi rerank.
3. `RagApiService` buduje kontekst + liste zrodel.
4. `RAGApplication` generuje odpowiedz przez Ollama.
5. API zwraca `answer` + `sources`.

### 3) Delete dokumentu

1. Frontend wysyla `POST /documents/delete` z `source`.
2. Backend usuwa powiazane chunki z ChromaDB.
3. Frontend odswieza liste dokumentow.

## API

Domyslnie:
- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

Endpointy:
- `GET /health`
- `GET /documents`
- `DELETE /documents?source=...`
- `POST /documents/delete`
- `POST /ingest`
- `GET /ingest/progress/{upload_id}`
- `POST /ask`

## Modele Ollama

Minimalnie:

```bash
ollama pull nomic-embed-text
```

Model LLM zalezy od konfiguracji:
- lokalnie (domyslnie w kodzie): `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0`
- w `docker-compose.yml`: `qwen2.5:7b`

W praktyce warto pobrac oba:

```bash
ollama pull SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
ollama pull qwen2.5:7b
```

## Konfiguracja (ENV)

Najwazniejsze zmienne:
- `CHROMA_DIRECTORY` (domyslnie: `./chroma_db`)
- `DOCS_DIRECTORY` (domyslnie: `./Docs`)
- `CHROMA_COLLECTION_NAME` (domyslnie: `rag_documents`)
- `OLLAMA_BASE_URL` (np. `http://127.0.0.1:11434`)
- `OLLAMA_EMBEDDING_MODEL` (domyslnie: `nomic-embed-text`)
- `OLLAMA_LLM_MODEL` (lokalnie domyslnie: `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0`)
- `DEFAULT_K` (domyslnie: `4`)
- `XLSX_LOADER_MODE` (`auto`, `standard`, `test-oriented`)
- `VITE_API_URL` (frontend, domyslnie: `http://127.0.0.1:8000`)

## Uruchomienie

### Opcja A: Docker Compose

```bash
docker compose up --build
```

Adresy:
- Frontend: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

Uwaga:
- Compose utrwala `chroma_db` przez volume.
- W obecnym `docker-compose.yml` folder `Docs/` nie jest podmontowany jako volume.

### Opcja B: lokalnie (bez Dockera)

1. Backend:

```bash
python -m venv backend/.venv
backend/.venv/Scripts/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000 --reload
```

2. Frontend:

```bash
cd frontend
npm install
npm run dev
```

## CLI (tryb developerski)

Z katalogu glownego:

```bash
python -m backend.main ingest Docs/plik.docx
python -m backend.main chat --k 4
```

## XLSX i tryb testowy

`DocumentLoader` obsluguje dwa tryby XLSX:
- `standard`: klasyczne odczytanie arkuszy,
- `test-oriented`: mapowanie wierszy testowych do semantycznych rekordow (z metadanymi typu `test_number`, `step_number`, `status`, `anomaly`).

Przy `XLSX_LOADER_MODE=auto` tryb testowy wlacza sie automatycznie dla workbookow zgodnych z formatem testowym.

## Uwagi developerskie

- `Docs/`, `chroma_db/`, `.venv/`, `node_modules/`, `dist/` nie powinny byc commitowane.
- Po zmianach backendu restartuj proces `uvicorn` (gdy nie uruchamiasz z `--reload`).
- Gdy frontend pokazuje API offline, sprawdz `GET /health`.
