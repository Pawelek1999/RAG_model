"""Formatting pipeline that converts Excel test sheets into structured JSON."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from .cell import ExcelCell
from .color_detector import ColorDetector
from .exceptions import ExcelParsingError
from .workbook import ExcelWorkbook


@dataclass(slots=True)
class ExcelColumnLayout:
    """Column index mapping for test workbook fields."""

    importance: int = 1
    test_sequence_number: int = 2
    revision: int = 3
    procedure: int = 4
    expected_result: int = 5
    observed_result: int = 6
    conclusion: int = 7
    comment: int = 8


@dataclass(slots=True)
class JsonFormattingOptions:
    """Behavior flags controlling workbook-to-JSON formatting."""

    stop_on_intentionally_blank: bool = True
    include_raw_rows: bool = False
    filter_sheets_from_prefix: str | None = "AA"


class ExcelJsonFormatter:
    """Converts test-oriented Excel sheets into structured JSON-ready dicts."""

    def __init__(
        self,
        column_layout: ExcelColumnLayout | None = None,
        colors: dict[str, list[str]] | None = None,
        options: JsonFormattingOptions | None = None,
    ) -> None:
        """Initializes formatter dependencies and parsing options.

        Args:
            column_layout: Optional explicit worksheet column mapping.
            colors: Optional custom color palette used for row classification.
            options: Optional formatter behavior overrides.
        """
        self._columns = column_layout or ExcelColumnLayout()
        self._colors = ColorDetector(colors=colors)
        self._options = options or JsonFormattingOptions()

    def format_workbook(self, workbook_path: str | Path, sheet_names: list[str] | None = None) -> dict[str, Any]:
        """Formats selected workbook sheets into structured JSON payload.

        Args:
            workbook_path: Path to source workbook.
            sheet_names: Optional list limiting processed sheets.

        Returns:
            JSON-serializable workbook payload.
        """
        workbook = ExcelWorkbook.load(workbook_path)
        names = sheet_names or workbook.get_sheet_names()
        names = self._select_sheet_names(names)

        sheets_payload: list[dict[str, Any]] = []
        for name in names:
            sheet = workbook.get_sheet(name)
            sheets_payload.append(self._format_sheet(sheet))

        return {
            "source_path": str(Path(workbook_path)),
            "sheet_names": names,
            "sheets": sheets_payload,
        }

    def _format_sheet(self, sheet) -> dict[str, Any]:
        columns = self._resolve_sheet_column_layout(sheet)
        rows: list[dict[str, Any]] = []
        ignored_rows = 0

        for row_index in range(1, sheet.max_row + 1):
            row_data = self._extract_row(sheet, row_index, columns)

            if row_data["is_intentionally_blank"] and self._options.stop_on_intentionally_blank:
                rows.append(row_data)
                break

            if row_data["skip_from_business_flow"]:
                ignored_rows += 1

            rows.append(row_data)

        summary = {
            "rows_total": len(rows),
            "rows_ignored": ignored_rows,
            "rows_actionable": len(rows) - ignored_rows,
            "ok_count": sum(1 for row in rows if row["status"] == "OK"),
            "nok_count": sum(1 for row in rows if row["status"] == "NOT OK"),
            "iar_count": sum(1 for row in rows if row["status"] == "IMPOSSIBLE TO ACHIEVE"),
        }

        return {
            "sheet_name": sheet.name,
            "summary": summary,
            "rows": rows,
        }

    def _extract_row(self, sheet, row_index: int, columns: ExcelColumnLayout) -> dict[str, Any]:
        importance = sheet.get_cell(row=row_index, column=columns.importance)
        seq = sheet.get_cell(row=row_index, column=columns.test_sequence_number)
        revision = sheet.get_cell(row=row_index, column=columns.revision)
        procedure = sheet.get_cell(row=row_index, column=columns.procedure)
        expected = sheet.get_cell(row=row_index, column=columns.expected_result)
        observed = sheet.get_cell(row=row_index, column=columns.observed_result)
        conclusion = sheet.get_cell(row=row_index, column=columns.conclusion)
        comment = sheet.get_cell(row=row_index, column=columns.comment)

        importance_text = importance.as_string().strip()
        sequence_text = seq.as_string().strip()
        revision_text = revision.as_string().strip()
        procedure_text = procedure.as_string()
        expected_text = expected.as_string()
        conclusion_text = conclusion.as_string().strip()
        observed_text = observed.as_string()
        comment_text = comment.as_string()

        is_intentionally_blank = "intentionally blank line" in importance_text.lower()

        row_type = self._classify_row_type(importance=importance, conclusion=conclusion)
        skip = self._is_blocked_for_business_flow(
            importance=importance,
            conclusion=conclusion,
            importance_text=importance_text,
            sequence_text=sequence_text,
            revision_text=revision_text,
            procedure_text=procedure_text,
            expected_text=expected_text,
            observed_text=observed_text,
            conclusion_text=conclusion_text,
            comment_text=comment_text,
        )

        payload: dict[str, Any] = {
            "row_index": row_index,
            "row_type": row_type,
            "skip_from_business_flow": skip,
            "is_intentionally_blank": is_intentionally_blank,
            "importance": importance_text,
            "test_sequence_number": sequence_text,
            "revision": revision_text,
            "procedure": procedure_text,
            "expected_result": expected_text,
            "observed_result": observed_text,
            "comment": comment_text,
            "conclusion": conclusion_text,
            "status": self._resolve_status(conclusion_text, observed_text),
            "flags": {
                "merged": importance.is_merged or conclusion.is_merged,
                "checker_pattern": self._is_checker(importance) or self._is_checker(conclusion),
                "diagonal_down": importance.has_diagonal_down or conclusion.has_diagonal_down,
                "is_blue": self._colors.is_blue(importance) or self._colors.is_blue(conclusion),
                "is_salmon": self._colors.is_salmon(importance) or self._colors.is_salmon(conclusion),
                "is_gray": self._colors.is_gray(importance) or self._colors.is_gray(conclusion),
            },
            "anomaly": self._extract_anomaly(observed_text),
        }

        payload["display_fields"] = self._build_display_fields(
            row_type=row_type,
            sequence_text=sequence_text,
            revision_text=revision_text,
            procedure_text=procedure_text,
            expected_text=expected_text,
            observed_text=observed_text,
            conclusion_text=conclusion_text,
            comment_text=comment_text,
        )

        if self._options.include_raw_rows:
            payload["raw"] = self._dump_raw_row(sheet=sheet, row_index=row_index)

        return payload

    def _classify_row_type(self, importance: ExcelCell, conclusion: ExcelCell) -> str:
        if self._colors.is_salmon(importance) or self._colors.is_salmon(conclusion):
            return "section_header"

        if self._colors.is_blue(importance) or self._colors.is_blue(conclusion):
            return "test_header"

        if self._colors.is_gray(importance) or self._colors.is_gray(conclusion):
            return "inactive"

        if importance.is_merged or conclusion.is_merged:
            return "merged_info"

        if self._is_checker(importance) or self._is_checker(conclusion):
            return "inactive"

        if importance.has_diagonal_down or conclusion.has_diagonal_down:
            return "crossed_out"

        return "test_step"

    def _is_blocked_for_business_flow(
        self,
        importance: ExcelCell,
        conclusion: ExcelCell,
        importance_text: str,
        sequence_text: str,
        revision_text: str,
        procedure_text: str,
        expected_text: str,
        observed_text: str,
        conclusion_text: str,
        comment_text: str,
    ) -> bool:
        if importance_text == "G":
            return True

        if "intentionally blank line" in importance_text.lower():
            return True

        if self._colors.is_salmon(importance) or self._colors.is_salmon(conclusion):
            return True

        if self._colors.is_gray(importance) or self._colors.is_gray(conclusion):
            return True

        if importance.is_merged or conclusion.is_merged:
            return True

        if importance.has_diagonal_down or conclusion.has_diagonal_down:
            return True

        if self._is_checker(importance) or self._is_checker(conclusion):
            return True

        if self._is_header_like_business_row(
            importance_text=importance_text,
            procedure_text=procedure_text,
            expected_text=expected_text,
            observed_text=observed_text,
            conclusion_text=conclusion_text,
            comment_text=comment_text,
            sequence_text=sequence_text,
            revision_text=revision_text,
        ):
            return True

        return False

    def _resolve_sheet_column_layout(self, sheet) -> ExcelColumnLayout:
        # Wykrywa rzeczywisty uklad kolumn po naglowkach i fallbackuje do domyslnego.
        max_scan_rows = min(sheet.max_row, 25)
        max_scan_columns = max(self._columns.comment, min(sheet.max_column, 20))
        best_row_map: dict[str, int] = {}

        for row_index in range(1, max_scan_rows + 1):
            row_map: dict[str, int] = {}
            for col_index in range(1, max_scan_columns + 1):
                value = sheet.get_cell(row=row_index, column=col_index).as_string().strip().casefold()
                if not value:
                    continue

                if value in {"importance", "nb d'importance", "nb d’importance"}:
                    row_map.setdefault("importance", col_index)
                elif value in {"test line number", "test sequence number"}:
                    row_map.setdefault("test_sequence_number", col_index)
                elif value in {"revision", "rev"}:
                    row_map.setdefault("revision", col_index)
                elif value == "procedure":
                    row_map.setdefault("procedure", col_index)
                elif value in {"expected result", "expected results"}:
                    row_map.setdefault("expected_result", col_index)
                elif value in {"observed result", "observed results"}:
                    row_map.setdefault("observed_result", col_index)
                elif value == "conclusion":
                    row_map.setdefault("conclusion", col_index)
                elif value in {"comment", "comments"}:
                    row_map.setdefault("comment", col_index)

            if len(row_map) > len(best_row_map):
                best_row_map = row_map

        if len(best_row_map) < 5:
            return self._columns

        return ExcelColumnLayout(
            importance=best_row_map.get("importance", self._columns.importance),
            test_sequence_number=best_row_map.get("test_sequence_number", self._columns.test_sequence_number),
            revision=best_row_map.get("revision", self._columns.revision),
            procedure=best_row_map.get("procedure", self._columns.procedure),
            expected_result=best_row_map.get("expected_result", self._columns.expected_result),
            observed_result=best_row_map.get("observed_result", self._columns.observed_result),
            conclusion=best_row_map.get("conclusion", self._columns.conclusion),
            comment=best_row_map.get("comment", self._columns.comment),
        )

    def _select_sheet_names(self, names: list[str]) -> list[str]:
        # Domyslnie przetwarza tylko zakladki testowe od prefiksu AA wzwyz.
        if not self._options.filter_sheets_from_prefix:
            return names

        min_prefix = self._options.filter_sheets_from_prefix.strip().upper()
        selected: list[tuple[str, str]] = []

        for name in names:
            prefix = self._extract_two_letter_prefix(name)
            if prefix is None:
                continue
            if prefix < min_prefix:
                continue
            selected.append((prefix, name))

        selected.sort(key=lambda item: (item[0], item[1]))
        return [name for _, name in selected]

    def _build_display_fields(
        self,
        row_type: str,
        sequence_text: str,
        revision_text: str,
        procedure_text: str,
        expected_text: str,
        observed_text: str,
        conclusion_text: str,
        comment_text: str,
    ) -> list[dict[str, str]]:
        if row_type == "test_header":
            field_labels = [
                ("Test sequence number", sequence_text),
                ("Revision", revision_text),
                ("Annotations List", procedure_text),
                ("Generic functionality", expected_text),
                ("Initial conditionss", observed_text),
                ("Purpose", conclusion_text),
                ("Description and remarks", comment_text),
            ]
        else:
            field_labels = [
                ("Test sequence number", sequence_text),
                ("Revision", revision_text),
                ("Procedure", procedure_text),
                ("Expected result", expected_text),
                ("Observed result", observed_text),
                ("Conclusion", conclusion_text),
                ("Comment", comment_text),
            ]

        return [
            {"label": label, "value": value}
            for label, value in field_labels
            if str(value or "").strip()
        ]

    def _extract_two_letter_prefix(self, sheet_name: str) -> str | None:
        # Akceptuje formaty typu AA(...) i ogolnie prefiksy dwuliterowe.
        match = re.match(r"^\s*([A-Za-z]{2})(?=$|[^A-Za-z])", sheet_name)
        if not match:
            return None
        return match.group(1).upper()

    def _is_header_like_business_row(
        self,
        importance_text: str,
        procedure_text: str,
        expected_text: str,
        observed_text: str,
        conclusion_text: str,
        comment_text: str,
        sequence_text: str,
        revision_text: str,
    ) -> bool:
        # Wykrywa naglowki kolumn osadzone w srodku arkusza testowego.
        normalized = {
            "importance": importance_text.strip().casefold(),
            "procedure": procedure_text.strip().casefold(),
            "revision": revision_text.strip().casefold(),
            "expected": expected_text.strip().casefold(),
            "observed": observed_text.strip().casefold(),
            "conclusion": conclusion_text.strip().casefold(),
            "comment": comment_text.strip().casefold(),
            "sequence": sequence_text.strip().casefold(),
        }

        flags = [
            normalized["importance"] in {"importance", "nb d'importance", "nb d’importance"},
            normalized["sequence"] in {"test line number", "test sequence number"},
            normalized["revision"] in {"revision", "rev"},
            normalized["procedure"] == "procedure",
            normalized["expected"] in {"expected result", "expected results"},
            normalized["observed"] in {"observed result", "observed results"},
            normalized["conclusion"] == "conclusion",
            normalized["comment"] in {"comment", "comments"},
        ]

        business_labels_matched = sum(1 for value in flags if value)
        return business_labels_matched >= 3

    def _resolve_status(self, conclusion: str, observed_result: str) -> str | None:
        normalized = conclusion.strip().upper()
        if normalized == "OK":
            return "OK"
        if normalized == "NOT OK":
            return "NOT OK"
        if "IMPOSSIBLE TO ACHIEVE" in normalized:
            return "IMPOSSIBLE TO ACHIEVE"
        if "WRITING ERROR" in observed_result.upper():
            return "WRITING ERROR"
        return None

    def _extract_anomaly(self, observed_result: str) -> str | None:
        marker = "Anomaly:"
        idx = observed_result.find(marker)
        if idx == -1:
            return None

        anomaly = observed_result[idx + len(marker) :].strip()
        if not anomaly:
            return None

        first_line = anomaly.splitlines()[0].strip()
        return first_line or None

    def _is_checker(self, cell: ExcelCell) -> bool:
        pattern = (cell.fill_pattern or "").lower()
        return pattern in {"gray125", "darkgray"}

    def _dump_raw_row(self, sheet, row_index: int) -> dict[str, Any]:
        max_column = max(
            self._columns.comment,
            self._columns.conclusion,
            self._columns.expected_result,
            self._columns.observed_result,
        )
        row_values: dict[str, dict[str, Any]] = {}

        for col_index in range(1, max_column + 1):
            cell = sheet.get_cell(row=row_index, column=col_index)
            row_values[str(col_index)] = {
                "coordinate": cell.coordinate,
                "value": cell.as_string(),
                "fill_color": cell.fill_color,
                "fill_pattern": cell.fill_pattern,
                "font_color": cell.font_color,
                "has_diagonal_down": cell.has_diagonal_down,
                "is_merged": cell.is_merged,
            }

        return row_values


def validate_sheet_names(sheet_names: list[str]) -> list[str]:
    """Validates explicit sheet names passed to formatter.

    Args:
        sheet_names: Candidate sheet names.

    Returns:
        Cleaned non-empty sheet name list.

    Raises:
        ExcelParsingError: When no valid sheet name remains.
    """
    cleaned = [name.strip() for name in sheet_names if name.strip()]
    if not cleaned:
        raise ExcelParsingError("At least one valid sheet name is required.")
    return cleaned
