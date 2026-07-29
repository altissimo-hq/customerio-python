"""Tests for altissimo.customerio.client."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from altissimo.customerio.client import CustomerIOClient
from altissimo.customerio.exceptions import CustomerIOSendError
from altissimo.customerio.models import EmailAddress

# ------------------------------------------------------------------
# Construction
# ------------------------------------------------------------------


class TestClientConstruction:
    """Tests for CustomerIOClient construction."""

    def test_basic_construction(self) -> None:
        client = CustomerIOClient(app_api_key="test-key", region="us")
        assert client._app_api_key == "test-key"
        assert client._region_str == "us"
        assert client._default_from is None
        assert client._max_retries == 0
        assert client._client is None

    def test_construction_with_options(self) -> None:
        client = CustomerIOClient(
            app_api_key="test-key",
            region="eu",
            default_from="sender@example.com",
            max_retries=3,
            retry_delay=2.0,
        )
        assert client._region_str == "eu"
        assert client._default_from == "sender@example.com"
        assert client._max_retries == 3
        assert client._retry_delay == 2.0

    def test_from_env(self) -> None:
        with patch.dict(os.environ, {"CUSTOMERIO_API_KEY": "env-key"}):
            client = CustomerIOClient.from_env()
            assert client._app_api_key == "env-key"
            assert client._region_str == "us"

    def test_from_env_custom_var(self) -> None:
        with patch.dict(os.environ, {"MY_CIO_KEY": "custom-key"}):
            client = CustomerIOClient.from_env(env_var="MY_CIO_KEY")
            assert client._app_api_key == "custom-key"

    def test_from_env_with_region(self) -> None:
        with patch.dict(os.environ, {"CUSTOMERIO_API_KEY": "key", "CUSTOMERIO_REGION": "eu"}):
            client = CustomerIOClient.from_env()
            assert client._region_str == "eu"

    def test_from_env_explicit_region_overrides_env(self) -> None:
        with patch.dict(os.environ, {"CUSTOMERIO_API_KEY": "key", "CUSTOMERIO_REGION": "eu"}):
            client = CustomerIOClient.from_env(region="us")
            assert client._region_str == "us"

    def test_from_env_missing_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError, match="not set or is empty"):
            CustomerIOClient.from_env(env_var="MISSING_KEY")

    def test_from_env_empty_key(self) -> None:
        with patch.dict(os.environ, {"CUSTOMERIO_API_KEY": ""}), pytest.raises(ValueError, match="not set or is empty"):
            CustomerIOClient.from_env()


# ------------------------------------------------------------------
# Lazy client
# ------------------------------------------------------------------


class TestLazyClient:
    """Tests for lazy client initialization."""

    @patch("altissimo.customerio.client._get_api_client")
    @patch("altissimo.customerio.client._resolve_region")
    def test_client_is_lazy(self, mock_resolve: MagicMock, mock_get: MagicMock) -> None:
        _client = CustomerIOClient(app_api_key="key")
        mock_get.assert_not_called()

    @patch("altissimo.customerio.client._get_api_client")
    @patch("altissimo.customerio.client._resolve_region", return_value="fake-region")
    def test_client_is_cached(self, mock_resolve: MagicMock, mock_get: MagicMock) -> None:
        mock_get.return_value = MagicMock()
        client = CustomerIOClient(app_api_key="key")
        _ = client.client
        _ = client.client
        mock_get.assert_called_once()


# ------------------------------------------------------------------
# Email address resolution
# ------------------------------------------------------------------


class TestResolveFrom:
    """Tests for sender email resolution."""

    def test_explicit_from(self) -> None:
        client = CustomerIOClient(app_api_key="key")
        result = client._resolve_from("explicit@example.com")
        assert result == "explicit@example.com"

    def test_default_from(self) -> None:
        client = CustomerIOClient(app_api_key="key", default_from="default@example.com")
        result = client._resolve_from(None)
        assert result == "default@example.com"

    def test_from_with_name(self) -> None:
        client = CustomerIOClient(app_api_key="key")
        result = client._resolve_from(EmailAddress("sender@example.com", "Sender Name"))
        assert result == "Sender Name <sender@example.com>"

    def test_from_with_tuple(self) -> None:
        client = CustomerIOClient(app_api_key="key")
        result = client._resolve_from(("sender@example.com", "Sender Name"))
        assert result == "Sender Name <sender@example.com>"

    def test_missing_from(self) -> None:
        client = CustomerIOClient(app_api_key="key")
        with pytest.raises(ValueError, match="No sender email"):
            client._resolve_from(None)


# ------------------------------------------------------------------
# Resolve email helpers
# ------------------------------------------------------------------


class TestResolveEmailStr:
    """Tests for _resolve_email_str static method."""

    def test_string(self) -> None:
        assert CustomerIOClient._resolve_email_str("user@example.com") == "user@example.com"

    def test_tuple(self) -> None:
        assert CustomerIOClient._resolve_email_str(("user@example.com", "Name")) == "user@example.com"

    def test_email_address(self) -> None:
        addr = EmailAddress("user@example.com", "Name")
        assert CustomerIOClient._resolve_email_str(addr) == "user@example.com"

    def test_unsupported_type(self) -> None:
        with pytest.raises(TypeError, match="Unsupported"):
            CustomerIOClient._resolve_email_str(123)  # type: ignore[arg-type]


class TestResolveEmailDisplay:
    """Tests for _resolve_email_display static method."""

    def test_string(self) -> None:
        assert CustomerIOClient._resolve_email_display("user@example.com") == "user@example.com"

    def test_tuple(self) -> None:
        assert CustomerIOClient._resolve_email_display(("user@example.com", "Name")) == "Name <user@example.com>"

    def test_email_address_with_name(self) -> None:
        addr = EmailAddress("user@example.com", "Name")
        assert CustomerIOClient._resolve_email_display(addr) == "Name <user@example.com>"

    def test_email_address_without_name(self) -> None:
        addr = EmailAddress("user@example.com")
        assert CustomerIOClient._resolve_email_display(addr) == "user@example.com"

    def test_unsupported_type(self) -> None:
        with pytest.raises(TypeError, match="Unsupported"):
            CustomerIOClient._resolve_email_display(123)  # type: ignore[arg-type]


# ------------------------------------------------------------------
# Normalize recipients
# ------------------------------------------------------------------


class TestNormalizeRecipients:
    """Tests for _normalize_recipients."""

    def test_single_string(self) -> None:
        result = CustomerIOClient._normalize_recipients("user@example.com")
        assert result == ["user@example.com"]

    def test_list(self) -> None:
        result = CustomerIOClient._normalize_recipients(["a@example.com", "b@example.com"])
        assert result == ["a@example.com", "b@example.com"]

    def test_single_item_list(self) -> None:
        result = CustomerIOClient._normalize_recipients(["a@example.com"])
        assert result == ["a@example.com"]


# ------------------------------------------------------------------
# Send email (template)
# ------------------------------------------------------------------


class TestSendEmail:
    """Tests for send_email (template-based)."""

    def test_send_email_success(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_email(
            to="recipient@example.com",
            transactional_message_id="tmpl-1",
            message_data={"name": "Alice"},
        )
        assert result.ok is True
        assert result.delivery_id == "test-delivery-123"
        fake_api_client.send_email.assert_called_once()

    def test_send_email_with_reply_to(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_email(
            to="recipient@example.com",
            transactional_message_id="tmpl-1",
            reply_to="support@example.com",
        )
        assert result.ok is True

    def test_send_email_with_bcc(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_email(
            to="recipient@example.com",
            transactional_message_id="tmpl-1",
            bcc="admin@example.com",
        )
        assert result.ok is True

    def test_send_email_api_error_raises_by_default(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        fake_api_client.send_email.side_effect = Exception("API error")
        with pytest.raises(CustomerIOSendError) as exc_info:
            client_with_mock.send_email(
                to="recipient@example.com",
                transactional_message_id="tmpl-1",
            )
        # The exception message carries the context the library used to swallow.
        assert "recipient@example.com" in str(exc_info.value)
        assert "tmpl-1" in str(exc_info.value)
        assert "API error" in str(exc_info.value)
        assert exc_info.value.result is not None
        assert exc_info.value.result.ok is False

    def test_send_email_api_error_swallowed_when_opted_out(
        self, client_no_raise: Any, fake_api_client: MagicMock
    ) -> None:
        fake_api_client.send_email.side_effect = Exception("API error")
        result = client_no_raise.send_email(
            to="recipient@example.com",
            transactional_message_id="tmpl-1",
        )
        assert result.ok is False
        assert result.error is not None
        assert "API error" in result.error


# ------------------------------------------------------------------
# Send text (inline)
# ------------------------------------------------------------------


class TestSendText:
    """Tests for send_text."""

    def test_send_text_success(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to="recipient@example.com",
            subject="Hello",
            body="Welcome aboard!",
        )
        assert result.ok is True
        # Verify the body was wrapped in <pre>
        call_args = fake_api_client.send_email.call_args
        request = call_args[0][0]
        assert "<pre" in request.body

    def test_send_text_with_reply_to(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to="recipient@example.com",
            subject="Hello",
            body="Text content",
            reply_to="support@example.com",
        )
        assert result.ok is True

    def test_send_text_api_error_raises_by_default(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        fake_api_client.send_email.side_effect = Exception("API error")
        with pytest.raises(CustomerIOSendError):
            client_with_mock.send_text(
                to="recipient@example.com",
                subject="Hello",
                body="Text content",
            )

    def test_send_text_api_error_swallowed_when_opted_out(
        self, client_no_raise: Any, fake_api_client: MagicMock
    ) -> None:
        fake_api_client.send_email.side_effect = Exception("API error")
        result = client_no_raise.send_text(
            to="recipient@example.com",
            subject="Hello",
            body="Text content",
        )
        assert result.ok is False


# ------------------------------------------------------------------
# Send HTML (inline)
# ------------------------------------------------------------------


class TestSendHtml:
    """Tests for send_html."""

    def test_send_html_success(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_html(
            to="recipient@example.com",
            subject="Hello",
            html="<h1>Welcome!</h1>",
        )
        assert result.ok is True

    def test_send_html_with_reply_to(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_html(
            to="recipient@example.com",
            subject="Hello",
            html="<h1>Welcome!</h1>",
            reply_to="support@example.com",
        )
        assert result.ok is True

    def test_send_html_api_error_raises_by_default(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        fake_api_client.send_email.side_effect = Exception("API error")
        with pytest.raises(CustomerIOSendError):
            client_with_mock.send_html(
                to="recipient@example.com",
                subject="Hello",
                html="<h1>Welcome!</h1>",
            )

    def test_send_html_api_error_swallowed_when_opted_out(
        self, client_no_raise: Any, fake_api_client: MagicMock
    ) -> None:
        fake_api_client.send_email.side_effect = Exception("API error")
        result = client_no_raise.send_html(
            to="recipient@example.com",
            subject="Hello",
            html="<h1>Welcome!</h1>",
        )
        assert result.ok is False


# ------------------------------------------------------------------
# Build result
# ------------------------------------------------------------------


class TestBuildResult:
    """Tests for _build_result and _build_error_result."""

    def test_dict_response(self) -> None:
        result = CustomerIOClient._build_result({"delivery_id": "abc-123", "queued_at": 12345})
        assert result.ok is True
        assert result.delivery_id == "abc-123"
        assert result.status_code == 200
        assert result.body == {"delivery_id": "abc-123", "queued_at": 12345}

    def test_dict_response_no_delivery_id(self) -> None:
        result = CustomerIOClient._build_result({"status": "ok"})
        assert result.ok is True
        assert result.delivery_id == ""

    def test_object_response(self) -> None:
        mock = MagicMock()
        mock.delivery_id = "obj-123"
        result = CustomerIOClient._build_result(mock)
        assert result.ok is True
        assert result.delivery_id == "obj-123"

    def test_error_result(self) -> None:
        result = CustomerIOClient._build_error_result(Exception("fail"))
        assert result.ok is False
        assert result.error == "fail"
        assert result.status_code == 0

    def test_error_result_with_status_code(self) -> None:
        exc = Exception("fail")
        exc.status_code = 429  # type: ignore[attr-defined]
        result = CustomerIOClient._build_error_result(exc)
        assert result.status_code == 429

    def test_error_result_preserves_exception(self) -> None:
        exc = Exception("fail")
        result = CustomerIOClient._build_error_result(exc)
        assert result.exception is exc

    def test_error_result_does_not_log_above_debug(self) -> None:
        """The library must not report failures on the caller's behalf."""
        with patch("altissimo.customerio.client.logger") as mock_logger:
            CustomerIOClient._build_error_result(Exception("fail"))
        mock_logger.exception.assert_not_called()
        mock_logger.error.assert_not_called()
        mock_logger.warning.assert_not_called()
        mock_logger.debug.assert_called_once()


