"""Exceptions for altissimo-customerio."""

from __future__ import annotations


class CustomerIOError(Exception):
    """Base exception for all altissimo-customerio errors."""


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
