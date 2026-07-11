from pathlib import Path

from langchain_core.documents import Document

from backend.api.config import ApiSettings
from backend.api.schemas import DeleteDocumentResponse, DocumentInfo, SourceResponse
from backend.components.document_chunker import DocumentChunker
from backend.components.document_loader import DocumentLoader
from backend.components.embedding_service import EmbeddingService
from backend.components.rag_application import RAGApplication
from backend.components.retriever_service import RetrieverService
from backend.components.vector_store_manager import VectorStoreManager


# Klasa RagApiService laczy endpointy API z istniejacymi klasami backendu RAG.
class RagApiService:
    def __init__(self, settings: ApiSettings) -> None:
        # Buduje wspolne komponenty, ktore moga byc uzywane przez endpointy.
        self.settings = settings
        self.loader = DocumentLoader()
        self.chunker = DocumentChunker()
        self.embedding_service = EmbeddingService(model_name=settings.embedding_model)
        self.vector_store_manager = VectorStoreManager(
            embedding_function=self.embedding_service.get_embedding_function(),
            persist_directory=settings.chroma_directory,
            collection_name=settings.collection_name,
        )
        self.retriever_service = RetrieverService(
            vector_store_manager=self.vector_store_manager,
            k=settings.default_k,
        )
        self.rag_application = RAGApplication(
            retriever_service=self.retriever_service,
            model_name=settings.llm_model,
        )

    def ingest_file(self, file_path: Path) -> dict[str, int | str]:
        # Wczytuje plik, dzieli go na chunki i zapisuje nowe chunki w ChromaDB.
        documents = self.loader.load(file_path)
        chunks = self.chunker.split(documents)
        added_count = self.vector_store_manager.add_documents(chunks)
        total_count = self.vector_store_manager.count_documents()

        return {
            "file_name": file_path.name,
            "documents_count": len(documents),
            "chunks_count": len(chunks),
            "added_chunks_count": added_count,
            "total_chunks_count": total_count,
        }

    def ask(self, question: str, k: int) -> tuple[str, list[SourceResponse]]:
        # Zadaje pytanie do RAG i zwraca odpowiedz razem ze zrodlami.
        documents = self.retriever_service.retrieve(query=question, k=k)
        context = self.retriever_service.format_context(documents)
        sources = self._build_sources(documents)
        answer = self.rag_application.ask_with_context(
            question=question,
            context=context,
        )
        return answer, sources

    def list_documents(self) -> tuple[list[DocumentInfo], int]:
        # Zwraca prosta liste plikow, ktore maja chunki zapisane w ChromaDB.
        result = self.vector_store_manager.vector_store.get(include=["metadatas"])
        metadatas = result.get("metadatas") or []
        documents_by_source: dict[str, dict[str, str | int | None]] = {}

        for metadata in metadatas:
            source = str(metadata.get("source") or "")
            key = source or str(metadata.get("file_name") or "unknown")

            if key not in documents_by_source:
                documents_by_source[key] = {
                    "file_name": metadata.get("file_name"),
                    "file_type": metadata.get("file_type"),
                    "source": source,
                    "chunks_count": 0,
                }

            documents_by_source[key]["chunks_count"] = int(
                documents_by_source[key]["chunks_count"] or 0
            ) + 1

        documents = [
            DocumentInfo(
                file_name=metadata["file_name"],
                file_type=metadata["file_type"],
                source=metadata["source"],
                chunks_count=int(metadata["chunks_count"] or 0),
            )
            for metadata in documents_by_source.values()
        ]

        return documents, self.vector_store_manager.count_documents()

    def supported_extensions(self) -> list[str]:
        # Zwraca formaty plikow obslugiwane przez loader.
        return self.loader.supported_extensions()

    def delete_document(self, source: str) -> DeleteDocumentResponse:
        # Usuwa z ChromaDB wszystkie chunki powiazane z podanym zrodlem.
        deleted_count = self.vector_store_manager.delete_by_source(source)
        total_count = self.vector_store_manager.count_documents()

        return DeleteDocumentResponse(
            source=source,
            deleted_chunks_count=deleted_count,
            total_chunks_count=total_count,
        )

    def _build_sources(self, documents: list[Document]) -> list[SourceResponse]:
        # Zamienia metadane pobranych chunkow na odpowiedz JSON.
        sources: list[SourceResponse] = []
        seen: set[tuple[str | None, int | None, str | None, int | None]] = set()

        for document in documents:
            metadata = document.metadata
            source = SourceResponse(
                file_name=metadata.get("file_name"),
                file_type=metadata.get("file_type"),
                source=metadata.get("source"),
                page=metadata.get("page"),
                sheet_name=metadata.get("sheet_name"),
                chunk_index=metadata.get("chunk_index"),
            )
            key = (source.source, source.page, source.sheet_name, source.chunk_index)

            if key in seen:
                continue

            seen.add(key)
            sources.append(source)

        return sources
