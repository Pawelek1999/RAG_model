import logging
import json
from pathlib import Path
from typing import Callable

import pandas as pd
from docx import Document as DocxDocument
from langchain_core.documents import Document
from pypdf import PdfReader


logger = logging.getLogger(__name__)


# Klasa DocumentLoader sluzy do wczytywania plikow z dysku i zamiany ich
# na obiekty Document zgodne z LangChain, ktore pozniej mozna dzielic
# na chunki, embedowac i zapisywac w bazie wektorowej.
class DocumentLoader:
    def __init__(self) -> None:
        # Mapa laczy rozszerzenie pliku z metoda, ktora potrafi go wczytac.
        self._loaders: dict[str, Callable[[Path], list[Document]]] = {
            ".docx": self._load_docx,
            ".pdf": self._load_pdf,
            ".txt": self._load_text,
            ".md": self._load_text,
            ".xlsx": self._load_xlsx,
        }

    def load(self, file_path: str | Path) -> list[Document]:
        # Wczytuje plik, wykrywa jego typ i zwraca liste dokumentow LangChain.
        path = Path(file_path)
        self._validate_file(path)

        extension = path.suffix.lower()
        logger.info("loader-load-start path=%s extension=%s", path, extension)
        loader = self._loaders.get(extension)

        if loader is None:
            supported = ", ".join(sorted(self._loaders))
            raise ValueError(
                f"Nieobslugiwany format pliku: {extension}. "
                f"Obslugiwane formaty: {supported}"
            )

        try:
            documents = loader(path)
            logger.info(
                "loader-load-end path=%s extension=%s documents_count=%s",
                path,
                extension,
                len(documents),
            )
            return documents
        except Exception:
            logger.exception("loader-load-error path=%s extension=%s", path, extension)
            raise

    def supported_extensions(self) -> list[str]:
        # Zwraca liste rozszerzen plikow obslugiwanych przez loader.
        return sorted(self._loaders)

    def _validate_file(self, path: Path) -> None:
        # Sprawdza, czy podana sciezka istnieje i wskazuje na zwykly plik.
        if not path.exists():
            raise FileNotFoundError(f"Plik nie istnieje: {path}")

        if not path.is_file():
            raise ValueError(f"Podana sciezka nie jest plikiem: {path}")

    def _load_docx(self, path: Path) -> list[Document]:
        # Wczytuje tekst z pliku DOCX, laczac niepuste akapity w jeden dokument.
        docx = DocxDocument(path)
        paragraphs = [
            paragraph.text.strip()
            for paragraph in docx.paragraphs
            if paragraph.text.strip()
        ]
        text = "\n".join(paragraphs)

        return [
            Document(
                page_content=text,
                metadata=self._base_metadata(path, file_type="docx"),
            )
        ]

    def _load_pdf(self, path: Path) -> list[Document]:
        # Wczytuje PDF i tworzy osobny Document dla kazdej strony z tekstem.
        reader = PdfReader(path)
        documents: list[Document] = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()

            if not text:
                continue

            metadata = self._base_metadata(path, file_type="pdf")
            metadata["page"] = page_number
            metadata["total_pages"] = len(reader.pages)

            documents.append(Document(page_content=text, metadata=metadata))

        return documents

    def _load_text(self, path: Path) -> list[Document]:
        # Wczytuje zwykly plik tekstowy, na przyklad TXT albo Markdown.
        text = path.read_text(encoding="utf-8").strip()

        return [
            Document(
                page_content=text,
                metadata=self._base_metadata(path, file_type=path.suffix.lower().lstrip(".")),
            )
        ]

    def _load_xlsx(self, path: Path) -> list[Document]:
        # Wczytuje plik XLSX i tworzy osobny Document dla kazdego wiersza arkusza.
        logger.info("loader-xlsx-read-start path=%s engine=openpyxl", path)
        sheets = pd.read_excel(
            path,
            sheet_name=None,
            engine="openpyxl",
            dtype=str,
            keep_default_na=False,
        )
        documents: list[Document] = []

        for sheet_name, dataframe in sheets.items():
            dataframe = dataframe.rename(columns=lambda value: str(value).strip())
            dataframe = dataframe.fillna("")
            dataframe = dataframe.astype(str)
            dataframe = dataframe.apply(lambda column: column.str.strip())
            dataframe = dataframe.loc[
                ~(dataframe.apply(lambda row: all(not str(cell).strip() for cell in row), axis=1))
            ]
            dataframe = dataframe.loc[
                :,
                ~(dataframe.apply(lambda column: all(not str(cell).strip() for cell in column), axis=0)),
            ]

            if dataframe.empty:
                continue

            headers = [str(column).strip() for column in dataframe.columns]

            for row_offset, row_values in enumerate(
                dataframe.to_dict(orient="records"),
                start=2,
            ):
                row_payload = {
                    "sheet_name": str(sheet_name),
                    "headers": headers,
                    "row_number": row_offset,
                    "cells": {
                        header: str(row_values.get(header, "")).strip()
                        for header in headers
                    },
                }
                metadata = self._base_metadata(path, file_type="xlsx")
                metadata["sheet_name"] = str(sheet_name)
                metadata["row_number"] = row_offset
                metadata["excel_row"] = "true"

                documents.append(
                    Document(
                        page_content=json.dumps(row_payload, ensure_ascii=False),
                        metadata=metadata,
                    )
                )

        return documents
    


    def _base_metadata(self, path: Path, file_type: str) -> dict[str, str]:
        # Buduje wspolne metadane dodawane do kazdego wczytanego dokumentu.
        return {
            "source": str(path),
            "file_name": path.name,
            "file_type": file_type,
        }
