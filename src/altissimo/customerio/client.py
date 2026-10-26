"""Customer.io transactional email client with typed wrappers for common operations."""

from __future__ import annotations

import logging
import os
import random
import re
import time
from typing import TYPE_CHECKING, Any, TypedDict, Unpack, cast

from altissimo.customerio.exceptions import CustomerIOImportError
from altissimo.customerio.models import EmailAddress, SendResult

if TYPE_CHECKING:
    from customerio import APIClient, Regions

logger = logging.getLogger(__name__)

#: Flexible type for email address arguments — plain string, (email, name) tuple,
#: or :class:`EmailAddress` dataclass.
EmailAddressLike = str | tuple[str, str] | EmailAddress

#: Type alias for recipient arguments — a single address or a list of addresses.
#: Each element can be any :data:`EmailAddressLike` form.
EmailRecipients = EmailAddressLike | list[EmailAddressLike]

#: HTTP status codes that are considered transient and eligible for retry.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

#: The ``customerio`` SDK's ``send_request`` collapses every failure — network
#: errors and real HTTP errors alike — into a single ``CustomerIOException``
#: that never sets a ``.status_code`` attribute. The status only survives as
#: text inside the exception's message, in the shape:
#:   "...Last caught exception -- <class '...CustomerIOException'>: 400: <url> ..."
#: This is not a documented contract of that library — a future release could
#: change the wording and silently break this extraction. A failed match is
#: the safe fallback: status_code stays 0, same as before this existed.
_CUSTOMERIO_STATUS_RE = re.compile(r"CustomerIOException'>: (\d{3}):")

__all__ = ["CustomerIOClient"]


class _RequestOptions(TypedDict, total=False):
    """Per-send fields forwarded unchanged to ``SendEmailRequest``.

    A field set to ``None`` is left off the request. ``False`` is kept, since it
    is a meaningful value distinct from "let the transactional message decide".
    Adding a field here and to the public send methods is all a new one needs.
    """

    preheader: str | None
    headers: dict[str, str] | None
    send_to_unsubscribed: bool | None
    tracked: bool | None
    disable_message_retention: bool | None


def _get_regions_class() -> type[Regions]:
    """Lazily import the Customer.io ``Regions`` enum.

    Raises:
        CustomerIOImportError: If the ``customerio`` package is not installed.
    """
    try:
        from customerio import Regions as _Regions
    except ImportError:
        raise CustomerIOImportError from None

    return cast("type[Regions]", _Regions)


def _get_api_client(app_api_key: str, region: Any) -> APIClient:
    """Lazily import and instantiate the Customer.io ``APIClient``.

    Raises:
        CustomerIOImportError: If the ``customerio`` package is not installed.
    """
    try:
        from customerio import APIClient as _APIClient
    except ImportError:
        raise CustomerIOImportError from None

    return _APIClient(app_api_key, region=region)


def _extract_customerio_status_code(exc: Exception) -> int:
    """Best-effort extraction of the real HTTP status from a ``customerio`` SDK exception.

    See :data:`_CUSTOMERIO_STATUS_RE` for why this is necessary and why it's
    fragile. Returns ``0`` (i.e. "unknown, treat as transient") if *exc* isn't
    a ``CustomerIOException`` or the message doesn't match the expected shape.
    """
    try:
        from customerio.client_base import CustomerIOException
    except ImportError:
        return 0

    if not isinstance(exc, CustomerIOException):
        return 0

    match = _CUSTOMERIO_STATUS_RE.search(str(exc))
    return int(match.group(1)) if match else 0


def _resolve_region(region: str) -> Any:
    """Resolve a region string (``"us"`` or ``"eu"``) to a ``Regions`` enum value.

    Args:
        region: Region string — ``"us"`` or ``"eu"`` (case-insensitive).

    Returns:
        A ``customerio.Regions`` enum value.

    Raises:
        ValueError: If *region* is not ``"us"`` or ``"eu"``.
    """
    regions_cls = _get_regions_class()
    normalized = region.strip().lower()
    if normalized == "us":
        return regions_cls.US
    if normalized == "eu":
        return regions_cls.EU
    msg = f"Invalid region '{region}'. Must be 'us' or 'eu'."
    raise ValueError(msg)


