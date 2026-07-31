"""Request-scoped logging context helpers based on context variables."""

import logging
from contextvars import ContextVar, Token


_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> Token[str]:
    """Stores request identifier in context for subsequent log records.

    Args:
        request_id: Identifier assigned to the current request scope.

    Returns:
        Context token required to reset the variable later.
    """
    return _REQUEST_ID.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Restores previous request identifier using a context token.

    Args:
        token: Token returned by a previous call to set_request_id.
    """
    _REQUEST_ID.reset(token)


def get_request_id() -> str:
    """Returns the current request identifier from context."""
    return _REQUEST_ID.get()


class RequestContextFilter(logging.Filter):
    """Injects request identifier into each processed log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Adds request context fields required by the logging formatter.

        Args:
            record: Log record being processed.

        Returns:
            Always True to keep the record in the logging pipeline.
        """
        record.request_id = get_request_id()
        return True
