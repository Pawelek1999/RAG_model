from pathlib import Path
from shutil import copyfileobj
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.api.config import settings
from backend.api.dependencies import get_rag_service
from backend.api.schemas import AskRequest, AskResponse, IngestResponse
from backend.api.services import RagApiService


router = APIRouter(tags=["rag"])


@router.post("/ask", response_model=AskResponse)
def ask_question(
    request: AskRequest,
    rag_service: Annotated[RagApiService, Depends(get_rag_service)],
) -> AskResponse:
    # Przyjmuje pytanie JSON i zwraca odpowiedz RAG razem ze zrodlami.
    try:
        answer, sources = rag_service.ask(question=request.question, k=request.k)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return AskResponse(answer=answer, sources=sources)


@router.post("/ingest", response_model=IngestResponse)
def ingest_document(
    file: UploadFile = File(...),
    rag_service: Annotated[RagApiService, Depends(get_rag_service)] = None,
) -> IngestResponse:
    # Przyjmuje plik przez API, zapisuje go lokalnie i indeksuje w ChromaDB.
    file_name = Path(file.filename or "").name

    if not file_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brak nazwy pliku.",
        )

    extension = Path(file_name).suffix.lower()
    if extension not in rag_service.supported_extensions():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nieobslugiwany format pliku: {extension}",
        )

    settings.docs_directory.mkdir(parents=True, exist_ok=True)
    saved_path = _build_unique_path(settings.docs_directory, file_name)

    try:
        with saved_path.open("wb") as output_file:
            copyfileobj(file.file, output_file)

        result = rag_service.ingest_file(saved_path)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
    finally:
        file.file.close()

    return IngestResponse(**result)


def _build_unique_path(directory: Path, file_name: str) -> Path:
    # Buduje sciezke, ktora nie nadpisze istniejacego pliku o tej samej nazwie.
    candidate = directory / file_name

    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 1

    while True:
        next_candidate = directory / f"{stem}_{index}{suffix}"

        if not next_candidate.exists():
            return next_candidate

        index += 1
