"""Command-line entrypoint for local indexing and chat workflows."""

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.api.config import settings
from backend.components.document_chunker import DocumentChunker
from backend.components.document_loader import DocumentLoader
from backend.components.embedding_service import EmbeddingService
from backend.components.rag_application import RAGApplication
from backend.components.RetrieverService.service import RetrieverService
from backend.components.VectorStoreManager.service import VectorStoreManager


def main() -> None:
    """Parses CLI arguments and executes selected command."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "ingest":
            ingest_document(Path(args.file_path))
        elif args.command == "chat":
            start_chat(k=args.k)
        else:
            parser.print_help()
    except Exception as error:
        print(f"Blad: {error}")


def build_parser() -> argparse.ArgumentParser:
    """Builds CLI parser with ingestion and chat subcommands.

    Returns:
        Configured argparse parser.
    """
    parser = argparse.ArgumentParser(description="Lokalna aplikacja RAG w terminalu")
    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser("ingest", help="Zaindeksuj dokument")
    ingest_parser.add_argument("file_path", help="Sciezka do dokumentu")

    chat_parser = subparsers.add_parser("chat", help="Uruchom czat z RAG")
    chat_parser.add_argument(
        "--k",
        type=int,
        default=4,
        help="Liczba chunkow pobieranych z bazy dla jednego pytania",
    )

    return parser


def ingest_document(file_path: Path) -> None:
    """Loads and indexes one document into ChromaDB.

    Args:
        file_path: Path to a supported input document.
    """
    loader = DocumentLoader(xlsx_mode=settings.xlsx_loader_mode)
    chunker = DocumentChunker()
    embedding_service = EmbeddingService(
        model_name=settings.embedding_model,
        base_url=settings.ollama_base_url,
    )
    vector_store_manager = VectorStoreManager(
        embedding_function=embedding_service.get_embedding_function(),
        persist_directory=settings.chroma_directory,
        collection_name=settings.collection_name,
    )

    documents = loader.load(file_path)
    chunks = chunker.split(documents)
    added_count = vector_store_manager.add_documents(chunks)
    total_count = vector_store_manager.count_documents()

    print(f"Wczytano dokumentow: {len(documents)}")
    print(f"Utworzono chunkow: {len(chunks)}")
    print(f"Dodano nowych chunkow do bazy: {added_count}")
    print(f"Laczna liczba chunkow w bazie: {total_count}")


def start_chat(k: int = 4) -> None:
    """Starts an interactive RAG chat loop using indexed documents.

    Args:
        k: Number of chunks retrieved for each user question.
    """
    embedding_service = EmbeddingService(
        model_name=settings.embedding_model,
        base_url=settings.ollama_base_url,
    )
    vector_store_manager = VectorStoreManager(
        embedding_function=embedding_service.get_embedding_function(),
        persist_directory=settings.chroma_directory,
        collection_name=settings.collection_name,
    )
    retriever_service = RetrieverService(vector_store_manager=vector_store_manager, k=k)
    rag_application = RAGApplication(
        retriever_service=retriever_service,
        model_name=settings.llm_model,
        base_url=settings.ollama_base_url,
    )

    print("Czat RAG uruchomiony. Wpisz 'exit' albo 'quit', aby zakonczyc.")

    while True:
        question = input("\nPytanie: ").strip()

        if question.lower() in {"exit", "quit"}:
            print("Koniec czatu.")
            break

        if not question:
            continue

        answer = rag_application.ask(question)
        print(f"\nOdpowiedz: {answer}")


if __name__ == "__main__":
    main()
