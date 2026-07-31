"""Health-check endpoint for API liveness verification."""

from fastapi import APIRouter

from backend.api.schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Reports a minimal service health status.

    Returns:
        Static status payload used by health probes.
    """
    return HealthResponse(status="ok", service="rag-api")
