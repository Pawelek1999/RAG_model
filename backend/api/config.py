from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


# Klasa ApiSettings przechowuje podstawowa konfiguracje API i modeli.
class ApiSettings:
    def __init__(
        self,
        chroma_directory: str | Path = BACKEND_ROOT / "chroma_db",
        docs_directory: str | Path = BACKEND_ROOT / "Docs",
        collection_name: str = "rag_documents",
        embedding_model: str = "nomic-embed-text",
        llm_model: str = "qwen2.5:7b",
        default_k: int = 4,
    ) -> None:
        # Ustawia sciezki, nazwy modeli i domyslne parametry wyszukiwania.
        self.chroma_directory = Path(chroma_directory)
        self.docs_directory = Path(docs_directory)
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.default_k = default_k


settings = ApiSettings()
