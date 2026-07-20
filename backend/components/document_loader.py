import logging
import os
from pathlib import Path
from typing import Callable

import pandas as pd
from docx import Document as DocxDocument
from langchain_core.documents import Document
from pypdf import PdfReader

from backend.tools.Excel_tests import ExcelJsonFormatter, ExcelWorkbook, JsonFormattingOptions


logger = logging.getLogger(__name__)


# Klasa DocumentLoader sluzy do wczytywania plikow z dysku i zamiany ich
# na obiekty Document zgodne z LangChain, ktore pozniej mozna dzielic
# na chunki, embedowac i zapisywac w bazie wektorowej.
class DocumentLoader:
    def __init__(self, xlsx_mode: str | None = None) -> None:
        # Mapa laczy rozszerzenie pliku z metoda, ktora potrafi go wczytac.
        self._xlsx_mode = self._normalize_xlsx_mode(
            xlsx_mode or os.getenv("XLSX_LOADER_MODE", "auto")
        )
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
        # Wczytuje plik XLSX i wybiera odpowiedni tryb dla workbooka.
        mode = self._resolve_xlsx_mode(path)
        logger.info("loader-xlsx-read-start path=%s mode=%s", path, mode)

        if mode == "test-oriented":
            return self._load_xlsx_test_oriented(path)

        return self._load_xlsx_standard(path)

    def _load_xlsx_standard(self, path: Path) -> list[Document]:
        # Zachowuje dotychczasowy przeplyw dla zwyklych arkuszy XLSX.
        logger.info("loader-xlsx-standard-read path=%s engine=openpyxl", path)
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
        documents: list[Document] = []

        for sheet_name, dataframe in sheets.items():
            dataframe = dataframe.dropna(how="all").dropna(axis=1, how="all")

            if dataframe.empty:
                continue

            text = dataframe.to_csv(index=False).strip()
            metadata = self._base_metadata(path, file_type="xlsx")
            metadata["sheet_name"] = str(sheet_name)

            documents.append(Document(page_content=text, metadata=metadata))

        logger.info(
            "loader-xlsx-standard-end path=%s sheets_count=%s documents_count=%s",
            path,
            len(sheets),
            len(documents),
        )
        return documents

    def _load_xlsx_test_oriented(self, path: Path) -> list[Document]:
        # Zamienia wiersze testowe na semantyczne Document przed chunkowaniem.
        formatter = ExcelJsonFormatter(options=JsonFormattingOptions())
        payload = formatter.format_workbook(workbook_path=path)
        documents: list[Document] = []
        rows_total = 0
        rows_rejected = 0

        for sheet_payload in payload.get("sheets", []):
            sheet_name = str(sheet_payload.get("sheet_name") or "")
            for row in sheet_payload.get("rows", []):
                rows_total += 1

                if self._is_test_header_row(row):
                    rows_rejected += 1
                    continue

                if row.get("skip_from_business_flow") or row.get("row_type") != "test_step":
                    rows_rejected += 1
                    continue

                page_content = self._build_test_row_content(row)
                if not page_content.strip():
                    rows_rejected += 1
                    continue

                metadata = self._base_metadata(path, file_type="xlsx")
                metadata.update(self._build_test_row_metadata(sheet_name=sheet_name, row=row))

                documents.append(Document(page_content=page_content, metadata=metadata))

        logger.info(
            "loader-xlsx-test-oriented-end path=%s rows_total=%s rows_rejected=%s documents_count=%s",
            path,
            rows_total,
            rows_rejected,
            len(documents),
        )
        return documents

    def _is_test_header_row(self, row: dict[str, object]) -> bool:
        # Chroni indeks przed wczytaniem wiersza naglowkowego jako testu.
        row_index = row.get("row_index")
        if row_index != 1:
            return False

        importance = str(row.get("importance") or "").strip().casefold()
        procedure = str(row.get("procedure") or "").strip().casefold()
        expected_result = str(row.get("expected_result") or "").strip().casefold()

        return importance in {"importance", "nb d'importance", "nb d’importance"} or (
            procedure == "procedure" and expected_result in {"expected result", "expected_result"}
        )

    def _build_test_row_content(self, row: dict[str, object]) -> str:
        # Buduje semantyczny opis jednego wiersza testowego.
        field_labels = [
            ("Test sequence number", row.get("test_sequence_number")),
            ("Revision", row.get("revision")),
            ("Procedure", row.get("procedure")),
            ("Expected result", row.get("expected_result")),
            ("Observed result", row.get("observed_result")),
            ("Conclusion", row.get("conclusion")),
            ("Comment", row.get("comment")),
            ("Status", row.get("status")),
            ("Anomaly", row.get("anomaly")),
        ]

        lines: list[str] = []
        for label, value in field_labels:
            text = str(value or "").strip()
            if not text:
                continue
            lines.append(f"{label}: {text}")

        return "\n".join(lines)

    def _build_test_row_metadata(self, sheet_name: str, row: dict[str, object]) -> dict[str, object]:
        # Przenosi metadane wiersza testowego do warstwy Document.
        return {
            "sheet_name": sheet_name,
            "row_index": row.get("row_index"),
            "row_type": row.get("row_type"),
            "status": row.get("status"),
            "anomaly": row.get("anomaly"),
            "skip_from_business_flow": row.get("skip_from_business_flow"),
            "test_sequence_number": row.get("test_sequence_number"),
            "revision": row.get("revision"),
        }

    def _resolve_xlsx_mode(self, path: Path) -> str:
        # Umozliwia jawny wybor trybu oraz automatyczne wykrycie workbooka testowego.
        if self._xlsx_mode != "auto":
            return self._xlsx_mode

        if self._looks_like_test_workbook(path):
            return "test-oriented"

        return "standard"

    def _looks_like_test_workbook(self, path: Path) -> bool:
        # Wykrywa workbook testowy po naglowku arkusza.
        workbook = ExcelWorkbook.load(path)

        for sheet in workbook.get_all_sheets():
            first_cell = sheet.get_cell(row=1, column=1).as_string().strip().casefold()
            if first_cell in {"importance", "nb d'importance", "nb d’importance"}:
                logger.debug("loader-xlsx-test-detected path=%s sheet=%s", path, sheet.name)
                return True

        return False

    def _normalize_xlsx_mode(self, mode: str) -> str:
        normalized = mode.strip().casefold().replace("_", "-")

        if normalized in {"auto", "standard", "test-oriented", "test"}:
            return "test-oriented" if normalized == "test" else normalized

        logger.warning("loader-xlsx-mode-unknown mode=%s fallback=auto", mode)
        return "auto"

    def _base_metadata(self, path: Path, file_type: str) -> dict[str, str | int | bool | None]:
        # Buduje wspolne metadane dodawane do kazdego wczytanego dokumentu.
        return {
            "source": str(path),
            "file_name": path.name,
            "file_type": file_type,
        }
