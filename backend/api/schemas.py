"""Pydantic request and response schemas exposed by the API layer."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response payload returned by health endpoint."""

    status: str
    service: str


class AskRequest(BaseModel):
    """Request payload for question answering endpoint."""

    question: str = Field(min_length=1)
    k: int = Field(default=4, gt=0)


class SourceResponse(BaseModel):
    """Serialized source metadata describing one supporting context fragment."""

    file_name: str | None = None
    file_type: str | None = None
    source: str | None = None
    page: int | None = None
    sheet_name: str | None = None
    row_index: int | None = None
    row_type: str | None = None
    status: str | None = None
    anomaly: str | None = None
    skip_from_business_flow: bool | None = None
    test_sequence_number: str | None = None
    revision: str | None = None
    chunk_index: int | None = None


class AskResponse(BaseModel):
    """Response payload with generated answer and source list."""

    answer: str
    sources: list[SourceResponse]


class IngestResponse(BaseModel):
    """Response payload summarizing ingestion counters."""

    file_name: str
    documents_count: int
    chunks_count: int
    added_chunks_count: int
    total_chunks_count: int


class IngestProgressResponse(BaseModel):
    """Progress payload for polling document ingestion state."""

    upload_id: str
    progress_percent: int = Field(ge=0, le=100)
    stage: str
    status: str
    message: str


class DocumentInfo(BaseModel):
    """Metadata summary for one indexed document source."""

    file_name: str | None = None
    file_type: str | None = None
    source: str | None = None
    chunks_count: int


class DocumentsResponse(BaseModel):
    """Response payload containing indexed document list and chunk total."""

    documents: list[DocumentInfo]
    total_chunks_count: int


class DeleteDocumentRequest(BaseModel):
    """Request payload for deleting a document by source identifier."""

    source: str = Field(min_length=1)


class DeleteDocumentResponse(BaseModel):
    """Response payload summarizing delete operation outcome."""

    source: str
    deleted_chunks_count: int
    total_chunks_count: int
