---
id: excel-parsing
sidebar_position: 4
title: Excel parsing (tools/Excel_tests)
---

# Excel parsing (`backend/tools/Excel_tests/`)

**TL;DR:** a small, self-contained toolkit for reading `.xlsx` files cell-by-cell (including fill color and borders) and classifying each row as a test step, header, or something to ignore. Used only by [`DocumentLoader`'s test-oriented XLSX path](./loading-and-chunking.md#xlsx-test-oriented-mode-_load_xlsx_test_oriented), via `ExcelJsonFormatter`.

:::note Lives under `tools/`, not `components/`
Unlike the other pages in this section, this module is not one of the `backend/components/` RAG components — it's a standalone, lower-level parsing library that `DocumentLoader` happens to depend on. That's why it gets its own directory (`backend/tools/Excel_tests/`) and its own page here.
:::

## Classes

| Class | File | Responsibility |
|---|---|---|
| `ExcelWorkbook` | `workbook.py` | Validated `.xlsx` loading (`WorkbookNotFoundError`, `InvalidWorkbookFormatError`) and sheet access, wrapping `openpyxl.load_workbook(data_only=True)`. |
| `ExcelWorksheet` | `worksheet.py` | Normalized cell access (`get_cell`, `iter_rows`, `iter_cells`); extracts each cell's fill color, fill pattern, font color, diagonal-down border flag, and merged-cell status. |
| `ExcelCell` | `cell.py` | Plain dataclass holding a cell's coordinates, value, and visual metadata, with `is_empty()` / `as_string()` helpers. |
| `ColorDetector` | `color_detector.py` | Classifies a cell's fill color against a configured palette: `is_blue`, `is_salmon`, `is_gray`, `is_white`. |
| `ExcelJsonFormatter` | `json_formatter.py` | The core row classifier — see below. |

:::warning Color palette is mostly empty by default
The default palette (`config.py`, `EXCEL_COLORS`) only defines `BLUE: ["INDEXED:44"]` — `salmon`, `gray`, and `white` are empty lists. This means the salmon/gray-based classification branches in `ExcelJsonFormatter` (below) are effectively inert unless this palette is customized for a specific workbook's color scheme.
:::

## `ExcelJsonFormatter` internals

| Method | Behavior |
|---|---|
| `_resolve_sheet_column_layout()` | Scans up to the first 25 rows to auto-detect column positions for `importance`, `test_sequence_number`, `revision`, `procedure`, `expected_result`, `observed_result`, `conclusion`, `comment` by header text. Falls back to the fixed `ExcelColumnLayout` defaults (columns 1–8) if fewer than 5 headers are detected. |
| `_classify_row_type()` | Assigns one of `section_header` (salmon fill), `test_header` (blue fill), `inactive` (gray fill or a "checker" hatch pattern), `merged_info` (merged cells), `crossed_out` (diagonal-down border), or the default `test_step`. |
| `_is_blocked_for_business_flow()` | Marks a row `skip_from_business_flow` — see conditions below. |
| `_resolve_status()` | Maps `conclusion` text to `OK` / `NOT OK` / `IMPOSSIBLE TO ACHIEVE`, or `WRITING ERROR` when `observed_result` contains that phrase; otherwise `None`. |
| `_extract_anomaly()` | Pulls the first line after an `"Anomaly:"` marker in `observed_result`. |
| `_select_sheet_names()` | By default only processes sheets whose name's two-letter prefix is alphabetically ≥ `"AA"` (`filter_sheets_from_prefix` option), sorted by that prefix. |
| `format_workbook(workbook_path, sheet_names=None)` | Ties it all together — see return shape below. |

`_is_blocked_for_business_flow()` returns `True` when any of these hold:

- importance text is exactly `"G"`
- importance mentions "intentionally blank line"
- the row is salmon/gray/merged/diagonal-down/checker-patterned
- it looks like an embedded column-header row repeated mid-sheet (`_is_header_like_business_row`, requiring ≥3 of 8 known header labels to match)

`format_workbook()` returns:

```python
{
    "source_path": "...",
    "sheet_names": [...],
    "sheets": [
        {
            "sheet_name": "...",
            "summary": {
                "rows_total": 42, "rows_ignored": 3, "rows_actionable": 39,
                "ok_count": 30, "nok_count": 8, "iar_count": 1,
            },
            "rows": [...],
        },
    ],
}
```

This is the payload `DocumentLoader._load_xlsx_test_oriented()` consumes to build one `Document` per test row — see [Loading & chunking](./loading-and-chunking.md#xlsx-test-oriented-mode-_load_xlsx_test_oriented).
