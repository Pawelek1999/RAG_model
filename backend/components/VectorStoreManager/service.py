"""Vector store manager responsible for persistence and retrieval primitives."""

import logging
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from backend.components.VectorStoreManager.deduplication import (
    create_document_id,
    filter_existing_documents,
)
from backend.components.VectorStoreManager.search import (
    keyword_search as execute_keyword_search,
)
from backend.components.VectorStoreManager.search import (
    similarity_search as execute_similarity_search,
)


logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Wraps Chroma operations used by ingestion and retrieval services."""

    def __init__(
        self,
        embedding_function: Embeddings,
        persist_directory: str | Path = "chroma_db",
        collection_name: str = "rag_documents",
    ) -> None:
        """Initializes persistent vector store connection.

        Args:
            embedding_function: Embedding function required by Chroma.
            persist_directory: Directory used to persist vector data.
            collection_name: Collection name used for document storage.
        """
        self.embedding_function = embedding_function
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.vector_store = self._load_vector_store()

    def add_documents(self, documents: list[Document]) -> int:
        """Adds non-duplicate documents to the vector collection.

        Args:
            documents: Documents to index.

        Returns:
            Number of newly added documents.
        """
        if not documents:
            logger.debug("vector-add-skip-empty-documents")
            return 0

        ids = [create_document_id(document) for document in documents]
        new_documents, new_ids = filter_existing_documents(
            vector_store=self.vector_store,
            documents=documents,
            ids=ids,
        )
        logger.debug(
            "vector-add-dedup planned_ids=%s new_ids=%s existing_ids=%s",
            len(ids),
            len(new_ids),
            len(ids) - len(new_ids),
        )

        if not new_documents:
            logger.debug("vector-add-skip-no-new-documents")
            return 0

        self.vector_store.add_documents(documents=new_documents, ids=new_ids)
        logger.info("vector-add-end added_count=%s", len(new_documents))
        return len(new_documents)

    def get_retriever(self, k: int = 4):
        """Builds LangChain retriever configured with top-k retrieval.

        Args:
            k: Number of chunks returned by retriever.

        Returns:
            LangChain retriever instance.

        Raises:
            ValueError: When k is not greater than zero.
        """
        if k <= 0:
            raise ValueError("k musi byc wieksze od 0")

        return self.vector_store.as_retriever(search_kwargs={"k": k})

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Executes semantic similarity search over indexed documents.

        Args:
            query: Query text.
            k: Maximum number of results.
            metadata_filter: Optional metadata predicate.

        Returns:
            Retrieved documents.
        """
        return execute_similarity_search(
            vector_store=self.vector_store,
            query=query,
            k=k,
            metadata_filter=metadata_filter,
        )

    def keyword_search(
        self,
        query_terms: list[str],
        k: int = 20,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Executes keyword-based search over stored documents.

        Args:
            query_terms: Normalized keyword list.
            k: Maximum number of results.
            metadata_filter: Optional metadata predicate.

        Returns:
            Ranked documents matching keyword criteria.
        """
        return execute_keyword_search(
            vector_store=self.vector_store,
            query_terms=query_terms,
            k=k,
            metadata_filter=metadata_filter,
        )

    def get_documents_by_metadata(
        self,
        metadata_filter: dict[str, Any],
        k: int = 100,
    ) -> list[Document]:
        """Fetches documents by metadata filter without semantic scoring.

        Args:
            metadata_filter: Metadata predicate used by Chroma.
            k: Maximum number of returned documents.

        Returns:
            Matching documents reconstructed from stored payloads.
        """
        if k <= 0:
            raise ValueError("k musi byc wieksze od 0")

        if not metadata_filter:
            return []

        result = self.vector_store.get(
            where=metadata_filter,
            include=["documents", "metadatas"],
        )
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []

        resolved: list[Document] = []
        for content, metadata in zip(documents, metadatas):
            resolved.append(
                Document(
                    page_content=str(content or ""),
                    metadata=dict(metadata or {}),
                )
            )

        return resolved[:k]

    def count_documents(self) -> int:
        """Returns the number of stored document chunks."""
        count = self.vector_store._collection.count()
        logger.debug("vector-count count=%s", count)
        return count

    def delete_by_source(self, source: str) -> int:
        """Deletes all stored chunks for one source path.

        Args:
            source: Source metadata value.

        Returns:
            Number of deleted chunks.

        Raises:
            ValueError: When source value is empty.
        """
        if not source or not source.strip():
            raise ValueError("Zrodlo dokumentu nie moze byc puste")

        result = self.vector_store.get(where={"source": source})
        ids = result.get("ids", [])
        logger.debug("vector-delete-start source=%s ids_count=%s", source, len(ids))

        if not ids:
            logger.debug("vector-delete-skip-no-ids source=%s", source)
            return 0

        self.vector_store.delete(ids=ids)
        logger.info("vector-delete-end source=%s deleted_count=%s", source, len(ids))
        return len(ids)

    def _load_vector_store(self) -> Chroma:
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        return Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedding_function,
            persist_directory=str(self.persist_directory),
        )
