"""Altissimo Customer.io — reusable Customer.io transactional email and messaging client."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .client import CustomerIOClient, EmailAddressLike, EmailRecipients
from .exceptions import CustomerIOError, CustomerIOImportError
from .models import EmailAddress, SendResult

try:
    __version__ = version("altissimo-customerio")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "CustomerIOClient",
    "CustomerIOError",
    "CustomerIOImportError",
    "EmailAddress",
    "EmailAddressLike",
    "EmailRecipients",
    "SendResult",
    "__version__",
]
