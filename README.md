# RAG Database

Lokalna aplikacja RAG z backendem Python/FastAPI i frontendem React. Aplikacja pozwala wgrywac dokumenty, indeksowac je do lokalnej bazy ChromaDB, zadawac pytania w formie chatu i wyswietlac zrodla, z ktorych pochodzi odpowiedz.

Projekt jest budowany jako baza do kolejnych aplikacji: API, panelu dokumentow, chatbota nad prywatnymi danymi albo innych lokalnych narzedzi RAG.

## Aktualny uklad

```text
RAG_database/
+-- backend/
|   +-- api/
|   |   +-- app.py
|   |   +-- config.py
|   |   +-- schemas.py
|   |   +-- services.py
|   |   +-- routers/
|   +-- components/
|   |   +-- document_loader.py
|   |   +-- document_chunker.py
|   |   +-- embedding_service.py
|   |   +-- vector_store_manager.py
|   |   +-- retriever_service.py
|   |   +-- rag_application.py
|   +-- main.py
|   +-- requirements.txt
+-- frontend/
|   +-- src/
|   |   +-- api/
|   |   +-- components/
|   |   +-- App.tsx
+-- Docs/
+-- chroma_db/
+-- docker-compose.yml
+-- README.md
```

`Docs/` przechowuje przeslane dokumenty.  
`chroma_db/` przechowuje lokalna baze wektorowa ChromaDB.  
Oba foldery sa danymi lokalnymi i nie powinny trafiac do GitHuba.

## Glowne technologie

Backend:

- `FastAPI` - warstwa HTTP.
- `LangChain` - obiekty dokumentow, retriever i integracja RAG.
- `Ollama` - lokalne modele LLM i embeddingow.
- `ChromaDB` - lokalna baza wektorowa.
- `python-docx`, `pypdf`, `pandas`, `openpyxl` - odczyt dokumentow.

Frontend:

- `Vite`
- `React`
- `TypeScript`
- `Tailwind CSS`

Modele Ollama:

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

## Komponenty backendu

- `DocumentLoader` - wczytuje pliki i zamienia je na dokumenty LangChain.
- `DocumentChunker` - dzieli dokumenty na chunki.
- `EmbeddingService` - tworzy embeddingi przez model `nomic-embed-text`.
- `VectorStoreManager` - zapisuje, wyszukuje i usuwa chunki w ChromaDB.
- `RetrieverService` - pobiera najbardziej podobne chunki dla pytania.
- `RAGApplication` - buduje prompt i odpytuje lokalny model `qwen2.5:7b`.
- `RagApiService` - laczy endpointy FastAPI z komponentami RAG.

## Workflow aplikacji

```text
1. Uzytkownik otwiera frontend
        |
        v
2. Frontend pobiera liste dokumentow
   GET /documents
        |
        v
3. Uzytkownik wrzuca dokument przez drag and drop
        |
        v
4. Frontend wysyla plik do API
   POST /ingest
        |
        v
5. Backend zapisuje plik w Docs/
        |
        v
6. DocumentLoader wczytuje dokument
        |
        v
7. DocumentChunker dzieli dokument na chunki
        |
        v
8. EmbeddingService tworzy embeddingi przez Ollama
        |
        v
9. VectorStoreManager zapisuje chunki w chroma_db/
        |
        v
10. Frontend odswieza liste dokumentow
    GET /documents
```

Workflow pytania:

```text
1. Uzytkownik wpisuje pytanie w chacie
        |
        v
2. Frontend wysyla JSON do API
   POST /ask
        |
        v
3. RetrieverService szuka podobnych chunkow w ChromaDB
        |
        v
4. RAGApplication buduje prompt z kontekstem
        |
        v
5. Ollama generuje odpowiedz
        |
        v
6. API zwraca odpowiedz i zrodla
        |
        v
7. Frontend pokazuje wiadomosc asystenta oraz liste zrodel
```

Workflow usuwania:

```text
1. Uzytkownik klika "Usun" przy dokumencie
        |
        v
2. Frontend wysyla source dokumentu
   POST /documents/delete
        |
        v
3. Backend usuwa z ChromaDB wszystkie chunki z tym source
        |
        v
4. Frontend odswieza liste dokumentow
```

## API

Domyslny adres API:

```text
http://127.0.0.1:8000
```


### GET /health

Sprawdza, czy API dziala.

Przykladowa odpowiedz:

```json
{
  "status": "ok",
  "service": "rag-api"
}
```

### GET /documents

Zwraca dokumenty zapisane w ChromaDB.

Przykladowa odpowiedz:

```json
{
  "documents": [
    {
      "file_name": "Dane_RAG.docx",
      "file_type": "docx",
      "source": "D:\\Projekty\\RAG_database\\Docs\\Dane_RAG.docx",
      "chunks_count": 7
    }
  ],
  "total_chunks_count": 7
}
```

### POST /ingest

Przyjmuje plik jako `multipart/form-data`, zapisuje go w `Docs/` i indeksuje w ChromaDB.

Jesli plik o tej samej nazwie juz istnieje, backend nie nadpisuje go, tylko tworzy nazwe typu:

