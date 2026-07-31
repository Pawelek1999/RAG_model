# RAG_model

Lokalna aplikacja RAG (Retrieval-Augmented Generation) do pracy na wlasnych dokumentach.
Projekt sklada sie z backendu FastAPI (Python) i frontendu React + Tailwind (Vite).

Aplikacja umozliwia:
- indeksowanie dokumentow do ChromaDB,
- zadawanie pytan do czatu RAG opartego o Ollama,
- przegladanie listy dokumentow i zrodel odpowiedzi,
- usuwanie dokumentow z indeksu wektorowego.

## Co robi ten program

1. Przyjmuje pliki (DOCX, PDF, TXT, MD, XLSX).
2. Laduje tresc i dzieli ja na chunki.
3. Tworzy embeddingi i zapisuje dane w ChromaDB.
4. Dla pytania uzytkownika wykonuje retrieval hybrydowy (dense + keyword) i reranking.
5. Przetwarza wyniki przez warstwe Fact Processing (FactPreparationLayer), ktora przygotowuje kontekst w trybie raw, structured albo hybrid.
6. Buduje prompt na podstawie przygotowanego kontekstu i generuje odpowiedz z lokalnego modelu LLM przez Ollama.

## Aktualna architektura

Najwazniejsze katalogi:

```text
RAG_model/
|- backend/
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
|  |  |- document_loader.py
|  |  |- document_chunker.py
|  |  |- embedding_service.py
|  |  |- fact_processing/
|  |  |- rag_application.py
|  |  |- RetrieverService/
|  |  |- VectorStoreManager/
|- frontend/
|  |- src/
|     |- api/ragApi.ts
|     |- components/
|- Docs/
|- chroma_db/
|- docker-compose.yml
```

Kluczowe elementy backendu:
- DocumentLoader: ladowanie i normalizacja plikow do LangChain Document.
- DocumentChunker: podzial na chunki.
- VectorStoreManager: zapis/deduplikacja/wyszukiwanie/usuwanie w Chroma.
- RetrieverService: retrieval hybrydowy i reranking.
- FactPreparationLayer: przygotowanie kontekstu faktowego (structured/hybrid/raw).
- RAGApplication: budowa promptu i zapytanie do modelu przez Ollama.
- RagApiService: spina endpointy API z logika RAG.

## Workflow

### 1) Ingest dokumentu

1. Frontend wysyla plik na POST /ingest.
2. Frontend ustawia X-Upload-Id i pyta o postep GET /ingest/progress/{upload_id}.
3. Backend zapisuje plik do katalogu Docs/ (z unikalna nazwa przy kolizji).
4. DocumentLoader laduje dokument.
5. DocumentChunker dzieli go na chunki.
6. VectorStoreManager zapisuje nowe chunki do ChromaDB (z deduplikacja).
7. Frontend odswieza liste dokumentow.

### 2) Ask (chat RAG)

1. Frontend wysyla POST /ask z question i k.
2. RetrieverService pobiera kandydatow (dense + sparse) i robi rerank.
3. FactPreparationLayer buduje kontekst (raw/structured/hybrid).
4. RAGApplication wywoluje model LLM przez Ollama.
5. API zwraca answer i sources.

### 3) Delete dokumentu

1. Frontend wysyla POST /documents/delete (lub DELETE /documents?source=...).
2. Backend usuwa wszystkie chunki powiazane z danym source.
3. Frontend odswieza liste dokumentow.

## Wymagania

- Python 3.12+
- Node.js 22+
- npm
- Dzialajacy Ollama (lokalnie lub pod wskazanym OLLAMA_BASE_URL)
- Opcjonalnie: Docker + Docker Compose

## Instalacja i uruchomienie

### Opcja A: Docker Compose (najprosciej)

```bash
docker compose up --build
```

Domyslne adresy:
- Frontend: http://127.0.0.1:5173
- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

Uwagi:
- Volume utrwalony jest dla chroma_db.
- Folder Docs nie jest podmontowany jako volume w aktualnym docker-compose.yml.
- Kontenery zakladaja, ze Ollama jest dostepna pod host.docker.internal:11434.

### Opcja B: lokalnie (bez Dockera)

1. Sklonuj repo i przejdz do katalogu projektu.
2. Utworz oraz aktywuj virtualenv backendu.
3. Zainstaluj zaleznosci backendu.
4. Uruchom API FastAPI.
5. Zainstaluj zaleznosci frontendu i uruchom Vite.

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

## Modele Ollama

Minimalnie wymagany embedding model:

```bash
ollama pull nomic-embed-text
```

LLM zalezy od konfiguracji:
- domyslnie w backendzie: SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
- w docker-compose.yml: qwen2.5:7b

W praktyce warto pobrac oba:

```bash
ollama pull SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
ollama pull qwen2.5:7b
```

## Konfiguracja (ENV)

