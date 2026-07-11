from functools import lru_cache
from typing import TYPE_CHECKING

from backend.api.config import settings

if TYPE_CHECKING:
    from backend.api.services import RagApiService


# Tworzy wspolny serwis RAG dla endpointow API.
@lru_cache(maxsize=1)
def get_rag_service() -> "RagApiService":
    from backend.api.services import RagApiService

    return RagApiService(settings=settings)
