"""RAG endpoints for asking questions, ingesting files, and polling ingest progress."""

import logging
import time
from pathlib import Path
from shutil import copyfileobj
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status

from backend.api.config import settings
from backend.api.dependencies import get_rag_service
from backend.api.schemas import AskRequest, AskResponse, IngestProgressResponse, IngestResponse
from backend.api.services import RagApiService


router = APIRouter(tags=["rag"])
logger = logging.getLogger(__name__)
_INGEST_PROGRESS: dict[str, dict[str, str | int | float]] = {}
_INGEST_PROGRESS_LOCK = Lock()
_INGEST_PROGRESS_TTL_SECONDS = 3600


@router.post("/ask", response_model=AskResponse)
def ask_question(
    request: AskRequest,
    rag_service: Annotated[RagApiService, Depends(get_rag_service)],
) -> AskResponse:
    """Returns an answer and source references for a user question.

    Args:
        request: Question payload with optional retrieval parameters.
        rag_service: Service dependency handling retrieval and generation.

    Returns:
        Answer payload with generated text and traceable sources.

    Raises:
        HTTPException: When the request payload is invalid.
    """
    started_at = time.perf_counter()
    logger.info("ask-start k=%s question_len=%s", request.k, len(request.question))

    try:
        answer, sources = rag_service.ask(question=request.question, k=request.k)
    except ValueError as error:
        logger.warning("ask-validation-error k=%s detail=%s", request.k, error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except Exception:
        logger.exception("ask-error k=%s", request.k)
        raise

    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "ask-end k=%s sources_count=%s answer_len=%s duration_ms=%.2f",
        request.k,
        len(sources),
        len(answer),
        duration_ms,
    )

    return AskResponse(answer=answer, sources=sources)


@router.post("/ingest", response_model=IngestResponse)
def ingest_document(
    file: UploadFile = File(...),
    x_upload_id: Annotated[str | None, Header()] = None,
    rag_service: Annotated[RagApiService, Depends(get_rag_service)] = None,
) -> IngestResponse:
    """Uploads and indexes a document in the vector store.

    Args:
        file: Uploaded file stream.
        x_upload_id: Optional tracking identifier used by progress polling.
        rag_service: Service dependency responsible for indexing.

    Returns:
        Ingestion summary with document and chunk counters.

    Raises:
        HTTPException: When validation or indexing fails.
    """
    started_at = time.perf_counter()
    file_name = Path(file.filename or "").name
    logger.info("ingest-start file_name=%s", file_name or "<empty>")
    _update_ingest_progress(
        upload_id=x_upload_id,
        percent=5,
        stage="starting",
        status="processing",
        message="Startuje przetwarzanie zadania",
    )

    if not file_name:
        logger.warning("ingest-validation-error missing file name")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brak nazwy pliku.",
        )

    extension = Path(file_name).suffix.lower()
    logger.info("ingest-extension file_name=%s extension=%s", file_name, extension)
    _update_ingest_progress(
        upload_id=x_upload_id,
        percent=10,
        stage="validation",
        status="processing",
        message="Waliduje rozszerzenie pliku",
    )
    if extension not in rag_service.supported_extensions():
        logger.warning("ingest-validation-error unsupported extension=%s", extension)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nieobslugiwany format pliku: {extension}",
        )

    settings.docs_directory.mkdir(parents=True, exist_ok=True)
    saved_path = _build_unique_path(settings.docs_directory, file_name)
    logger.info("ingest-save-path file_name=%s saved_path=%s", file_name, saved_path)
    _update_ingest_progress(
        upload_id=x_upload_id,
        percent=20,
        stage="saving",
        status="processing",
        message="Zapisuje plik na dysku",
    )

    def report_service_progress(service_percent: int, service_message: str) -> None:
        """Maps service-level progress into API-level progress percentages."""
        mapped_percent = 20 + int(service_percent * 0.75)
        _update_ingest_progress(
            upload_id=x_upload_id,
            percent=min(mapped_percent, 95),
            stage="processing",
            status="processing",
            message=service_message,
        )

    try:
        with saved_path.open("wb") as output_file:
            copyfileobj(file.file, output_file)

        _update_ingest_progress(
            upload_id=x_upload_id,
            percent=25,
            stage="processing",
            status="processing",
            message="Rozpoczynam indeksowanie dokumentu",
        )

        result = rag_service.ingest_file(saved_path, on_progress=report_service_progress)

        _update_ingest_progress(
            upload_id=x_upload_id,
            percent=100,
            stage="completed",
            status="completed",
            message="Dokument gotowy do pracy",
        )
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "ingest-end file_name=%s documents_count=%s chunks_count=%s added_chunks_count=%s total_chunks_count=%s duration_ms=%.2f",
            result["file_name"],
            result["documents_count"],
            result["chunks_count"],
            result["added_chunks_count"],
            result["total_chunks_count"],
            duration_ms,
        )
    except Exception as error:
        _update_ingest_progress(
            upload_id=x_upload_id,
            percent=100,
            stage="failed",
            status="failed",
            message=f"Blad podczas indeksowania: {error}",
        )
        logger.exception("ingest-error file_name=%s saved_path=%s", file_name, saved_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        ) from error
    finally:
        file.file.close()

    return IngestResponse(**result)


@router.get("/ingest/progress/{upload_id}", response_model=IngestProgressResponse)
def get_ingest_progress(upload_id: str) -> IngestProgressResponse:
    """Returns current ingestion progress for a previously started upload.

    Args:
        upload_id: Upload identifier provided during ingestion.

    Returns:
        Progress snapshot for the upload.

    Raises:
        HTTPException: When no progress entry exists for the identifier.
    """
    progress = _get_ingest_progress(upload_id)

    if progress is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono postepu dla podanego upload_id.",
        )

    return IngestProgressResponse(
        upload_id=upload_id,
        progress_percent=int(progress["progress_percent"]),
        stage=str(progress["stage"]),
        status=str(progress["status"]),
        message=str(progress["message"]),
    )


def _build_unique_path(directory: Path, file_name: str) -> Path:
    # Buduje sciezke, ktora nie nadpisze istniejacego pliku o tej samej nazwie.
    candidate = directory / file_name

    if not candidate.exists():
        logger.info("ingest-path-selected path=%s", candidate)
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 1

    while True:
        next_candidate = directory / f"{stem}_{index}{suffix}"

        if not next_candidate.exists():
            logger.info("ingest-path-collision-resolved path=%s", next_candidate)
            return next_candidate

        index += 1


def _update_ingest_progress(
    upload_id: str | None,
    percent: int,
    stage: str,
    status: str,
    message: str,
) -> None:
    if not upload_id:
        return

    now = time.time()
    with _INGEST_PROGRESS_LOCK:
        _cleanup_old_progress_locked(now)
        _INGEST_PROGRESS[upload_id] = {
            "progress_percent": max(0, min(100, percent)),
            "stage": stage,
            "status": status,
            "message": message,
            "updated_at": now,
        }


def _get_ingest_progress(upload_id: str) -> dict[str, str | int | float] | None:
    now = time.time()
    with _INGEST_PROGRESS_LOCK:
        _cleanup_old_progress_locked(now)
        return _INGEST_PROGRESS.get(upload_id)


def _cleanup_old_progress_locked(now: float) -> None:
    expired_ids = [
        upload_id
        for upload_id, progress in _INGEST_PROGRESS.items()
        if now - float(progress.get("updated_at", now)) > _INGEST_PROGRESS_TTL_SECONDS
    ]
    for upload_id in expired_ids:
        _INGEST_PROGRESS.pop(upload_id, None)
