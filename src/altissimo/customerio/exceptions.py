"""Exceptions for altissimo-customerio."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from altissimo.customerio.models import SendResult


class CustomerIOError(Exception):
    """Base exception for all altissimo-customerio errors."""


class CustomerIOSendError(CustomerIOError):
    """Raised when a send fails.

    Raised by :meth:`SendResult.raise_for_status` and, when the client is
    constructed with ``raise_on_error=True`` (the default), by the send
    methods themselves.

    The originating SDK exception is preserved as ``__cause__``, and the
    full :class:`SendResult` is available as :attr:`result` for callers
    that need the status code or response body.

    Attributes:
        status_code: HTTP status code from the Customer.io API (0 if the
            request never got a response, e.g. a network error).
        result: The ``SendResult`` that failed.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 0,
        result: SendResult | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.result = result


class CustomerIOImportError(CustomerIOError, ImportError):
    """Raised when the ``customerio`` SDK is not installed.

    Install with::

        pip install altissimo-customerio[customerio]
    """

    def __init__(self) -> None:
        super().__init__(
            "The 'customerio' package is required but not installed. "
            "Install it with: pip install altissimo-customerio[customerio]"
        )