```text
plik_1.docx
plik_2.docx
```

Przykladowa odpowiedz:

```json
{
  "file_name": "Dane_RAG.docx",
  "documents_count": 1,
  "chunks_count": 7,
  "added_chunks_count": 7,
  "total_chunks_count": 7
}
```

### POST /ask

Zadaje pytanie do RAG.

Przykladowe zapytanie:

```json
{
  "question": "Kiedy zalozono firme?",
  "k": 4
}
```

Przykladowa odpowiedz:

```json
{
  "answer": "Firma zostala zalozona w 2020 roku.",
  "sources": [
    {
      "file_name": "Dane_RAG.docx",
      "file_type": "docx",
      "source": "D:\\Projekty\\RAG_database\\Docs\\Dane_RAG.docx",
      "page": null,
      "sheet_name": null,
      "chunk_index": 4
    }
  ]
}
```

### POST /documents/delete

Usuwa dokument z ChromaDB po polu `source`.

Przykladowe zapytanie:

```json
{
  "source": "D:\\Projekty\\RAG_database\\Docs\\Dane_RAG.docx"
}
```

Przykladowa odpowiedz:

```json
{
  "source": "D:\\Projekty\\RAG_database\\Docs\\Dane_RAG.docx",
  "deleted_chunks_count": 7,
  "total_chunks_count": 0
}
```

API ma tez endpoint:

```text
DELETE /documents?source=...
```

Frontend uzywa jednak `POST /documents/delete`, bo jest wygodniejszy dla JSON body.

## Frontend

Frontend jest prostym panelem do pracy z API.

Aktualnie zawiera:

- status API,
- drag and drop do uploadu dokumentow,
- liste dokumentow z ChromaDB,
- przycisk usuwania dokumentu,
- chat RAG,
- wyswietlanie zrodel odpowiedzi.

Frontend komunikuje sie z API przez [ragApi.ts](frontend/src/api/ragApi.ts).

Domyslny adres API we frontendzie:

```text
http://127.0.0.1:8000
```

Mozna go zmienic przez zmienna:

```text
VITE_API_URL=http://127.0.0.1:8000
```

## Uruchomienie

### Docker

Najprostsze uruchomienie calej aplikacji:

```bash
docker compose up --build
```

Adresy:

```text
Frontend: http://127.0.0.1:5173
API:      http://127.0.0.1:8000
Swagger:  http://127.0.0.1:8000/docs
```

Compose zaklada, ze Ollama dziala lokalnie poza Dockerem na hoście:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Foldery `Docs/` i `chroma_db/` sa podmontowane jako volume, wiec dokumenty i baza wektorowa zostaja na dysku projektu po zatrzymaniu kontenerow.

### 1. Uruchom Ollama

Upewnij sie, ze Ollama dziala i modele sa pobrane:

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:7b
```

### 2. Uruchom backend API

Z katalogu glownego projektu:

```bash
cd D:\Projekty\RAG_database
.\backend\.venv\Scripts\  --host 127.0.0.1 --port 8000
```

Sprawdzenie:

```text
http://127.0.0.1:8000/health
```

### 3. Uruchom frontend

W drugim terminalu:

```bash
cd D:\Projekty\RAG_database\frontend
npm run dev
```

Adres frontendu:

```text
http://127.0.0.1:5173
```

## CLI

CLI nadal istnieje jako prosty tryb developerski.

Z katalogu `backend`:

```bash
cd D:\Projekty\RAG_database\backend
.\.venv\Scripts\python.exe main.py ingest Docs\plik.docx
.\.venv\Scripts\python.exe main.py chat
```

Albo z katalogu glownego projektu:

```bash
cd D:\Projekty\RAG_database
.\backend\.venv\Scripts\python.exe -m backend.main ingest Docs\plik.docx
.\backend\.venv\Scripts\python.exe -m backend.main chat
```

CLI i API korzystaja z tej samej konfiguracji:

```text
Docs/
chroma_db/
```

## Obslugiwane formaty dokumentow

Aktualnie `DocumentLoader` obsluguje:

- `.docx`
- `.pdf`
- `.txt`
- `.md`
- `.xlsx`

## Zasada odpowiedzi RAG

Model nie powinien odpowiadac z samej wiedzy ogolnej. Najpierw aplikacja pobiera podobne chunki z ChromaDB, a dopiero potem przekazuje je do modelu jako kontekst.

Jesli w dokumentach nie ma odpowiedzi, aplikacja powinna odpowiedziec:

```text
Nie wiem. Nie znalazlem odpowiedzi w dostepnych dokumentach.
```

## Uwagi developerskie

- Po zmianach w backendzie trzeba zrestartowac `uvicorn`.
- Jesli frontend pokazuje `API: offline`, sprawdz czy backend dziala na porcie `8000`.
- Jesli port `8000` jest zajety, sprawdz proces:

```powershell
Get-NetTCPConnection -LocalPort 8000
```

- `Docs/`, `chroma_db/`, `.venv/`, `node_modules/` i `dist/` nie powinny byc commitowane.
