"""Tests for altissimo.customerio.models."""

from __future__ import annotations

from altissimo.customerio.models import EmailAddress, SendResult


class TestEmailAddress:
    """Tests for the EmailAddress dataclass."""

    def test_with_name(self) -> None:
        addr = EmailAddress(email="user@example.com", name="Test User")
        assert addr.email == "user@example.com"
        assert addr.name == "Test User"

    def test_without_name(self) -> None:
        addr = EmailAddress(email="user@example.com")
        assert addr.email == "user@example.com"
        assert addr.name is None

    def test_frozen(self) -> None:
        import pytest

        addr = EmailAddress(email="user@example.com")
        with pytest.raises(AttributeError):
            addr.email = "other@example.com"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = EmailAddress(email="user@example.com", name="Test")
        b = EmailAddress(email="user@example.com", name="Test")
        assert a == b

    def test_repr(self) -> None:
        addr = EmailAddress(email="user@example.com", name="Test")
        assert "user@example.com" in repr(addr)


class TestSendResult:
    """Tests for the SendResult dataclass."""

    def test_ok_result(self) -> None:
        result = SendResult(ok=True, delivery_id="abc-123", status_code=200)
        assert result.ok is True
        assert result.delivery_id == "abc-123"
        assert result.status_code == 200
        assert result.error is None

    def test_error_result(self) -> None:
        result = SendResult(ok=False, status_code=400, error="Bad request")
        assert result.ok is False
        assert result.delivery_id == ""
        assert result.error == "Bad request"

    def test_defaults(self) -> None:
        result = SendResult(ok=True)
        assert result.delivery_id == ""
        assert result.status_code == 0
        assert result.body == {}
        assert result.error is None

    def test_frozen(self) -> None:
        import pytest

        result = SendResult(ok=True)
        with pytest.raises(AttributeError):
            result.ok = False  # type: ignore[misc]

    def test_equality(self) -> None:
        a = SendResult(ok=True, delivery_id="abc")
        b = SendResult(ok=True, delivery_id="abc")
        assert a == b
