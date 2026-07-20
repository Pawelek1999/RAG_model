import logging
import time
from pathlib import Path
from typing import Callable

from langchain_core.documents import Document

from backend.api.config import ApiSettings
from backend.api.schemas import DeleteDocumentResponse, DocumentInfo, SourceResponse
from backend.components.document_chunker import DocumentChunker
from backend.components.document_loader import DocumentLoader
from backend.components.embedding_service import EmbeddingService
from backend.components.rag_application import RAGApplication
from backend.components.retriever_service import RetrieverService
from backend.components.vector_store_manager import VectorStoreManager


logger = logging.getLogger(__name__)


# Klasa RagApiService laczy endpointy API z istniejacymi klasami backendu RAG.
class RagApiService:
    def __init__(self, settings: ApiSettings) -> None:
        # Buduje wspolne komponenty, ktore moga byc uzywane przez endpointy.
        self.settings = settings
        self.loader = DocumentLoader(xlsx_mode=settings.xlsx_loader_mode)
        self.chunker = DocumentChunker()
        self.embedding_service = EmbeddingService(
            model_name=settings.embedding_model,
            base_url=settings.ollama_base_url,
        )
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
            base_url=settings.ollama_base_url,
        )

    def ingest_file(
        self,
        file_path: Path,
        on_progress: Callable[[int, str], None] | None = None,
    ) -> dict[str, int | str]:
        # Wczytuje plik, dzieli go na chunki i zapisuje nowe chunki w ChromaDB.
        started_at = time.perf_counter()
        logger.info("service-ingest-start file_path=%s", file_path)
        if on_progress:
            on_progress(20, "Wczytuje dokument")
        documents = self.loader.load(file_path)
        logger.debug(
            "service-ingest-loaded file_path=%s documents_before_chunking=%s",
            file_path,
            len(documents),
        )
        if on_progress:
            on_progress(45, "Dzieli dokument na chunki")
        chunks = self.chunker.split(documents)
        logger.debug(
            "service-ingest-chunked file_path=%s documents_before_chunking=%s chunks_after_chunking=%s",
            file_path,
            len(documents),
            len(chunks),
        )
        if on_progress:
            on_progress(70, "Zapisuje chunki w ChromaDB")
        added_count = self.vector_store_manager.add_documents(chunks)
        if on_progress:
            on_progress(90, "Finalizuje indeksowanie")
        total_count = self.vector_store_manager.count_documents()
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "service-ingest-end file_path=%s documents_count=%s chunks_count=%s added_chunks_count=%s total_chunks_count=%s duration_ms=%.2f",
            file_path,
            len(documents),
            len(chunks),
            added_count,
            total_count,
            duration_ms,
        )
        if on_progress:
            on_progress(100, "Dokument gotowy do uzycia")

        return {
            "file_name": file_path.name,
            "documents_count": len(documents),
            "chunks_count": len(chunks),
            "added_chunks_count": added_count,
            "total_chunks_count": total_count,
        }

    def ask(self, question: str, k: int) -> tuple[str, list[SourceResponse]]:
        # Zadaje pytanie do RAG i zwraca odpowiedz razem ze zrodlami.
        started_at = time.perf_counter()
        logger.debug("service-ask-start k=%s question_len=%s", k, len(question))
        documents = self.retriever_service.retrieve(query=question, k=k)
        logger.debug("service-ask-retrieved k=%s documents_count=%s", k, len(documents))
        context = self.retriever_service.format_context(documents)
        sources = self._build_sources(documents)
        answer = self.rag_application.ask_with_context(
            question=question,
            context=context,
        )
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "service-ask-end k=%s sources_count=%s answer_len=%s duration_ms=%.2f",
            k,
            len(sources),
            len(answer),
            duration_ms,
        )
        return answer, sources

    def list_documents(self) -> tuple[list[DocumentInfo], int]:
        # Zwraca prosta liste plikow, ktore maja chunki zapisane w ChromaDB.
        logger.debug("service-list-documents-start")
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

        total_chunks_count = self.vector_store_manager.count_documents()
        logger.debug(
            "service-list-documents-end documents_count=%s total_chunks_count=%s",
            len(documents),
            total_chunks_count,
        )
        return documents, total_chunks_count

    def supported_extensions(self) -> list[str]:
        # Zwraca formaty plikow obslugiwane przez loader.
        return self.loader.supported_extensions()

    def delete_document(self, source: str) -> DeleteDocumentResponse:
        # Usuwa z ChromaDB wszystkie chunki powiazane z podanym zrodlem.
        logger.info("service-delete-document-start source=%s", source)
        deleted_count = self.vector_store_manager.delete_by_source(source)
        total_count = self.vector_store_manager.count_documents()
        logger.info(
            "service-delete-document-end source=%s deleted_chunks_count=%s total_chunks_count=%s",
            source,
            deleted_count,
            total_count,
        )

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
                row_index=metadata.get("row_index"),
                row_type=metadata.get("row_type"),
                status=metadata.get("status"),
                anomaly=metadata.get("anomaly"),
                skip_from_business_flow=metadata.get("skip_from_business_flow"),
                test_sequence_number=metadata.get("test_sequence_number"),
                revision=metadata.get("revision"),
                chunk_index=metadata.get("chunk_index"),
            )
            key = (source.source, source.page, source.sheet_name, source.row_index, source.chunk_index)

            if key in seen:
                continue

            seen.add(key)
            sources.append(source)

        return sources