Backend:
- CHROMA_DIRECTORY: katalog bazy wektorowej (domyslnie: ./chroma_db)
- DOCS_DIRECTORY: katalog uploadowanych dokumentow (domyslnie: ./Docs)
- CHROMA_COLLECTION_NAME: nazwa kolekcji Chroma (domyslnie: rag_documents)
- OLLAMA_BASE_URL: adres Ollama, np. http://127.0.0.1:11434
- OLLAMA_EMBEDDING_MODEL: model embeddingow (domyslnie: nomic-embed-text)
- OLLAMA_LLM_MODEL: model czatu LLM
- DEFAULT_K: domyslna liczba chunkow (domyslnie: 4)
- XLSX_LOADER_MODE: auto | standard | test-oriented
- RAG_FACT_MODE: raw | structured | hybrid (domyslnie: hybrid)
- RAG_FACT_MAX_ITEMS: limit rekordow faktowych (domyslnie: 120)
- RAG_FACT_INCLUDE_RAW_SNIPPETS: true/false (domyslnie: true)

Frontend:
- VITE_API_URL: adres backendu (domyslnie: http://127.0.0.1:8000)

## Tryby Fact Processing

Projekt wspiera trzy tryby przygotowania kontekstu dla LLM, sterowane przez RAG_FACT_MODE:

- raw
	- Do modelu trafia surowy kontekst z retrievera (fragmenty dokumentow).
	- Brak dodatkowej struktury faktow i relacji.
	- Przydatny przy ogolnych pytaniach i szybkim prototypowaniu.

- structured
	- Dokumenty sa parsowane do faktow i relacji miedzy nimi.
	- Kontekst zawiera sekcje STRUCTURED_FACTS, FACTS_JSON i RELATIONSHIPS_JSON.
	- Najlepszy do pytan o testy, kroki i powiazania z bugami.

- hybrid (domyslny)
	- Laczy structured z dodatkowymi RAW_SNIPPETS jako fallback.
	- Model najpierw korzysta z faktow/relacji, a surowe fragmenty dopelniaja brakujacy kontekst.
	- Najbardziej uniwersalny tryb do codziennego uzycia.

## API

Domyslny adres API: http://127.0.0.1:8000

### GET /health

Do czego sluzy:
- Prosty healthcheck backendu.

Request:
- Brak parametrow.

Response 200:
- status: ok
- service: rag-api

### GET /documents

Do czego sluzy:
- Zwraca liste dokumentow obecnych w indeksie ChromaDB.

Request:
- Brak parametrow.

Response 200:
- documents: lista obiektow z polami file_name, file_type, source, chunks_count
- total_chunks_count: laczna liczba chunkow we wszystkich dokumentach

### DELETE /documents?source=...

Do czego sluzy:
- Usuwa dokument po polu source (query param).

Request:
- Query param: source (wymagany, niepusty)

Response 200:
- source
- deleted_chunks_count
- total_chunks_count

Typowe bledy:
- 404 gdy nie znaleziono dokumentu dla podanego source.

### POST /documents/delete

Do czego sluzy:
- Alternatywny endpoint usuwania dokumentu (JSON body zamiast query param).

Request body:
- source: string (wymagany)

Response 200:
- source
- deleted_chunks_count
- total_chunks_count

Typowe bledy:
- 404 gdy nie znaleziono dokumentu dla podanego source.

### POST /ingest

Do czego sluzy:
- Upload i indeksowanie pliku do ChromaDB.

Request:
- multipart/form-data
- pole file: UploadFile (wymagane)
- header X-Upload-Id: string (opcjonalny, potrzebny do sledzenia postepu)

Response 200:
- file_name
- documents_count
- chunks_count
- added_chunks_count
- total_chunks_count

Typowe bledy:
- 400 dla pustej nazwy pliku lub nieobslugiwanego rozszerzenia
- 500 dla bledow podczas zapisu/indeksowania

### GET /ingest/progress/{upload_id}

Do czego sluzy:
- Zwraca postep ingestu dla upload_id przekazanego w X-Upload-Id.

Request:
- Path param: upload_id

Response 200:
- upload_id
- progress_percent (0-100)
- stage
- status
- message

Typowe bledy:
- 404 gdy brak postepu dla podanego upload_id (np. bledne ID lub wygasniety wpis).

### POST /ask

Do czego sluzy:
- Przyjmuje pytanie i zwraca odpowiedz RAG wraz ze zrodlami.

Request body:
- question: string (wymagane)
- k: int > 0 (opcjonalne, domyslnie 4)

Response 200:
- answer: string
- sources: lista zrodel (m.in. file_name, file_type, source, page, sheet_name, row_index, status, anomaly, test_sequence_number, chunk_index)

Typowe bledy:
- 400 dla niepoprawnych danych wejsciowych (np. puste pytanie, niepoprawne k).

## Obslugiwane formaty dokumentow

- .docx
- .pdf
- .txt
- .md
- .xlsx

Tryby XLSX:
- standard: klasyczny odczyt arkuszy
- test-oriented: mapowanie wierszy testowych do rekordow semantycznych
- auto: automatyczny wybor trybu na podstawie workbooka

## Przydatne komendy developerskie

Frontend:

```bash
cd frontend
npm run build
npm run lint
npm run preview
```

## Znane ograniczenia

- CLI dziala po zainstalowaniu zaleznosci backendu i dostepnym Ollama; bez tego komendy ingest/chat zwroca bledy importu lub polaczenia.

## Troubleshooting

- Frontend pokazuje API offline: sprawdz GET /health i wartosc VITE_API_URL.
- Brak odpowiedzi z modelu: sprawdz czy Ollama dziala i czy modele sa pobrane.
- Brak wynikow po ingest: sprawdz czy dokument ma tresc i czy chunki zapisaly sie w chroma_db.

