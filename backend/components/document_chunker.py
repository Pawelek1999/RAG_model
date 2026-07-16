import json
import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Klasa DocumentChunker sluzy do dzielenia dokumentow LangChain na mniejsze
# fragmenty tekstu, ktore pozniej mozna zamienic na embeddingi i zapisac
# w bazie wektorowej.
class DocumentChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        # Ustawia parametry dzielenia tekstu i tworzy splitter LangChain.
        self._validate_settings(chunk_size, chunk_overlap)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, documents: list[Document]) -> list[Document]:
        # Dzieli liste dokumentow na chunki i zwraca liste nowych Document.
        if not documents:
            return []

        if self._looks_like_excel_rows(documents):
            excel_chunks = self._split_excel_documents(documents)
            if excel_chunks:
                return self._add_chunk_metadata(excel_chunks)

        chunks = self._splitter.split_documents(documents)
        return self._add_chunk_metadata(chunks)

    def split_one(self, document: Document) -> list[Document]:
        # Dzieli jeden dokument na chunki.
        return self.split([document])

    def _validate_settings(self, chunk_size: int, chunk_overlap: int) -> None:
        # Sprawdza, czy rozmiar chunka i overlap maja poprawne wartosci.
        if chunk_size <= 0:
            raise ValueError("chunk_size musi byc wiekszy od 0")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap nie moze byc mniejszy od 0")

        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap musi byc mniejszy niz chunk_size")

    def _add_chunk_metadata(self, chunks: list[Document]) -> list[Document]:
        # Dodaje do metadanych numer chunka, zachowujac metadane z dokumentu zrodlowego.
        for index, chunk in enumerate(chunks, start=1):
            chunk.metadata["chunk_index"] = index

        return chunks

    def _looks_like_excel_rows(self, documents: list[Document]) -> bool:
        for document in documents:
            file_type = str(document.metadata.get("file_type", "")).lower()
            excel_row = str(document.metadata.get("excel_row", "")).lower()
            if file_type == "xlsx" or excel_row == "true":
                return True
        return False

    def _split_excel_documents(self, documents: list[Document]) -> list[Document]:
        rows = []
        for document in documents:
            parsed_row = self._parse_excel_row_document(document)
            if parsed_row is None:
                continue
            rows.append(parsed_row)

        if not rows:
            return []

        scenario_groups = self._group_rows_by_scenario(rows)
        chunks: list[Document] = []

        for _, grouped_rows in scenario_groups.items():
            chunks.extend(self._build_scenario_chunk_documents(grouped_rows))

        traceability_rows = [
            row for row in rows if self._is_traceability_row(row)
        ]
        for row in traceability_rows:
            chunks.extend(self._build_traceability_chunk_documents(row))

        return chunks

    def _parse_excel_row_document(self, document: Document) -> dict[str, object] | None:
        try:
            payload = json.loads(document.page_content)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        raw_cells = payload.get("cells")
        if not isinstance(raw_cells, dict):
            return None

        cells: dict[str, str] = {}
        for header, value in raw_cells.items():
            header_text = str(header).strip()
            if not header_text:
                continue
            cells[header_text] = str(value or "").strip()

        if not cells:
            return None

        sheet_name = str(payload.get("sheet_name") or document.metadata.get("sheet_name") or "")
        row_number = int(payload.get("row_number") or document.metadata.get("row_number") or 0)

        normalized_cells = {
            self._normalize_key(header): (header, value)
            for header, value in cells.items()
        }

        test_case_id, test_case_header = self._find_value_with_header(normalized_cells, self._test_case_aliases())
        requirement_id, requirement_header = self._find_value_with_header(
            normalized_cells,
            self._requirement_aliases(),
        )
        bug_id, bug_header = self._find_value_with_header(normalized_cells, self._bug_aliases())

        line_number, line_header = self._find_value_with_header(normalized_cells, self._line_aliases())
        procedure, procedure_header = self._find_value_with_header(normalized_cells, self._procedure_aliases())
        expected_result, expected_header = self._find_value_with_header(
            normalized_cells,
            self._expected_result_aliases(),
        )
        observed_result, observed_header = self._find_value_with_header(
            normalized_cells,
            self._observed_result_aliases(),
        )
        comments, comments_header = self._find_value_with_header(normalized_cells, self._comments_aliases())
        conclusion, conclusion_header = self._find_value_with_header(
            normalized_cells,
            self._conclusion_aliases(),
        )

        test_suite, suite_header = self._find_value_with_header(normalized_cells, self._suite_aliases())
        revision, revision_header = self._find_value_with_header(normalized_cells, self._revision_aliases())
        mode, mode_header = self._find_value_with_header(normalized_cells, self._mode_aliases())
        description, description_header = self._find_value_with_header(
            normalized_cells,
            self._description_aliases(),
        )
        preconditions, preconditions_header = self._find_value_with_header(
            normalized_cells,
            self._preconditions_aliases(),
        )

        return {
            "source": str(document.metadata.get("source", "")),
            "file_name": str(document.metadata.get("file_name", "")),
            "sheet_name": sheet_name,
            "row_number": row_number,
            "cells": cells,
            "headers": list(cells.keys()),
            "test_case_id": self._first_non_empty(test_case_id, self._extract_test_case_id(cells)),
            "test_case_header": test_case_header,
            "requirement_id": self._first_non_empty(requirement_id, self._extract_requirement_id(cells)),
            "requirement_header": requirement_header,
            "bug_id": self._first_non_empty(bug_id, self._extract_bug_id(cells)),
            "bug_header": bug_header,
            "line_number": line_number,
            "line_header": line_header,
            "procedure": procedure,
            "procedure_header": procedure_header,
            "expected_result": expected_result,
            "expected_header": expected_header,
            "observed_result": observed_result,
            "observed_header": observed_header,
            "comments": comments,
            "comments_header": comments_header,
            "conclusion": conclusion,
            "conclusion_header": conclusion_header,
            "test_suite": test_suite,
            "suite_header": suite_header,
            "revision": revision,
            "revision_header": revision_header,
            "mode": mode,
            "mode_header": mode_header,
            "description": description,
            "description_header": description_header,
            "preconditions": preconditions,
            "preconditions_header": preconditions_header,
        }

    def _group_rows_by_scenario(
        self,
        rows: list[dict[str, object]],
    ) -> dict[tuple[str, str, str], list[dict[str, object]]]:
        grouped: dict[tuple[str, str, str], list[dict[str, object]]] = {}

        for row in rows:
            sheet_name = str(row.get("sheet_name") or "")
            test_case_id = str(row.get("test_case_id") or "")
            line_number = str(row.get("line_number") or "")
            scenario_part = line_number.rsplit(".", 1)[0] if "." in line_number else line_number

            if not test_case_id:
                test_case_id = scenario_part or f"ROW-{row.get('row_number', '0')}"

            if not scenario_part:
                scenario_part = test_case_id

            key = (sheet_name, test_case_id, scenario_part)
            grouped.setdefault(key, []).append(row)

        for grouped_rows in grouped.values():
            grouped_rows.sort(key=lambda item: int(item.get("row_number") or 0))

        return grouped

    def _build_scenario_chunk_documents(
        self,
        rows: list[dict[str, object]],
    ) -> list[Document]:
        if not rows:
            return []

        first_row = rows[0]
        sheet_name = str(first_row.get("sheet_name") or "")
        file_name = str(first_row.get("file_name") or "")
        source = str(first_row.get("source") or "")
        test_case_id = self._first_non_empty(*[str(row.get("test_case_id") or "") for row in rows])
        test_suite = self._first_non_empty(*[str(row.get("test_suite") or "") for row in rows])
        mode = self._first_non_empty(*[str(row.get("mode") or "") for row in rows])
        description = self._first_non_empty(*[str(row.get("description") or "") for row in rows])
        preconditions = self._first_non_empty(*[str(row.get("preconditions") or "") for row in rows])

        requirement_ids = self._collect_unique([str(row.get("requirement_id") or "") for row in rows])
        bug_ids = self._collect_unique([str(row.get("bug_id") or "") for row in rows])
        line_numbers = self._collect_unique([str(row.get("line_number") or "") for row in rows])
        revisions = self._collect_unique([str(row.get("revision") or "") for row in rows])

        sections: list[str] = []
        sections.append(f"TEST SUITE: {test_suite or 'N/A'}")
        sections.append(f"SHEET: {sheet_name or 'N/A'}")
        sections.append("")
        sections.append(f"TEST CASE ID: {test_case_id or 'N/A'}")
        sections.append(f"TEST LINE NUMBER(S): {', '.join(line_numbers) if line_numbers else 'N/A'}")
        sections.append(f"REVISION(S): {', '.join(revisions) if revisions else 'N/A'}")
        sections.append("")
        sections.append(f"MODE: {mode or 'N/A'}")
        sections.append(f"TEST DESCRIPTION: {description or 'N/A'}")
        sections.append(f"PRECONDITIONS: {preconditions or 'N/A'}")
        sections.append("")
        sections.append(f"REQUIREMENT ID(S): {', '.join(requirement_ids) if requirement_ids else 'N/A'}")
        sections.append(f"BUG ID(S): {', '.join(bug_ids) if bug_ids else 'N/A'}")
        sections.append(
            "SEARCH KEYS: "
            f"TEST_CASE_ID={test_case_id or 'N/A'} | "
            f"REQUIREMENT_ID={', '.join(requirement_ids) if requirement_ids else 'N/A'} | "
            f"BUG_ID={', '.join(bug_ids) if bug_ids else 'N/A'}"
        )
        sections.append("")
        sections.append("COLUMN HEADERS:")
        sections.append(self._render_headers(rows))

        for row in rows:
            sections.append("")
            sections.extend(self._render_test_record(row))

        chunk_text = "\n".join(sections).strip()
        metadata = {
            "source": source,
            "file_name": file_name,
            "file_type": "xlsx",
            "sheet_name": sheet_name,
            "test_case_id": test_case_id,
            "bug_id": ",".join(bug_ids),
            "requirement_id": ",".join(requirement_ids),
            "chunk_type": "excel_test_scenario",
            "line_number": ",".join(line_numbers),
        }

        return self._create_document_with_fallback_split(chunk_text, metadata)

    def _build_traceability_chunk_documents(
        self,
        row: dict[str, object],
    ) -> list[Document]:
        test_case_id = str(row.get("test_case_id") or "")
        requirement_id = str(row.get("requirement_id") or "")
        bug_id = str(row.get("bug_id") or "")
        line_number = str(row.get("line_number") or "")

        text = "\n".join(
            [
                "TRACEABILITY RECORD",
                f"SHEET: {str(row.get('sheet_name') or 'N/A')}",
                f"TEST CASE: {test_case_id or 'N/A'}",
                f"REQUIREMENT: {requirement_id or 'N/A'}",
                f"BUG: {bug_id or 'N/A'}",
                f"TEST LINE NUMBER: {line_number or 'N/A'}",
                "",
                "IDENTIFIERS:",
                f"TEST_CASE_ID={test_case_id or 'N/A'}",
                f"REQUIREMENT_ID={requirement_id or 'N/A'}",
                f"BUG_ID={bug_id or 'N/A'}",
            ]
        )
        metadata = {
            "source": str(row.get("source") or ""),
            "file_name": str(row.get("file_name") or ""),
            "file_type": "xlsx",
            "sheet_name": str(row.get("sheet_name") or ""),
            "test_case_id": test_case_id,
            "bug_id": bug_id,
            "requirement_id": requirement_id,
            "chunk_type": "excel_traceability",
        }
        return self._create_document_with_fallback_split(text, metadata)

    def _create_document_with_fallback_split(
        self,
        text: str,
        metadata: dict[str, str],
    ) -> list[Document]:
        if len(text) <= self.chunk_size:
            return [Document(page_content=text, metadata=metadata)]

        split_docs = self._splitter.create_documents([text], metadatas=[metadata])
        for index, split_doc in enumerate(split_docs, start=1):
            split_doc.metadata["chunk_type"] = f"{metadata.get('chunk_type', 'excel')}_part"
            split_doc.metadata["record_part"] = str(index)
        return split_docs

    def _render_headers(self, rows: list[dict[str, object]]) -> str:
        header_order: list[str] = []
        seen_headers: set[str] = set()

        for row in rows:
            row_headers = row.get("headers") or []
            if not isinstance(row_headers, list):
                continue
            for header in row_headers:
                header_text = str(header).strip()
                if not header_text or header_text in seen_headers:
                    continue
                seen_headers.add(header_text)
                header_order.append(header_text)

        if not header_order:
            return "- N/A"

        return "\n".join(f"- {header}" for header in header_order)

    def _render_test_record(self, row: dict[str, object]) -> list[str]:
        row_number = str(row.get("row_number") or "N/A")
        line_number = str(row.get("line_number") or "N/A")
        revision = str(row.get("revision") or "N/A")

        procedure = str(row.get("procedure") or "N/A")
        expected = str(row.get("expected_result") or "N/A")
        observed = str(row.get("observed_result") or "N/A")
        comments = str(row.get("comments") or "N/A")
        conclusion = str(row.get("conclusion") or "N/A")
        requirement_id = str(row.get("requirement_id") or "N/A")
        bug_id = str(row.get("bug_id") or "N/A")
        test_case_id = str(row.get("test_case_id") or "N/A")

        return [
            f"ROW NUMBER: {row_number}",
            f"TEST CASE ID: {test_case_id}",
            f"TEST LINE NUMBER: {line_number}",
            f"REVISION: {revision}",
            "",
            f"PROCEDURE (header: {row.get('procedure_header') or 'N/A'}):",
            procedure,
            "",
            f"EXPECTED RESULT (header: {row.get('expected_header') or 'N/A'}):",
            expected,
            "",
            f"OBSERVED RESULT (header: {row.get('observed_header') or 'N/A'}):",
            observed,
            "",
            f"COMMENTS (header: {row.get('comments_header') or 'N/A'}):",
            comments,
            "",
            f"CONCLUSION (header: {row.get('conclusion_header') or 'N/A'}):",
            conclusion,
            "",
            f"REQUIREMENT ID (header: {row.get('requirement_header') or 'N/A'}): {requirement_id}",
            f"BUG ID (header: {row.get('bug_header') or 'N/A'}): {bug_id}",
        ]

    def _is_traceability_row(self, row: dict[str, object]) -> bool:
        sheet_name = self._normalize_key(str(row.get("sheet_name") or ""))
        headers = [self._normalize_key(str(header)) for header in row.get("headers") or []]
        has_test_case = bool(str(row.get("test_case_id") or "").strip())
        has_requirement = bool(str(row.get("requirement_id") or "").strip())
        has_bug = bool(str(row.get("bug_id") or "").strip())

        if "trace" in sheet_name or "matrix" in sheet_name:
            return has_test_case and (has_requirement or has_bug)

        header_blob = " ".join(headers)
        likely_traceability = "requirement" in header_blob and "test" in header_blob
        return likely_traceability and has_test_case and (has_requirement or has_bug)

    def _collect_unique(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            value_text = str(value).strip()
            if not value_text:
                continue
            if value_text in seen:
                continue
            seen.add(value_text)
            unique_values.append(value_text)
        return unique_values

    def _find_value_with_header(
        self,
        normalized_cells: dict[str, tuple[str, str]],
        aliases: list[str],
    ) -> tuple[str, str]:
        normalized_aliases = [self._normalize_key(alias) for alias in aliases]
        for alias in normalized_aliases:
            cell = normalized_cells.get(alias)
            if cell and cell[1].strip():
                return cell[1].strip(), cell[0]
        return "", ""

    def _first_non_empty(self, *values: str) -> str:
        for value in values:
            value_text = str(value).strip()
            if value_text:
                return value_text
        return ""

    def _extract_test_case_id(self, cells: dict[str, str]) -> str:
        return self._extract_first_pattern(cells.values(), r"\bDOC[\w.-]+")

    def _extract_requirement_id(self, cells: dict[str, str]) -> str:
        return self._extract_first_pattern(cells.values(), r"\bREQ[\w.-]+")

    def _extract_bug_id(self, cells: dict[str, str]) -> str:
        return self._extract_first_pattern(cells.values(), r"\bBUG[\w.-]+")

    def _extract_first_pattern(self, values, pattern: str) -> str:
        matcher = re.compile(pattern, flags=re.IGNORECASE)
        for value in values:
            match = matcher.search(str(value))
            if match:
                return match.group(0)
        return ""

    def _normalize_key(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
        return normalized.strip("_")

    def _test_case_aliases(self) -> list[str]:
        return ["test case id", "test_case_id", "test case", "tc id", "test id", "scenario id"]

    def _line_aliases(self) -> list[str]:
        return ["line number", "test line number", "line", "test line", "step id", "line no"]

    def _procedure_aliases(self) -> list[str]:
        return ["procedure", "test procedure", "steps", "step", "action"]

    def _expected_result_aliases(self) -> list[str]:
        return ["expected result", "expected", "expected outcome", "exp result"]

    def _observed_result_aliases(self) -> list[str]:
        return ["observed result", "observed", "actual result", "actual", "result"]

    def _comments_aliases(self) -> list[str]:
        return ["comments", "comment", "notes", "remark", "remarks"]

    def _conclusion_aliases(self) -> list[str]:
        return ["conclusion", "status", "verdict", "outcome"]

    def _bug_aliases(self) -> list[str]:
        return ["bug id", "bug", "defect id", "jira", "jira bug", "ticket"]

    def _requirement_aliases(self) -> list[str]:
        return ["requirement id", "requirement", "req id", "req", "requirement_ref"]

    def _suite_aliases(self) -> list[str]:
        return ["test suite", "suite", "suite id", "campaign"]

    def _revision_aliases(self) -> list[str]:
        return ["revision", "rev", "version"]

    def _mode_aliases(self) -> list[str]:
        return ["mode", "test mode", "execution mode"]

    def _description_aliases(self) -> list[str]:
        return ["test description", "description", "scenario", "objective"]

    def _preconditions_aliases(self) -> list[str]:
        return ["preconditions", "precondition", "setup", "initial conditions"]
