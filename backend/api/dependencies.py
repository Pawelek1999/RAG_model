"""Dependency providers shared across FastAPI routers."""

from functools import lru_cache
from typing import TYPE_CHECKING

from backend.api.config import settings

if TYPE_CHECKING:
    from backend.api.services import RagApiService


@lru_cache(maxsize=1)
def get_rag_service() -> "RagApiService":
    """Returns a cached RAG service instance for dependency injection.

    Returns:
        Singleton-like service object reused by request handlers.
    """
    from backend.api.services import RagApiService

    return RagApiService(settings=settings)
