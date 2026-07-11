from pathlib import Path
from typing import Callable

import pandas as pd
from docx import Document as DocxDocument
from langchain_core.documents import Document
from pypdf import PdfReader


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
        loader = self._loaders.get(extension)

        if loader is None:
            supported = ", ".join(sorted(self._loaders))
            raise ValueError(
                f"Nieobslugiwany format pliku: {extension}. "
                f"Obslugiwane formaty: {supported}"
            )

        return loader(path)

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
        # Wczytuje plik XLSX i tworzy osobny Document dla kazdego arkusza.
        sheets = pd.read_excel(path, sheet_name=None)
        documents: list[Document] = []

        for sheet_name, dataframe in sheets.items():
            dataframe = dataframe.dropna(how="all").dropna(axis=1, how="all")

            if dataframe.empty:
                continue

            text = dataframe.to_csv(index=False).strip()
            metadata = self._base_metadata(path, file_type="xlsx")
            metadata["sheet_name"] = str(sheet_name)

            documents.append(Document(page_content=text, metadata=metadata))

        return documents

    def _base_metadata(self, path: Path, file_type: str) -> dict[str, str]:
        # Buduje wspolne metadane dodawane do kazdego wczytanego dokumentu.
        return {
            "source": str(path),
            "file_name": path.name,
            "file_type": file_type,
        }
