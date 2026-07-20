from __future__ import annotations

"""
CLI tool for exporting test-oriented Excel sheets to JSON.

Examples:
    python backend/tools/excel_tests_to_json.py --input ./Docs/tests.xlsx
    python backend/tools/excel_tests_to_json.py --input ./Docs/tests.xlsx --sheet "TAB_01"
    python backend/tools/excel_tests_to_json.py --input ./Docs/tests.xlsx --output ./out/tests.json --include-raw
"""

import argparse
import json
from pathlib import Path
from typing import Any

from Excel_tests import InvalidWorkbookFormatError, WorkbookNotFoundError, WorksheetNotFoundError
from Excel_tests.exceptions import ExcelParsingError
from Excel_tests.json_formatter import (
    ExcelColumnLayout,
    ExcelJsonFormatter,
    JsonFormattingOptions,
    validate_sheet_names,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export structured JSON from Excel test workbook based on macro-compatible rules."
    )
    parser.add_argument("--input", required=True, type=Path, help="Path to input .xlsx workbook.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output .json file path.")
    parser.add_argument(
        "--sheet",
        action="append",
        default=None,
        help="Sheet name to process. You can pass this argument multiple times.",
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Include raw per-cell metadata in output JSON.",
    )
    parser.add_argument(
        "--dont-stop-on-intentionally-blank",
        action="store_true",
        help="Continue parsing after rows marked as 'Intentionally blank line'.",
    )

    parser.add_argument("--col-importance", type=int, default=1)
    parser.add_argument("--col-test-sequence", type=int, default=2)
    parser.add_argument("--col-revision", type=int, default=3)
    parser.add_argument("--col-procedure", type=int, default=4)
    parser.add_argument("--col-expected", type=int, default=5)
    parser.add_argument("--col-observed", type=int, default=6)
    parser.add_argument("--col-conclusion", type=int, default=7)
    parser.add_argument("--col-comment", type=int, default=8)

    parser.add_argument(
        "--colors-json",
        type=Path,
        default=None,
        help="Optional path to JSON file with color configuration keys: BLUE, SALMON, GRAY_LIGHT, GRAY_DARK, WHITE.",
    )

    return parser.parse_args()


def load_colors(path: Path | None) -> dict[str, list[str]] | None:
    if path is None:
        return None

    if not path.exists():
        raise ExcelParsingError(f"Color config file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ExcelParsingError(f"Invalid colors JSON file: {path}: {error}") from error

    if not isinstance(data, dict):
        raise ExcelParsingError("Color config must be a JSON object.")

    normalized: dict[str, list[str]] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ExcelParsingError("Color config keys must be strings.")
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ExcelParsingError(f"Color config key '{key}' must be an array of strings.")
        normalized[key] = value

    return normalized


def build_column_layout(args: argparse.Namespace) -> ExcelColumnLayout:
    values = [
        args.col_importance,
        args.col_test_sequence,
        args.col_revision,
        args.col_procedure,
        args.col_expected,
        args.col_observed,
        args.col_conclusion,
        args.col_comment,
    ]

    if any(value < 1 for value in values):
        raise ExcelParsingError("All column indexes must be >= 1.")

    return ExcelColumnLayout(
        importance=args.col_importance,
        test_sequence_number=args.col_test_sequence,
        revision=args.col_revision,
        procedure=args.col_procedure,
        expected_result=args.col_expected,
        observed_result=args.col_observed,
        conclusion=args.col_conclusion,
        comment=args.col_comment,
    )


def main() -> int:
    args = parse_args()

    try:
        column_layout = build_column_layout(args)
        options = JsonFormattingOptions(
            stop_on_intentionally_blank=not args.dont_stop_on_intentionally_blank,
            include_raw_rows=args.include_raw,
        )
        colors = load_colors(args.colors_json)

        formatter = ExcelJsonFormatter(
            column_layout=column_layout,
            colors=colors,
            options=options,
        )

        sheets = validate_sheet_names(args.sheet) if args.sheet else None
        payload: dict[str, Any] = formatter.format_workbook(workbook_path=args.input, sheet_names=sheets)

    except (WorkbookNotFoundError, InvalidWorkbookFormatError, WorksheetNotFoundError, ExcelParsingError) as error:
        print(f"ERROR: {error}")
        return 1

    output_text = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text, encoding="utf-8")
        print(f"Saved JSON to: {args.output}")
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
