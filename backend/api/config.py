import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent


# Klasa ApiSettings przechowuje podstawowa konfiguracje API i modeli.
class ApiSettings:
    def __init__(
        self,
        chroma_directory: str | Path | None = None,
        docs_directory: str | Path | None = None,
        collection_name: str | None = None,
        embedding_model: str | None = None,
        llm_model: str | None = None,
        ollama_base_url: str | None = None,
        default_k: int | None = None,
    ) -> None:
        # Ustawia sciezki, nazwy modeli i domyslne parametry wyszukiwania.
        self.chroma_directory = Path(
            chroma_directory
            or os.getenv("CHROMA_DIRECTORY")
            or PROJECT_ROOT / "chroma_db"
        )
        self.docs_directory = Path(
            docs_directory
            or os.getenv("DOCS_DIRECTORY")
            or PROJECT_ROOT / "Docs"
        )
        self.collection_name = collection_name or os.getenv(
            "CHROMA_COLLECTION_NAME",
            "rag_documents",
        )
        self.embedding_model = embedding_model or os.getenv(
            "OLLAMA_EMBEDDING_MODEL",
            "nomic-embed-text",
        )
        self.llm_model = llm_model or os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:7b")
        self.ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL")
        self.default_k = default_k or int(os.getenv("DEFAULT_K", "4"))


settings = ApiSettings()
