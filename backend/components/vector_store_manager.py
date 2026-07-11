import hashlib
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma


# Klasa VectorStoreManager sluzy do tworzenia, ladowania i uzupelniania
# lokalnej bazy wektorowej ChromaDB, w ktorej przechowywane sa chunki
# dokumentow razem z ich embeddingami.
class VectorStoreManager:
    def __init__(
        self,
        embedding_function: Embeddings,
        persist_directory: str | Path = "chroma_db",
        collection_name: str = "rag_documents",
    ) -> None:
        # Ustawia konfiguracje ChromaDB i od razu tworzy albo laduje kolekcje.
        self.embedding_function = embedding_function
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.vector_store = self._load_vector_store()

    def add_documents(self, documents: list[Document]) -> int:
        # Dodaje dokumenty do ChromaDB, pomijajac chunki, ktore juz istnieja.
        if not documents:
            return 0

        ids = [self._create_document_id(document) for document in documents]
        new_documents, new_ids = self._filter_existing_documents(documents, ids)

        if not new_documents:
            return 0

        self.vector_store.add_documents(documents=new_documents, ids=new_ids)
        return len(new_documents)

    def get_retriever(self, k: int = 4):
        # Zwraca retriever LangChain, ktory pobiera k najbardziej podobnych chunkow.
        if k <= 0:
            raise ValueError("k musi byc wieksze od 0")

        return self.vector_store.as_retriever(search_kwargs={"k": k})

    def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        # Wykonuje proste wyszukiwanie semantyczne w ChromaDB.
        if not query or not query.strip():
            raise ValueError("Zapytanie nie moze byc puste")

        if k <= 0:
            raise ValueError("k musi byc wieksze od 0")

        return self.vector_store.similarity_search(query, k=k)

    def count_documents(self) -> int:
        # Zwraca liczbe rekordow zapisanych w kolekcji ChromaDB.
        return self.vector_store._collection.count()

    def delete_by_source(self, source: str) -> int:
        # Usuwa wszystkie chunki, ktore pochodza z podanego zrodla dokumentu.
        if not source or not source.strip():
            raise ValueError("Zrodlo dokumentu nie moze byc puste")

        result = self.vector_store.get(where={"source": source})
        ids = result.get("ids", [])

        if not ids:
            return 0

        self.vector_store.delete(ids=ids)
        return len(ids)

    def _load_vector_store(self) -> Chroma:
        # Tworzy lokalna baze ChromaDB albo laduje ja z katalogu, jesli juz istnieje.
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        return Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedding_function,
            persist_directory=str(self.persist_directory),
        )

    def _filter_existing_documents(
        self,
        documents: list[Document],
        ids: list[str],
    ) -> tuple[list[Document], list[str]]:
        # Porownuje ID chunkow z baza i zostawia tylko te, ktorych jeszcze nie ma.
        existing_ids = set(self._get_existing_ids(ids))
        new_documents: list[Document] = []
        new_ids: list[str] = []

        for document, document_id in zip(documents, ids):
            if document_id in existing_ids:
                continue

            document.metadata["document_id"] = document_id
            new_documents.append(document)
            new_ids.append(document_id)

        return new_documents, new_ids

    def _get_existing_ids(self, ids: list[str]) -> list[str]:
        # Sprawdza w ChromaDB, ktore z podanych ID sa juz zapisane.
        if not ids:
            return []

        result = self.vector_store.get(ids=ids)
        return result.get("ids", [])

    def _create_document_id(self, document: Document) -> str:
        # Tworzy stabilne ID chunka na podstawie zrodla, numeru chunka i tresci.
        source = str(document.metadata.get("source", ""))
        page = str(document.metadata.get("page", ""))
        chunk_index = str(document.metadata.get("chunk_index", ""))
        content = document.page_content

        raw_id = f"{source}|{page}|{chunk_index}|{content}"
        return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
