from langchain_core.documents import Document

from backend.components.vector_store_manager import VectorStoreManager


# Klasa RetrieverService sluzy do pobierania z ChromaDB najbardziej pasujacych
# chunkow dla pytania uzytkownika. Jest osobna warstwa nad VectorStoreManager,
# zeby logika wyszukiwania byla oddzielona od logiki zapisu bazy.
class RetrieverService:
    def __init__(self, vector_store_manager: VectorStoreManager, k: int = 4) -> None:
        # Ustawia manager bazy wektorowej i domyslna liczbe pobieranych chunkow.
        self._validate_k(k)
        self.vector_store_manager = vector_store_manager
        self.k = k

    def retrieve(self, query: str, k: int | None = None) -> list[Document]:
        # Pobiera liste najbardziej podobnych dokumentow dla pytania.
        self._validate_query(query)
        search_k = k if k is not None else self.k
        self._validate_k(search_k)

        return self.vector_store_manager.similarity_search(query=query, k=search_k)

    def retrieve_context(self, query: str, k: int | None = None) -> str:
        # Pobiera chunki i laczy ich tekst w jeden kontekst do promptu RAG.
        documents = self.retrieve(query=query, k=k)
        return self.format_context(documents)

    def format_context(self, documents: list[Document]) -> str:
        # Zamienia pobrane dokumenty na kontekst bez ponownego wyszukiwania.
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
        # Zwraca natywny retriever LangChain skonfigurowany z wybranym k.
        search_k = k if k is not None else self.k
        self._validate_k(search_k)

        return self.vector_store_manager.get_retriever(k=search_k)

    def _validate_query(self, query: str) -> None:
        # Sprawdza, czy pytanie uzytkownika nie jest puste.
        if not query or not query.strip():
            raise ValueError("Zapytanie nie moze byc puste")

    def _validate_k(self, k: int) -> None:
        # Sprawdza, czy liczba pobieranych chunkow jest poprawna.
        if k <= 0:
            raise ValueError("k musi byc wieksze od 0")
