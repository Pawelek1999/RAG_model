class ExcelError(Exception):
    """Base exception for Excel infrastructure errors."""


class WorkbookNotFoundError(ExcelError):
    """Raised when workbook path does not exist."""


class WorksheetNotFoundError(ExcelError):
    """Raised when requested worksheet name does not exist."""


class InvalidWorkbookFormatError(ExcelError):
    """Raised when workbook format is not supported."""


class ExcelParsingError(ExcelError):
    """Raised when workbook content cannot be mapped into test JSON schema."""