class CustomerIOClient:
    """Thin, typed wrapper around the Customer.io ``APIClient``.

    Provides three convenience methods for the most common transactional
    email operations: plain-text, HTML, and template-based emails.

    The underlying ``APIClient`` is lazily initialized on the first send
    call, so constructing a ``CustomerIOClient`` — via either the
    constructor or :meth:`from_env` — is side-effect-free.

    Args:
        app_api_key: Customer.io App API key (for transactional messaging).
        region: Customer.io data center region — ``"us"`` or ``"eu"``.
        default_from: Default sender email address. Accepts a plain string,
            a ``(email, name)`` tuple, or an :class:`EmailAddress`.
        max_retries: Maximum number of retry attempts for transient errors.
            Set to ``0`` (default) to disable retries.
        retry_delay: Base delay in seconds between retries. Actual delay
            uses exponential backoff with jitter.
        raise_on_error: If ``True`` (default), a failed send raises
            :class:`CustomerIOSendError` instead of returning a
            ``SendResult`` with ``ok=False``. Set to ``False`` for batch
            sends where you want to inspect results and continue past a
            failed recipient — but then you are responsible for checking
            ``result.ok``, because nothing else will.
    """

    def __init__(
        self,
        app_api_key: str,
        region: str = "us",
        default_from: EmailAddressLike | None = None,
        *,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        raise_on_error: bool = True,
    ) -> None:
        self._init_common(region, default_from, max_retries, retry_delay, raise_on_error)
        self._app_api_key: str | None = app_api_key
        self._app_api_key_env_var: str | None = None

    def _init_common(
        self,
        region: str,
        default_from: EmailAddressLike | None,
        max_retries: int,
        retry_delay: float,
        raise_on_error: bool,
    ) -> None:
        self._region_str = region
        self._default_from = default_from
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._raise_on_error = raise_on_error
        self._client: APIClient | None = None

    @classmethod
    def from_env(
        cls,
        *,
        env_var: str = "CUSTOMERIO_API_KEY",
        region: str | None = None,
        default_from: EmailAddressLike | None = None,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        raise_on_error: bool = True,
    ) -> CustomerIOClient:
        """Create a client that reads its API key from an environment variable.

        The environment variable is not read until the API key is actually
        needed (the first send call, or access to :attr:`client`) — this
        factory is just as side-effect-free as the regular constructor.

        Args:
            env_var: Name of the environment variable containing the App API key.
            region: Customer.io region (``"us"`` or ``"eu"``). If ``None``
                (default), reads from the ``CUSTOMERIO_REGION`` environment
                variable, falling back to ``"us"``.
            default_from: Default sender email address.
            max_retries: Maximum number of retry attempts for transient errors.
            retry_delay: Base delay in seconds between retries.
            raise_on_error: Raise :class:`CustomerIOSendError` on send failure.

        Raises:
            ValueError: If the environment variable is not set or is empty,
                raised lazily on first use rather than from this call.
        """
        if region is None:
            region = os.environ.get("CUSTOMERIO_REGION", "us")
        instance = cls.__new__(cls)
        instance._init_common(region, default_from, max_retries, retry_delay, raise_on_error)
        instance._app_api_key = None
        instance._app_api_key_env_var = env_var
        return instance

    def _resolve_api_key(self) -> str:
        """Return the App API key, reading it from the environment on first use.

        Raises:
            ValueError: If the client was built via :meth:`from_env` and the
                configured environment variable is not set or is empty.
        """
        if self._app_api_key is not None:
            return self._app_api_key
        env_var = self._app_api_key_env_var
        app_api_key = os.environ.get(env_var) if env_var else None
        if not app_api_key:
            msg = f"Environment variable '{env_var}' is not set or is empty."
            raise ValueError(msg)
        self._app_api_key = app_api_key
        return app_api_key

    @property
    def client(self) -> APIClient:
        """Return the lazily-initialized ``APIClient``."""
        if self._client is None:
            resolved_region = _resolve_region(self._region_str)
            self._client = _get_api_client(self._resolve_api_key(), resolved_region)
        return self._client

    # ------------------------------------------------------------------
    # Email address resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_email_str(value: EmailAddressLike) -> str:
        """Extract the email address string from any supported form.

        Args:
            value: A plain string, ``(email, name)`` tuple, or :class:`EmailAddress`.

        Returns:
            The email address as a plain string.

        Raises:
            TypeError: If *value* is not a supported type.
        """
        if isinstance(value, str):
            return value
        if isinstance(value, tuple):
            return value[0]
        if isinstance(value, EmailAddress):
            return value.email
        msg = f"Unsupported email address type: {type(value)}"
        raise TypeError(msg)

    @staticmethod
    def _resolve_email_display(value: EmailAddressLike) -> str:
        """Resolve an email address to the ``Display Name <email>`` format.

        If no display name is available, returns just the email address.
        """
        if isinstance(value, str):
            return value
        if isinstance(value, tuple):
            return f"{value[1]} <{value[0]}>"
        if isinstance(value, EmailAddress):
            if value.name:
                return f"{value.name} <{value.email}>"
            return value.email
        msg = f"Unsupported email address type: {type(value)}"
        raise TypeError(msg)

    def _resolve_from(self, from_email: EmailAddressLike | None) -> str:
        """Resolve the sender email, falling back to the default.

        Returns:
            The sender email in ``Display Name <email>`` format or plain email.

        Raises:
            ValueError: If no sender email is provided or configured.
        """
        resolved = from_email or self._default_from
        if not resolved:
            msg = "No sender email provided. Pass 'from_email' to the send method or set 'default_from' on the client."
            raise ValueError(msg)
        return self._resolve_email_display(resolved)

    @staticmethod
    def _normalize_recipients(recipients: EmailRecipients) -> list[EmailAddressLike]:
        """Normalize a recipient argument to a list."""
        if isinstance(recipients, list):
            return list(recipients)
        return [recipients]

    # ------------------------------------------------------------------
    # Result building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_result(response: Any) -> SendResult:
        """Convert a Customer.io API response to a ``SendResult``.

        The ``customerio`` SDK returns a ``dict`` on success with a
        ``delivery_id`` key, or raises on error.
        """
        delivery_id = ""
        body: dict[str, Any] = {}

        if isinstance(response, dict):
            delivery_id = response.get("delivery_id", "")
            body = response
        elif hasattr(response, "delivery_id"):
            delivery_id = getattr(response, "delivery_id", "")

        return SendResult(
            ok=True,
            delivery_id=str(delivery_id),
            status_code=200,
            body=body,
        )

    @staticmethod
    def _build_error_result(exc: Exception) -> SendResult:
        """Build a ``SendResult`` from an exception.

        Deliberately does not log at warning or above. The library has no
        recipient, subject, or template context here, so a log emitted from
        this frame is both unactionable and misleading — it makes the failure
        look handled. Reporting is the caller's job: the exception is
        preserved on the result, and the send methods either raise it or log
        it with full context.
        """
        status_code = 0
        if hasattr(exc, "status_code"):
            status_code = int(getattr(exc, "status_code", 0) or 0)
        else:
            status_code = _extract_customerio_status_code(exc)

        logger.debug("Customer.io API error (status=%s)", status_code, exc_info=exc)

        return SendResult(
            ok=False,
            status_code=status_code,
            error=str(exc),
            exception=exc,
        )

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    def _send_with_retry(self, send_fn: Any, *, context: str = "") -> SendResult:
        """Execute a send function, retrying on transient failures with exponential backoff.

        ``send_fn`` must be built from an already-resolved :attr:`client`
        (call sites do this before entering the loop), not from ``self.client``
        directly — resolving it lazily inside ``send_fn`` would let a missing
        API key or an uninstalled SDK get caught below, given ``status_code=0``,
        and retried through the full backoff schedule instead of propagating
        immediately as the config error it actually is.

        The ``customerio`` SDK collapses every send failure — network errors
        and real HTTP errors alike — into one ``CustomerIOException`` with no
        ``.status_code`` attribute; :func:`_extract_customerio_status_code`
        recovers it on a best-effort basis by parsing the exception's message.
        When that extraction fails (unrecognized message shape, or a non-HTTP
        exception), ``status_code`` stays ``0`` and is treated as transient —
        the same conservative default this had before the extraction existed.

        Args:
            send_fn: A zero-argument callable that performs the API send,
                closing over an already-resolved client.
            context: Description of the send, used in retry logs and in the
                raised exception message.

        Returns:
            A ``SendResult`` with the API response details.

        Raises:
            CustomerIOSendError: If the send failed and the client was
                constructed with ``raise_on_error=True`` (the default).
        """
        last_result: SendResult | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = send_fn()
            except Exception as exc:
                last_result = self._build_error_result(exc)
                # Retry on transient status codes or network errors
                if attempt < self._max_retries and (
                    last_result.status_code in _RETRYABLE_STATUS_CODES or last_result.status_code == 0
                ):
                    logger.warning(
                        "Customer.io error (status=%d) for %s, retrying (attempt %d/%d)",
                        last_result.status_code,
                        context or "send",
                        attempt + 1,
                        self._max_retries,
                    )
                    self._backoff(attempt)
                    continue
                return self._finalize(last_result, context)

            return self._build_result(response)

        # All retries exhausted
        return self._finalize(last_result, context)  # type: ignore[arg-type]

    def _finalize(self, result: SendResult, context: str = "") -> SendResult:
        """Raise if the send failed and ``raise_on_error`` is enabled, else return it."""
        if self._raise_on_error:
            result.raise_for_status(context or None)
        return result

    def _backoff(self, attempt: int) -> None:
        """Sleep with exponential backoff and jitter."""
        delay = self._retry_delay * (2**attempt)
        jitter = random.uniform(0, delay * 0.5)  # noqa: S311
        time.sleep(delay + jitter)

    # ------------------------------------------------------------------
    # SendEmailRequest builder
    # ------------------------------------------------------------------

    def _build_email_request(
        self,
        *,
        to: str,
        transactional_message_id: str | None = None,
        from_email: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        message_data: dict[str, Any] | None = None,
        identifiers: dict[str, str] | None = None,
        reply_to: str | None = None,
        bcc: list[str] | None = None,
        **options: Unpack[_RequestOptions],
    ) -> Any:
        """Build a ``SendEmailRequest`` from the given parameters.

        Returns:
            A ``customerio.SendEmailRequest`` instance.
        """
        try:
            from customerio import SendEmailRequest
        except ImportError:
            raise CustomerIOImportError from None

        fields: dict[str, Any] = {
            "transactional_message_id": transactional_message_id,
            "_from": from_email,
            "subject": subject,
            "body": body,
            "message_data": message_data,
            "reply_to": reply_to,
            "bcc": bcc,
            **options,
        }
        # ``is not None`` rather than truthy: ``False`` is a meaningful value the
        # caller may want to send, distinct from "leave it unset and let the
        # transactional message's own configuration decide".
        kwargs: dict[str, Any] = {
            "to": to,
            # Default to the recipient's email if no identifiers were given.
            "identifiers": identifiers if identifiers is not None else {"email": to},
            **{key: value for key, value in fields.items() if value is not None},
        }

        return SendEmailRequest(**kwargs)

    # ------------------------------------------------------------------
    # Send methods
    # ------------------------------------------------------------------

    def send_email(
        self,
        *,
        to: EmailRecipients,
        transactional_message_id: str,
        message_data: dict[str, Any] | None = None,
        identifiers: dict[str, str] | None = None,
        from_email: EmailAddressLike | None = None,
        reply_to: EmailAddressLike | None = None,
        bcc: EmailRecipients | None = None,
        preheader: str | None = None,
        headers: dict[str, str] | None = None,
        send_to_unsubscribed: bool | None = None,
        tracked: bool | None = None,
        disable_message_retention: bool | None = None,
    ) -> SendResult:
        """Send a transactional email using a Customer.io template.

        This is the primary send method — it uses a pre-configured
        transactional message template from the Customer.io dashboard.

        Args:
            to: Recipient email address or list of addresses.
            transactional_message_id: The transactional message ID from
                the Customer.io dashboard.
            message_data: Template variable substitutions (Liquid template
                data accessible as ``{{message_data.key}}``).
            identifiers: Customer.io profile identifiers
                (e.g. ``{"email": "user@example.com"}``). Defaults to
                the recipient's email address.
            from_email: Sender email (overrides ``default_from``). Accepts
                a string, ``(email, name)`` tuple, or :class:`EmailAddress`.
            reply_to: Reply-to email address.
            bcc: BCC recipient(s) — a single address or list of addresses.
            preheader: Email preheader text (inbox preview).
            headers: Custom email headers. The motivating case is the RFC 8058
                one-click unsubscribe pair::

                    headers={
                        "List-Unsubscribe": "<https://api.example.com/email/unsubscribe?t=TOKEN>",
                        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    }

                **Both** are required for Gmail and Yahoo to render a one-click
                unsubscribe button; ``List-Unsubscribe`` on its own only yields a
                plain link, which some clients issue a ``GET`` against. The URL
                must therefore answer an unauthenticated ``POST`` with a ``2xx``
                and no redirect — RFC 8058 forbids redirecting the POST, since
                browsers have historically turned redirected POSTs into GETs.
            send_to_unsubscribed: Send even to profiles Customer.io has flagged
                ``unsubscribed``. Set this for notification-class mail whose
                opt-out is tracked in your own system rather than by Customer.io,
                so a marketing unsubscribe does not silently suppress it. Leave
                unset to inherit the transactional message's own setting.
            tracked: Track opens and link clicks for this send. ``False`` keeps
                links unrewritten (no click-tracking redirect) and adds no open
                pixel, which matters for links carrying one-time codes. Leave
                unset to inherit the transactional message's own setting.
            disable_message_retention: Keep the rendered body out of Customer.io's
                delivery history, for mail that carries links or codes nobody
                should be able to read back later. Leave unset to inherit the
                transactional message's own setting.

        Returns:
            A ``SendResult`` with the API response details.
        """
        client = self.client  # Resolve eagerly — config/import errors must not be retried.

        sender = self._resolve_from(from_email) if from_email or self._default_from else None
        recipients = self._normalize_recipients(to)
        bcc_list = [self._resolve_email_str(a) for a in self._normalize_recipients(bcc)] if bcc else None
        reply_to_str = self._resolve_email_display(reply_to) if reply_to else None

        # Send to each recipient
        last_result: SendResult | None = None
        for recipient in recipients:
            to_str = self._resolve_email_str(recipient)
            request = self._build_email_request(
                to=to_str,
                transactional_message_id=transactional_message_id,
                from_email=sender,
                message_data=message_data,
                identifiers=identifiers,
                reply_to=reply_to_str,
                bcc=bcc_list,
                preheader=preheader,
                headers=headers,
                send_to_unsubscribed=send_to_unsubscribed,
                tracked=tracked,
                disable_message_retention=disable_message_retention,
            )

            context = f"to={to_str} template={transactional_message_id}"
            result = self._send_with_retry(lambda r=request: client.send_email(r), context=context)
            last_result = result
            if result.ok:
                logger.info(
                    "Email sent: template=%s to=%s delivery_id=%s",
                    transactional_message_id,
                    to_str,
                    result.delivery_id,
                )
            else:
                # Only reachable when raise_on_error=False.
                logger.warning(
                    "Email send failed: template=%s to=%s status=%d error=%s",
                    transactional_message_id,
                    to_str,
                    result.status_code,
                    result.error,
                )

        return last_result  # type: ignore[return-value]

    def send_text(
        self,
        *,
        to: EmailRecipients,
        subject: str,
        body: str,
        from_email: EmailAddressLike | None = None,
        reply_to: EmailAddressLike | None = None,
        bcc: EmailRecipients | None = None,
        identifiers: dict[str, str] | None = None,
        preheader: str | None = None,
        headers: dict[str, str] | None = None,
        send_to_unsubscribed: bool | None = None,
        tracked: bool | None = None,
        disable_message_retention: bool | None = None,
    ) -> SendResult:
        """Send a plain-text transactional email with inline content.

        Uses Customer.io's inline content feature (no template required).
        The body is sent as plain text wrapped in a minimal HTML structure.

        Args:
            to: Recipient email address or list of addresses.
            subject: Email subject line.
            body: Plain-text email body.
            from_email: Sender email (overrides ``default_from``). Accepts
                a string, ``(email, name)`` tuple, or :class:`EmailAddress`.
            reply_to: Reply-to email address.
            bcc: BCC recipient(s) — a single address or list of addresses.
            identifiers: Customer.io profile identifiers.
            preheader: Email preheader text (inbox preview).
            headers: Custom email headers — see :meth:`send_email`.
            send_to_unsubscribed: Send even to unsubscribed profiles — see
                :meth:`send_email`.
            tracked: Track opens and link clicks — see :meth:`send_email`. An
                inline send has no transactional message to inherit from, so
                leaving this unset means Customer.io's default: tracking **on**.
                Pass ``False`` for mail carrying one-time links or codes.
            disable_message_retention: Keep the body out of delivery history — see
                :meth:`send_email`. Leaving this unset means Customer.io's
                default: the body **is** retained.

        Returns:
            A ``SendResult`` with the API response details.
        """
        # Wrap plain text in <pre> so it renders correctly in email clients.
        # Escape HTML entities to prevent accidental injection.
        import html

        html_body = f'<pre style="font-family: sans-serif; white-space: pre-wrap;">{html.escape(body)}</pre>'
        return self._send_inline(
            to=to,
            subject=subject,
            body=html_body,
            from_email=from_email,
            reply_to=reply_to,
            bcc=bcc,
            identifiers=identifiers,
            preheader=preheader,
            headers=headers,
            send_to_unsubscribed=send_to_unsubscribed,
            tracked=tracked,
            disable_message_retention=disable_message_retention,
        )

    def send_html(
        self,
        *,
        to: EmailRecipients,
        subject: str,
        html: str,
        from_email: EmailAddressLike | None = None,
        reply_to: EmailAddressLike | None = None,
        bcc: EmailRecipients | None = None,
        identifiers: dict[str, str] | None = None,
        preheader: str | None = None,
        headers: dict[str, str] | None = None,
        send_to_unsubscribed: bool | None = None,
        tracked: bool | None = None,
        disable_message_retention: bool | None = None,
    ) -> SendResult:
        """Send an HTML transactional email with inline content.

        Uses Customer.io's inline content feature (no template required).

        Args:
            to: Recipient email address or list of addresses.
            subject: Email subject line.
            html: HTML email body.
            from_email: Sender email (overrides ``default_from``). Accepts
                a string, ``(email, name)`` tuple, or :class:`EmailAddress`.
            reply_to: Reply-to email address.
            bcc: BCC recipient(s) — a single address or list of addresses.
            identifiers: Customer.io profile identifiers.
            preheader: Email preheader text (inbox preview).
            headers: Custom email headers — see :meth:`send_email`.
            send_to_unsubscribed: Send even to unsubscribed profiles — see
                :meth:`send_email`.
            tracked: Track opens and link clicks — see :meth:`send_email`. An
                inline send has no transactional message to inherit from, so
                leaving this unset means Customer.io's default: tracking **on**.
                Pass ``False`` for mail carrying one-time links or codes.
            disable_message_retention: Keep the body out of delivery history — see
                :meth:`send_email`. Leaving this unset means Customer.io's
                default: the body **is** retained.

        Returns:
            A ``SendResult`` with the API response details.
        """
        return self._send_inline(
            to=to,
            subject=subject,
            body=html,
            from_email=from_email,
            reply_to=reply_to,
            bcc=bcc,
            identifiers=identifiers,
            preheader=preheader,
            headers=headers,
            send_to_unsubscribed=send_to_unsubscribed,
            tracked=tracked,
            disable_message_retention=disable_message_retention,
        )

    def _send_inline(
        self,
        *,
        to: EmailRecipients,
        subject: str,
        body: str,
        from_email: EmailAddressLike | None = None,
        reply_to: EmailAddressLike | None = None,
        bcc: EmailRecipients | None = None,
        identifiers: dict[str, str] | None = None,
        **options: Unpack[_RequestOptions],
    ) -> SendResult:
        """Internal method to send inline-content transactional emails."""
        client = self.client  # Resolve eagerly — config/import errors must not be retried.

        sender = self._resolve_from(from_email)
        recipients = self._normalize_recipients(to)
        bcc_list = [self._resolve_email_str(a) for a in self._normalize_recipients(bcc)] if bcc else None
        reply_to_str = self._resolve_email_display(reply_to) if reply_to else None

        last_result: SendResult | None = None
        for recipient in recipients:
            to_str = self._resolve_email_str(recipient)
            request = self._build_email_request(
                to=to_str,
                from_email=sender,
                subject=subject,
                body=body,
                identifiers=identifiers,
                reply_to=reply_to_str,
                bcc=bcc_list,
                **options,
            )

            context = f"to={to_str} subject={subject!r}"
            result = self._send_with_retry(lambda r=request: client.send_email(r), context=context)
            last_result = result
            if result.ok:
                logger.info(
                    "Email sent: subject=%r to=%s delivery_id=%s",
                    subject,
                    to_str,
                    result.delivery_id,
                )
            else:
                # Only reachable when raise_on_error=False.
                logger.warning(
                    "Email send failed: subject=%r to=%s status=%d error=%s",
                    subject,
                    to_str,
                    result.status_code,
                    result.error,
                )

        return last_result  # type: ignore[return-value]
