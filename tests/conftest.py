"""Shared test fixtures for altissimo-customerio."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_api_client() -> MagicMock:
    """Return a mock Customer.io ``APIClient`` whose ``send_email`` returns a delivery ID."""
    mock = MagicMock()
    mock.send_email.return_value = {"delivery_id": "test-delivery-123"}
    return mock


@pytest.fixture
def client_with_mock(fake_api_client: MagicMock) -> Any:
    """Return a ``CustomerIOClient`` wired to the fake API client (default: raises on error)."""
    from altissimo.customerio import CustomerIOClient

    cio = CustomerIOClient(app_api_key="fake-api-key", region="us", default_from="sender@example.com")
    cio._client = fake_api_client
    return cio


@pytest.fixture
def client_no_raise(fake_api_client: MagicMock) -> Any:
    """Return a ``CustomerIOClient`` in swallow mode, for exercising ``ok=False`` results."""
    from altissimo.customerio import CustomerIOClient

    cio = CustomerIOClient(
        app_api_key="fake-api-key",
        region="us",
        default_from="sender@example.com",
        raise_on_error=False,
    )
    cio._client = fake_api_client
    return cio
