from __future__ import annotations

from .cell import ExcelCell
from .config import EXCEL_COLORS


class ColorDetector:
    def __init__(self, colors: dict[str, list[str]] | None = None) -> None:
        source = colors or EXCEL_COLORS
        self._colors = {
            key.upper(): [self._normalize(value) for value in values]
            for key, values in source.items()
        }

    def is_blue(self, cell: ExcelCell) -> bool:
        return self._cell_fill_matches(cell, "BLUE")

    def is_salmon(self, cell: ExcelCell) -> bool:
        return self._cell_fill_matches(cell, "SALMON")

    def is_gray(self, cell: ExcelCell) -> bool:
        return self._cell_fill_matches(cell, "GRAY_LIGHT") or self._cell_fill_matches(cell, "GRAY_DARK")

    def is_white(self, cell: ExcelCell) -> bool:
        if cell.fill_color is None:
            return True
        return self._cell_fill_matches(cell, "WHITE")

    def _cell_fill_matches(self, cell: ExcelCell, key: str) -> bool:
        configured = self._colors.get(key, [])
        if not configured:
            return False

        if cell.fill_color is None:
            return False

        return self._normalize(cell.fill_color) in configured

    def _normalize(self, value: str) -> str:
        return value.strip().upper()
