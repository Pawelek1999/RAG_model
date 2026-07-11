from pydantic import BaseModel, Field


# Schemat odpowiedzi health check.
class HealthResponse(BaseModel):
    status: str
    service: str


# Schemat zapytania zadawanego do RAG przez API.
class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    k: int = Field(default=4, gt=0)


# Schemat pojedynczego zrodla zwracanego razem z odpowiedzia.
class SourceResponse(BaseModel):
    file_name: str | None = None
    file_type: str | None = None
    source: str | None = None
    page: int | None = None
    sheet_name: str | None = None
    chunk_index: int | None = None


# Schemat odpowiedzi RAG z trescia i lista zrodel.
class AskResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]


# Schemat odpowiedzi po zaindeksowaniu dokumentu.
class IngestResponse(BaseModel):
    file_name: str
    documents_count: int
    chunks_count: int
    added_chunks_count: int
    total_chunks_count: int


# Schemat informacji o zaindeksowanym pliku.
class DocumentInfo(BaseModel):
    file_name: str | None = None
    file_type: str | None = None
    source: str | None = None
    chunks_count: int


# Schemat listy dokumentow zapisanych w ChromaDB.
class DocumentsResponse(BaseModel):
    documents: list[DocumentInfo]
    total_chunks_count: int


# Schemat zapytania usuwajacego dokument po polu source.
class DeleteDocumentRequest(BaseModel):
    source: str = Field(min_length=1)


# Schemat odpowiedzi po usunieciu dokumentu z ChromaDB.
class DeleteDocumentResponse(BaseModel):
    source: str
    deleted_chunks_count: int
    total_chunks_count: int
