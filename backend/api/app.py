"""FastAPI application factory and HTTP middleware wiring for the RAG backend."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.api.logging_context import (
    RequestContextFilter,
    get_request_id,
    reset_request_id,
    set_request_id,
)
from backend.api.routers import documents, health, rag


logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configures process-wide logging used by the API runtime.

    The configuration injects request identifiers into log records and reduces
    noise from third-party access logs.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] req=%(request_id)s %(message)s",
    )

    # Zapewnia pole request_id dla kazdego rekordu, nawet gdy filtr loggera nie zostanie wykonany.
    current_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        """Ensures every log record contains request_id used by formatters."""
        record = current_factory(*args, **kwargs)
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return record

    logging.setLogRecordFactory(record_factory)

    context_filter = RequestContextFilter()
    root_logger = logging.getLogger()
    root_logger.addFilter(context_filter)
    for handler in root_logger.handlers:
        handler.addFilter(context_filter)

    # Ogranicza szum z zewnetrznych bibliotek, bo aplikacja loguje requesty sama.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    """Builds and configures the FastAPI application instance.

    Returns:
        Fully configured FastAPI application with middleware and routers.
    """
    configure_logging()

    app = FastAPI(
        title="RAG Database API",
        description="Lokalne API dla backendu RAG opartego o Ollama i ChromaDB.",
        version="0.1.0",
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Logs request lifecycle and attaches X-Request-ID response header."""
        request_id = uuid.uuid4().hex[:8]
        started_at = time.perf_counter()
        token = set_request_id(request_id)
        is_noisy_path = request.url.path.startswith("/ingest/progress/") or request.url.path == "/health"
        log_method = logger.debug if is_noisy_path else logger.info

        log_method(
            "request-start id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.exception(
                "request-error id=%s method=%s path=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            reset_request_id(token)
            raise

        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id
        log_method(
            "request-end id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        reset_request_id(token)
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):517[0-9]$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(rag.router)
    app.include_router(documents.router)

    return app


app = create_app()
