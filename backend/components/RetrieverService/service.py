import logging

from langchain_core.documents import Document

from backend.components.RetrieverService.query_features import (
    build_metadata_filter,
    build_sparse_terms,
    extract_query_features,
)
from backend.components.RetrieverService.ranking import merge_candidates, rerank_documents
from backend.components.VectorStoreManager.service import VectorStoreManager


logger = logging.getLogger(__name__)


class RetrieverService:
    def __init__(self, vector_store_manager: VectorStoreManager, k: int = 4) -> None:
        self._validate_k(k)
        self.vector_store_manager = vector_store_manager
        self.k = k

    def retrieve(self, query: str, k: int | None = None) -> list[Document]:
        self._validate_query(query)
        search_k = k if k is not None else self.k
        self._validate_k(search_k)

        query_features = extract_query_features(query)
        metadata_filter = build_metadata_filter(query_features)
        sparse_terms = build_sparse_terms(query_features)

        logger.info("retriever-start query_len=%s k=%s", len(query), search_k)
        candidates_k = max(search_k, search_k * 6)

        if query_features.intent in {"LIST_BUGS", "AFFECTED_TEST_FULL"}:
            candidates_k = max(candidates_k, 60)

        dense_candidates = self.vector_store_manager.similarity_search(
            query=query,
            k=candidates_k,
            metadata_filter=metadata_filter,
        )
        if metadata_filter and not dense_candidates:
            logger.debug("retriever-dense-fallback-no-filter")
            dense_candidates = self.vector_store_manager.similarity_search(query=query, k=candidates_k)

        sparse_candidates = self.vector_store_manager.keyword_search(
            query_terms=sparse_terms,
            k=candidates_k,
            metadata_filter=metadata_filter,
        )
        if metadata_filter and not sparse_candidates and sparse_terms:
            logger.debug("retriever-sparse-fallback-no-filter")
            sparse_candidates = self.vector_store_manager.keyword_search(
                query_terms=sparse_terms,
                k=candidates_k,
            )

        candidates = merge_candidates(
            dense_documents=dense_candidates,
            sparse_documents=sparse_candidates,
            query_features=query_features,
        )
        documents = rerank_documents(
            documents=candidates,
            top_k=search_k,
            query_features=query_features,
        )

        logger.info(
            "retriever-end k=%s dense_candidates=%s sparse_candidates=%s merged_candidates=%s documents_count=%s",
            search_k,
            len(dense_candidates),
            len(sparse_candidates),
            len(candidates),
            len(documents),
        )
        return documents

    def retrieve_context(self, query: str, k: int | None = None) -> str:
        documents = self.retrieve(query=query, k=k)
        return self.format_context(documents)

    def retrieve_by_metadata(
        self,
        metadata_filter: dict[str, object],
        k: int | None = None,
    ) -> list[Document]:
        search_k = k if k is not None else self.k
        self._validate_k(search_k)
        return self.vector_store_manager.get_documents_by_metadata(
            metadata_filter=metadata_filter,
            k=search_k,
        )

    def format_context(self, documents: list[Document]) -> str:
        if not documents:
            return ""

        chunks = []
        for index, document in enumerate(documents, start=1):
            source = document.metadata.get("source", "brak zrodla")
            page = document.metadata.get("page")
            header = f"[Fragment {index} | zrodlo: {source}"

            if page is not None:
                header += f" | strona: {page}"

            header += "]"
            chunks.append(f"{header}\n{document.page_content}")

        return "\n\n".join(chunks)

    def get_retriever(self, k: int | None = None):
        search_k = k if k is not None else self.k
        self._validate_k(search_k)
        return self.vector_store_manager.get_retriever(k=search_k)

    def _validate_query(self, query: str) -> None:
        if not query or not query.strip():
            raise ValueError("Zapytanie nie moze byc puste")

    def _validate_k(self, k: int) -> None:
        if k <= 0:
            raise ValueError("k musi byc wieksze od 0")
