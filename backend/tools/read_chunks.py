from __future__ import annotations

"""CLI diagnostics tool for inspecting persisted chunks in ChromaDB."""

import argparse
import json
from pathlib import Path
from typing import Any

import chromadb


SEPARATOR = "=" * 60


def parse_args() -> argparse.Namespace:
    """Parses command-line arguments for chunk diagnostics.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(
        description="Diagnostyczny odczyt chunkow z istniejacej bazy ChromaDB (read-only)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Wyswietla tylko pierwsze N chunkow z kazdej kolekcji.",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=None,
        help="Nazwa jednej kolekcji do odczytu.",
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="Zapisz raport do pliku tekstowego, np. --save chunks.txt",
    )
    return parser.parse_args()


def resolve_db_path() -> Path:
    """Resolves ChromaDB directory from common project locations.

    Returns:
        First existing candidate path, or primary default candidate.
    """
    script_path = Path(__file__).resolve()
    candidates = [
        (Path.cwd() / "chroma_db").resolve(),
        (script_path.parents[2] / "chroma_db").resolve(),  # root projektu
        (script_path.parents[1] / "chroma_db").resolve(),  # backend/chroma_db
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def _collection_names(collections: list[Any]) -> list[str]:
    names: list[str] = []
    for item in collections:
        name = getattr(item, "name", None)
        names.append(str(name if name is not None else item))
    return names


def _validate_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if limit <= 0:
        raise ValueError("Parametr --limit musi byc wiekszy od 0.")
    return limit


def _metadata_to_text(metadata: Any) -> str:
    if metadata is None:
        return "{}"
    if isinstance(metadata, dict):
        return json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    return str(metadata)


def build_report(
    client: chromadb.PersistentClient,
    selected_collection: str | None,
    limit: int | None,
) -> tuple[str, int]:
    """Builds text diagnostics report for one or many Chroma collections.

    Args:
        client: Initialized Chroma persistent client.
        selected_collection: Optional single collection name.
        limit: Optional per-collection number of displayed chunks.

    Returns:
        Tuple with report text and process exit code.
    """
    lines: list[str] = []
    exit_code = 0

    lines.append(SEPARATOR)
    lines.append("CHROMADB DIAGNOSTICS")
    lines.append(SEPARATOR)

    collections = client.list_collections()
    collection_names = _collection_names(collections)
    lines.append("Dostepne kolekcje:")

    if not collection_names:
        lines.append("- brak kolekcji")
        lines.append(SEPARATOR)
        lines.append("PODSUMOWANIE")
        lines.append("Liczba kolekcji: 0")
        lines.append("Liczba chunkow: 0")
        lines.append("Srednia dlugosc chunkow: 0.00")
        lines.append("Dlugosc najdluzszego chunka: 0")
        lines.append(SEPARATOR)
        return "\n".join(lines), 0

    for name in collection_names:
        lines.append(f"- {name}")

    selected_names: list[str]
    if selected_collection:
        if selected_collection not in collection_names:
            lines.append(SEPARATOR)
            lines.append(
                f"BLAD: Kolekcja '{selected_collection}' nie istnieje."
            )
            exit_code = 1
            selected_names = []
        else:
            selected_names = [selected_collection]
    else:
        selected_names = collection_names

    lines.append(SEPARATOR)

    total_collections = len(selected_names)
    total_chunks = 0
    total_length = 0
    max_length = 0

    for collection_name in selected_names:
        collection = client.get_collection(name=collection_name)
        count = collection.count()

        lines.append(f"Kolekcja: {collection_name}")
        lines.append(f"Liczba dokumentow (chunks): {count}")

        if count == 0:
            lines.append("INFO: Kolekcja jest pusta.")
            lines.append(SEPARATOR)
            continue

        result = collection.get(include=["documents", "metadatas"])
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []

        available = min(len(ids), len(documents), len(metadatas))
        if available < count:
            lines.append(
                "UWAGA: Niespojne dane kolekcji. "
                f"ids={len(ids)}, documents={len(documents)}, metadatas={len(metadatas)}"
            )

        show_count = available if limit is None else min(limit, available)

        for index in range(show_count):
            doc_text = str(documents[index] or "")
            metadata_text = _metadata_to_text(metadatas[index])
            text_len = len(doc_text)

            total_chunks += 1
            total_length += text_len
            max_length = max(max_length, text_len)

            lines.append(f"Chunk #{index + 1}")
            lines.append(f"ID: {ids[index]}")
            lines.append(f"Dlugosc tekstu: {text_len}")
            lines.append(f"Metadata: {metadata_text}")
            lines.append("Pelna tresc chunka:")
            lines.append(doc_text)
            lines.append(SEPARATOR)

        if show_count == 0:
            lines.append("INFO: Brak chunkow do wyswietlenia po zastosowaniu limitu.")
            lines.append(SEPARATOR)

    average_length = (total_length / total_chunks) if total_chunks else 0.0

    lines.append("PODSUMOWANIE")
    lines.append(f"Liczba kolekcji: {total_collections}")
    lines.append(f"Liczba chunkow: {total_chunks}")
    lines.append(f"Srednia dlugosc chunkow: {average_length:.2f}")
    lines.append(f"Dlugosc najdluzszego chunka: {max_length}")
    lines.append(SEPARATOR)

    return "\n".join(lines), exit_code


def main() -> int:
    """Executes CLI diagnostics flow and returns shell exit code.

    Returns:
        Zero on success, non-zero on validation or connection failures.
    """
    args = parse_args()

    try:
        limit = _validate_limit(args.limit)
    except ValueError as error:
        print(f"BLAD: {error}")
        return 1

    db_path = resolve_db_path()
    if not db_path.exists():
        print("BLAD: Nie znaleziono folderu bazy ChromaDB.")
        print(f"Oczekiwana lokalizacja: {db_path}")
        return 1

    try:
        client = chromadb.PersistentClient(path=str(db_path))
    except Exception as error:
        print(f"BLAD: Nie mozna polaczyc z ChromaDB: {error}")
        return 1

    report, exit_code = build_report(
        client=client,
        selected_collection=args.collection,
        limit=limit,
    )
    print(report)

    if args.save is not None:
        try:
            args.save.parent.mkdir(parents=True, exist_ok=True)
            args.save.write_text(report, encoding="utf-8")
            print(f"Raport zapisano do: {args.save}")
        except Exception as error:
            print(f"BLAD: Nie mozna zapisac raportu: {error}")
            return 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
