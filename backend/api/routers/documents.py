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


@router.get("/documents", response_model=DocumentsResponse)
def list_documents(
    rag_service: Annotated[RagApiService, Depends(get_rag_service)],
) -> DocumentsResponse:
    # Zwraca liste plikow, ktore maja zapisane chunki w ChromaDB.
    documents, total_chunks_count = rag_service.list_documents()
    return DocumentsResponse(
        documents=documents,
        total_chunks_count=total_chunks_count,
    )


@router.delete("/documents", response_model=DeleteDocumentResponse)
def delete_document(
    source: Annotated[str, Query(min_length=1)],
    rag_service: Annotated[RagApiService, Depends(get_rag_service)],
) -> DeleteDocumentResponse:
    # Usuwa dokument z bazy wektorowej na podstawie pola source.
    return _delete_document_by_source(rag_service=rag_service, source=source)


@router.post("/documents/delete", response_model=DeleteDocumentResponse)
def delete_document_with_body(
    request: DeleteDocumentRequest,
    rag_service: Annotated[RagApiService, Depends(get_rag_service)],
) -> DeleteDocumentResponse:
    # Alternatywny endpoint usuwania dokumentu z JSON body.
    return _delete_document_by_source(
        rag_service=rag_service,
        source=request.source,
    )


def _delete_document_by_source(
    rag_service: RagApiService,
    source: str,
) -> DeleteDocumentResponse:
    result = rag_service.delete_document(source=source)

    if result.deleted_chunks_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono dokumentu dla podanego source.",
        )

    return result
