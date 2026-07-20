from dataclasses import dataclass


CellValue = str | int | float | None


@dataclass(slots=True)
class ExcelCell:
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
        if self.value is None:
            return True

        if isinstance(self.value, str):
            return not self.value.strip()

        return False

    def as_string(self) -> str:
        if self.value is None:
            return ""
        return str(self.value)
