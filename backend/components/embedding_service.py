"""Embedding utilities wrapping Ollama embedding models for backend usage."""

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings


class EmbeddingService:
    """Converts text and documents into vector embeddings."""

    def __init__(
        self,
        model_name: str = "nomic-embed-text",
        base_url: str | None = None,
    ) -> None:
        """Initializes embedding client for a selected Ollama model.

        Args:
            model_name: Name of embedding model available in Ollama.
            base_url: Optional Ollama endpoint override.
        """
        self.model_name = model_name
        self.base_url = base_url
        kwargs = {"model": model_name}
        if base_url:
            kwargs["base_url"] = base_url
        self.embeddings = OllamaEmbeddings(**kwargs)

    def embed_text(self, text: str) -> list[float]:
        """Embeds a single text query.

        Args:
            text: Text to embed.

        Returns:
            Dense embedding vector for the text.
        """
        self._validate_text(text)
        return self.embeddings.embed_query(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embeds multiple texts in one call.

        Args:
            texts: Texts to embed.

        Returns:
            Embedding vectors aligned with input order.
        """
        self._validate_texts(texts)
        return self.embeddings.embed_documents(texts)

    def embed_documents(self, documents: list[Document]) -> list[list[float]]:
        """Embeds page content extracted from LangChain documents.

        Args:
            documents: Documents whose page content should be embedded.

        Returns:
            Embedding vectors for all non-empty input documents.
        """
        if not documents:
            return []

        texts = [document.page_content for document in documents]
        return self.embed_texts(texts)

    def get_embedding_function(self) -> OllamaEmbeddings:
        """Returns the underlying embedding function object.

        Returns:
            Ollama embeddings client compatible with Chroma initialization.
        """
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
