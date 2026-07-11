from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import documents, health, rag


# Tworzy aplikacje FastAPI i podpina wszystkie routery API.
def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Database API",
        description="Lokalne API dla backendu RAG opartego o Ollama i ChromaDB.",
        version="0.1.0",
    )

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
