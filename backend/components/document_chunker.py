"""Document chunking utilities used before embedding and indexing."""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class DocumentChunker:
    """Splits LangChain documents into overlap-aware chunks for retrieval."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        """Creates a text splitter with validated chunking parameters.

        Args:
            chunk_size: Maximum characters per chunk.
            chunk_overlap: Overlap size shared between adjacent chunks.

        Raises:
            ValueError: If chunking parameters are inconsistent.
        """
        self._validate_settings(chunk_size, chunk_overlap)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, documents: list[Document]) -> list[Document]:
        """Splits a list of documents and enriches chunk metadata.

        Args:
            documents: Source documents to split.

        Returns:
            Chunked documents with chunk index metadata.
        """
        if not documents:
            return []

        chunks = self._splitter.split_documents(documents)
        return self._add_chunk_metadata(chunks)

    def split_one(self, document: Document) -> list[Document]:
        """Splits a single document into chunks.

        Args:
            document: Source document to split.

        Returns:
            Chunked representation of the provided document.
        """
        return self.split([document])

    def _validate_settings(self, chunk_size: int, chunk_overlap: int) -> None:
        # Sprawdza, czy rozmiar chunka i overlap maja poprawne wartosci.
        if chunk_size <= 0:
            raise ValueError("chunk_size musi byc wiekszy od 0")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap nie moze byc mniejszy od 0")

        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap musi byc mniejszy niz chunk_size")

    def _add_chunk_metadata(self, chunks: list[Document]) -> list[Document]:
        # Dodaje do metadanych numer chunka, zachowujac metadane z dokumentu zrodlowego.
        for index, chunk in enumerate(chunks, start=1):
            chunk.metadata["chunk_index"] = index

        return chunks
