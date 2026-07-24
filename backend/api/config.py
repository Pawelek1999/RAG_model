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
        xlsx_loader_mode: str | None = None,
        rag_fact_mode: str | None = None,
        rag_fact_max_items: int | None = None,
        rag_fact_include_raw_snippets: bool | None = None,
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
        self.llm_model = llm_model or os.getenv(
            "OLLAMA_LLM_MODEL", "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
        )
        self.ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL")
        self.default_k = default_k or int(os.getenv("DEFAULT_K", "4"))
        self.xlsx_loader_mode = (xlsx_loader_mode or os.getenv("XLSX_LOADER_MODE", "auto")).strip().lower()
        self.rag_fact_mode = self._normalize_fact_mode(
            rag_fact_mode or os.getenv("RAG_FACT_MODE", "hybrid")
        )
        self.rag_fact_max_items = max(
            1,
            rag_fact_max_items or int(os.getenv("RAG_FACT_MAX_ITEMS", "120")),
        )
        self.rag_fact_include_raw_snippets = self._parse_bool_env(
            rag_fact_include_raw_snippets,
            os.getenv("RAG_FACT_INCLUDE_RAW_SNIPPETS", "true"),
        )

    def _normalize_fact_mode(self, mode: str) -> str:
        normalized = str(mode or "").strip().lower()
        if normalized in {"raw", "structured", "hybrid"}:
            return normalized
        return "hybrid"

    def _parse_bool_env(self, explicit: bool | None, raw: str) -> bool:
        if explicit is not None:
            return explicit

        normalized = str(raw or "").strip().lower()
        return normalized in {"1", "true", "yes", "on"}


settings = ApiSettings()
