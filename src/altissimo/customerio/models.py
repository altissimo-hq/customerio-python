"""Customer.io email models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EmailAddress:
    """An email address with an optional display name.

    Supports three input forms for convenience:

    - Plain string: ``"user@example.com"``
    - Tuple: ``("user@example.com", "Display Name")``
    - Dataclass: ``EmailAddress("user@example.com", "Display Name")``

    Attributes:
        email: The email address.
        name: Optional display name (e.g. ``"Lived"``).
    """

    email: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class SendResult:
    """Structured result returned by all send methods.

    Attributes:
        ok: Whether the request was successful.
        delivery_id: The delivery ID returned by Customer.io on success.
        status_code: HTTP status code from the Customer.io API (0 on exception).
        body: Response body as a dictionary.
        error: Error message if the request failed, ``None`` otherwise.
    """

    ok: bool
    delivery_id: str = ""
    status_code: int = 0
    body: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
