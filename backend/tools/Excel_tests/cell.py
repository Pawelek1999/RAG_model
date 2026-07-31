"""Normalized cell model used across Excel parsing helpers."""

from dataclasses import dataclass


CellValue = str | int | float | None


@dataclass(slots=True)
class ExcelCell:
    """Represents worksheet cell value and visual metadata relevant to parsing."""

    row: int
    column: int
    coordinate: str
    value: CellValue
    fill_color: str | None
    fill_pattern: str | None
    font_color: str | None
    has_diagonal_down: bool
    is_merged: bool

    def is_empty(self) -> bool:
        """Checks whether the cell contains a meaningful value.

        Returns:
            True when value is None or blank text.
        """
        if self.value is None:
            return True

        if isinstance(self.value, str):
            return not self.value.strip()

        return False

    def as_string(self) -> str:
        """Returns cell value converted to string representation."""
        if self.value is None:
            return ""
        return str(self.value)
