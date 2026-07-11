from fastapi import APIRouter

from backend.api.schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    # Prosty endpoint do sprawdzania, czy API dziala.
    return HealthResponse(status="ok", service="rag-api")
