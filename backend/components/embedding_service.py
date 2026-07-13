from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings


# Klasa EmbeddingService sluzy do zamiany tekstu albo dokumentow LangChain
# na embeddingi, czyli wektory liczbowe uzywane pozniej przez baze ChromaDB
# do wyszukiwania semantycznego.
class EmbeddingService:
    def __init__(
        self,
        model_name: str = "nomic-embed-text",
        base_url: str | None = None,
    ) -> None:
        # Tworzy klienta embeddingow Ollama dla wybranego lokalnego modelu.
        self.model_name = model_name
        self.base_url = base_url
        kwargs = {"model": model_name}
        if base_url:
            kwargs["base_url"] = base_url
        self.embeddings = OllamaEmbeddings(**kwargs)

    def embed_text(self, text: str) -> list[float]:
        # Zamienia jeden tekst na jeden embedding.
        self._validate_text(text)
        return self.embeddings.embed_query(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        # Zamienia liste tekstow na liste embeddingow.
        self._validate_texts(texts)
        return self.embeddings.embed_documents(texts)

    def embed_documents(self, documents: list[Document]) -> list[list[float]]:
        # Pobiera tekst z dokumentow LangChain i zamienia go na embeddingi.
        if not documents:
            return []

        texts = [document.page_content for document in documents]
        return self.embed_texts(texts)

    def get_embedding_function(self) -> OllamaEmbeddings:
        # Zwraca obiekt embeddingow, ktory mozna przekazac bezposrednio do ChromaDB.
        return self.embeddings

    def _validate_text(self, text: str) -> None:
        # Sprawdza, czy pojedynczy tekst nadaje sie do embeddingu.
        if not text or not text.strip():
            raise ValueError("Tekst do embeddingu nie moze byc pusty")

    def _validate_texts(self, texts: list[str]) -> None:
        # Sprawdza, czy lista tekstow nie jest pusta i nie zawiera pustych wartosci.
        if not texts:
            raise ValueError("Lista tekstow do embeddingu nie moze byc pusta")

        for text in texts:
            self._validate_text(text)
