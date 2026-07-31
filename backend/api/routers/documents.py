"""Document management endpoints for listing and deleting indexed files."""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.dependencies import get_rag_service
from backend.api.schemas import (
    DeleteDocumentRequest,
    DeleteDocumentResponse,
    DocumentsResponse,
)
from backend.api.services import RagApiService


router = APIRouter(tags=["documents"])
logger = logging.getLogger(__name__)


@router.get("/documents", response_model=DocumentsResponse)
def list_documents(
    rag_service: Annotated[RagApiService, Depends(get_rag_service)],
) -> DocumentsResponse:
    """Lists documents currently represented in the vector store.

    Args:
        rag_service: Service dependency exposing document listing operations.

    Returns:
        List of documents with global chunk count.
    """
    started_at = time.perf_counter()
    logger.debug("documents-list-start")
    documents, total_chunks_count = rag_service.list_documents()
    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.debug(
        "documents-list-end documents_count=%s total_chunks_count=%s duration_ms=%.2f",
        len(documents),
        total_chunks_count,
        duration_ms,
    )
    return DocumentsResponse(
        documents=documents,
        total_chunks_count=total_chunks_count,
    )


@router.delete("/documents", response_model=DeleteDocumentResponse)
def delete_document(
    source: Annotated[str, Query(min_length=1)],
    rag_service: Annotated[RagApiService, Depends(get_rag_service)],
) -> DeleteDocumentResponse:
    """Deletes one document by source identifier passed as query parameter.

    Args:
        source: Metadata source value identifying the document.
        rag_service: Service dependency performing deletion.

    Returns:
        Deletion summary for the selected source.
    """
    return _delete_document_by_source(rag_service=rag_service, source=source)


@router.post("/documents/delete", response_model=DeleteDocumentResponse)
def delete_document_with_body(
    request: DeleteDocumentRequest,
    rag_service: Annotated[RagApiService, Depends(get_rag_service)],
) -> DeleteDocumentResponse:
    """Deletes one document by source identifier sent in request body.

    Args:
        request: Payload containing source value.
        rag_service: Service dependency performing deletion.

    Returns:
        Deletion summary for the selected source.
    """
    return _delete_document_by_source(
        rag_service=rag_service,
        source=request.source,
    )


def _delete_document_by_source(
    rag_service: RagApiService,
    source: str,
) -> DeleteDocumentResponse:
    started_at = time.perf_counter()
    logger.info("documents-delete-start source=%s", source)
    result = rag_service.delete_document(source=source)

    if result.deleted_chunks_count == 0:
        logger.warning("documents-delete-not-found source=%s", source)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono dokumentu dla podanego source.",
        )

    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "documents-delete-end source=%s deleted_chunks_count=%s total_chunks_count=%s duration_ms=%.2f",
        source,
        result.deleted_chunks_count,
        result.total_chunks_count,
        duration_ms,
    )

    return result