# ------------------------------------------------------------------
# Import error
# ------------------------------------------------------------------


class TestCustomerIOImportError:
    """Tests for CustomerIOImportError."""

    def test_message(self) -> None:
        from altissimo.customerio.exceptions import CustomerIOImportError

        exc = CustomerIOImportError()
        assert "customerio" in str(exc)
        assert "pip install" in str(exc)

    def test_isinstance(self) -> None:
        from altissimo.customerio.exceptions import CustomerIOError, CustomerIOImportError

        exc = CustomerIOImportError()
        assert isinstance(exc, CustomerIOError)
        assert isinstance(exc, ImportError)


# ------------------------------------------------------------------
# Multiple recipients
# ------------------------------------------------------------------


class TestMultipleRecipients:
    """Tests for sending to multiple recipients."""

    def test_send_email_multiple(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_email(
            to=["a@example.com", "b@example.com"],
            transactional_message_id="tmpl-1",
        )
        assert result.ok is True
        assert fake_api_client.send_email.call_count == 2

    def test_send_text_multiple(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to=["a@example.com", "b@example.com"],
            subject="Hello",
            body="Hi",
        )
        assert result.ok is True
        assert fake_api_client.send_email.call_count == 2

    def test_send_html_multiple(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_html(
            to=["a@example.com", "b@example.com"],
            subject="Hello",
            html="<p>Hi</p>",
        )
        assert result.ok is True
        assert fake_api_client.send_email.call_count == 2


# ------------------------------------------------------------------
# BCC
# ------------------------------------------------------------------


class TestBcc:
    """Tests for BCC recipients."""

    def test_single_bcc(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to="recipient@example.com",
            subject="Hello",
            body="Text",
            bcc="admin@example.com",
        )
        assert result.ok is True
        call_args = fake_api_client.send_email.call_args
        request = call_args[0][0]
        assert request.bcc == ["admin@example.com"]

    def test_multiple_bcc(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to="recipient@example.com",
            subject="Hello",
            body="Text",
            bcc=["admin1@example.com", "admin2@example.com"],
        )
        assert result.ok is True
        call_args = fake_api_client.send_email.call_args
        request = call_args[0][0]
        assert request.bcc == ["admin1@example.com", "admin2@example.com"]


# ------------------------------------------------------------------
# Retry behavior
# ------------------------------------------------------------------


class TestRetryBehavior:
    """Tests for retry logic."""

    def test_no_retry_on_success(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        client_with_mock._max_retries = 3
        result = client_with_mock.send_email(
            to="recipient@example.com",
            transactional_message_id="tmpl-1",
        )
        assert result.ok is True
        assert fake_api_client.send_email.call_count == 1

    def test_retry_on_transient_error(self, fake_api_client: MagicMock) -> None:
        from altissimo.customerio import CustomerIOClient

        client = CustomerIOClient(app_api_key="key", default_from="sender@example.com", max_retries=2)
        client._client = fake_api_client

        exc = Exception("rate limited")
        exc.status_code = 429  # type: ignore[attr-defined]
        fake_api_client.send_email.side_effect = [exc, {"delivery_id": "retry-ok"}]

        with patch.object(client, "_backoff"):
            result = client.send_email(
                to="recipient@example.com",
                transactional_message_id="tmpl-1",
            )
        assert result.ok is True
        assert fake_api_client.send_email.call_count == 2

    def test_retry_exhausted(self, fake_api_client: MagicMock) -> None:
        from altissimo.customerio import CustomerIOClient

        client = CustomerIOClient(
            app_api_key="key",
            default_from="sender@example.com",
            max_retries=1,
            raise_on_error=False,
        )
        client._client = fake_api_client

        exc = Exception("server error")
        exc.status_code = 500  # type: ignore[attr-defined]
        fake_api_client.send_email.side_effect = exc

        with patch.object(client, "_backoff"):
            result = client.send_email(
                to="recipient@example.com",
                transactional_message_id="tmpl-1",
            )
        assert result.ok is False
        assert fake_api_client.send_email.call_count == 2

    def test_retry_exhausted_raises_by_default(self, fake_api_client: MagicMock) -> None:
        from altissimo.customerio import CustomerIOClient

        client = CustomerIOClient(app_api_key="key", default_from="sender@example.com", max_retries=1)
        client._client = fake_api_client

        exc = Exception("server error")
        exc.status_code = 500  # type: ignore[attr-defined]
        fake_api_client.send_email.side_effect = exc

        with patch.object(client, "_backoff"), pytest.raises(CustomerIOSendError) as exc_info:
            client.send_email(
                to="recipient@example.com",
                transactional_message_id="tmpl-1",
            )
        assert exc_info.value.status_code == 500
        assert exc_info.value.__cause__ is exc
        assert fake_api_client.send_email.call_count == 2

    def test_no_retry_on_non_transient(self, fake_api_client: MagicMock) -> None:
        from altissimo.customerio import CustomerIOClient

        client = CustomerIOClient(
            app_api_key="key",
            default_from="sender@example.com",
            max_retries=3,
            raise_on_error=False,
        )
        client._client = fake_api_client

        exc = Exception("bad request")
        exc.status_code = 400  # type: ignore[attr-defined]
        fake_api_client.send_email.side_effect = exc

        result = client.send_email(
            to="recipient@example.com",
            transactional_message_id="tmpl-1",
        )
        assert result.ok is False
        assert fake_api_client.send_email.call_count == 1


# ------------------------------------------------------------------
# Backoff
# ------------------------------------------------------------------


class TestBackoff:
    """Tests for exponential backoff."""

    @patch("altissimo.customerio.client.time.sleep")
    @patch("altissimo.customerio.client.random.uniform", return_value=0.1)
    def test_backoff_called(self, mock_uniform: MagicMock, mock_sleep: MagicMock) -> None:
        client = CustomerIOClient(app_api_key="key", retry_delay=1.0)
        client._backoff(0)
        mock_sleep.assert_called_once()

    @patch("altissimo.customerio.client.time.sleep")
    @patch("altissimo.customerio.client.random.uniform", return_value=0.0)
    def test_backoff_exponential(self, mock_uniform: MagicMock, mock_sleep: MagicMock) -> None:
        client = CustomerIOClient(app_api_key="key", retry_delay=1.0)
        client._backoff(0)
        mock_sleep.assert_called_with(1.0)
        mock_sleep.reset_mock()
        client._backoff(1)
        mock_sleep.assert_called_with(2.0)
        mock_sleep.reset_mock()
        client._backoff(2)
        mock_sleep.assert_called_with(4.0)


# ------------------------------------------------------------------
# EmailAddressLike forms in send methods
# ------------------------------------------------------------------


class TestEmailAddressLikeSend:
    """Tests that all EmailAddressLike forms work in send methods."""

    def test_string_from(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to="recipient@example.com",
            subject="Test",
            body="body",
            from_email="sender@example.com",
        )
        assert result.ok is True

    def test_tuple_from(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to="recipient@example.com",
            subject="Test",
            body="body",
            from_email=("sender@example.com", "Sender Name"),
        )
        assert result.ok is True

    def test_email_address_from(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to="recipient@example.com",
            subject="Test",
            body="body",
            from_email=EmailAddress("sender@example.com", "Sender Name"),
        )
        assert result.ok is True

    def test_tuple_to(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to=("recipient@example.com", "Recipient"),
            subject="Test",
            body="body",
        )
        assert result.ok is True

    def test_email_address_to(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to=EmailAddress("recipient@example.com", "Recipient"),
            subject="Test",
            body="body",
        )
        assert result.ok is True

    def test_email_address_reply_to(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        result = client_with_mock.send_text(
            to="recipient@example.com",
            subject="Test",
            body="body",
            reply_to=EmailAddress("support@example.com", "Support"),
        )
        assert result.ok is True


# ------------------------------------------------------------------
# Success logging
# ------------------------------------------------------------------


class TestSuccessLogging:
    """Tests for success logging."""

    def test_log_on_send_email(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        with patch("altissimo.customerio.client.logger") as mock_logger:
            client_with_mock.send_email(
                to="recipient@example.com",
                transactional_message_id="tmpl-1",
            )
            mock_logger.info.assert_called_once()

    def test_log_on_send_text(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        with patch("altissimo.customerio.client.logger") as mock_logger:
            client_with_mock.send_text(
                to="recipient@example.com",
                subject="Hello",
                body="body",
            )
            mock_logger.info.assert_called_once()

    def test_log_on_send_html(self, client_with_mock: Any, fake_api_client: MagicMock) -> None:
        with patch("altissimo.customerio.client.logger") as mock_logger:
            client_with_mock.send_html(
                to="recipient@example.com",
                subject="Hello",
                html="<p>Hi</p>",
            )
            mock_logger.info.assert_called_once()

    def test_no_success_log_on_failure(self, client_no_raise: Any, fake_api_client: MagicMock) -> None:
        fake_api_client.send_email.side_effect = Exception("fail")
        with patch("altissimo.customerio.client.logger") as mock_logger:
            client_no_raise.send_text(
                to="recipient@example.com",
                subject="Hello",
                body="body",
            )
            mock_logger.info.assert_not_called()

    def test_warns_with_context_on_swallowed_failure(self, client_no_raise: Any, fake_api_client: MagicMock) -> None:
        """In swallow mode the library logs the failure — with context, unlike before."""
        exc = Exception("bad sender")
        exc.status_code = 400  # type: ignore[attr-defined]
        fake_api_client.send_email.side_effect = exc

        with patch("altissimo.customerio.client.logger") as mock_logger:
            client_no_raise.send_html(
                to="recipient@example.com",
                subject="Reset your password",
                html="<p>Hi</p>",
            )
            mock_logger.warning.assert_called_once()
            rendered = mock_logger.warning.call_args[0][0] % mock_logger.warning.call_args[0][1:]

        assert "recipient@example.com" in rendered
        assert "Reset your password" in rendered
        assert "400" in rendered
