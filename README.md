# altissimo-customerio

[![CI](https://github.com/altissimo-hq/customerio-python/actions/workflows/ci.yml/badge.svg)](https://github.com/altissimo-hq/customerio-python/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Customer.io transactional email and messaging client for Altissimo Python projects.

## Features

- 📋 **Template emails** via `send_email()` — uses Customer.io transactional templates
- 📧 **Plain text** emails via `send_text()` — inline content, no template required
- 🎨 **HTML** emails via `send_html()` — inline content, no template required
- 🌍 **Region support** — US and EU data centers
- 🏗️ **Factory method** — `CustomerIOClient.from_env()` reads `CUSTOMERIO_API_KEY` from the environment
- 🔌 **Optional dependency** — `customerio` SDK is lazily imported with a helpful error message
- 📐 **Typed** — full type annotations with `py.typed` PEP 561 marker
- ✅ **Consistent return type** — all methods return a `SendResult` dataclass
- 🔄 **Retry with backoff** — configurable retry for transient failures
- ✉️ **Custom headers** — including the RFC 8058 one-click unsubscribe pair
- 🔔 **Fails loudly** — send failures raise `CustomerIOSendError` by default; opt out per client for batch sends

## Requirements

- Python 3.11+

## Installation

```bash
pip install altissimo-customerio[customerio]   # core + Customer.io SDK
```

## Quick Start

```python
from altissimo.customerio import CustomerIOClient

client = CustomerIOClient.from_env()

# Template email (most common)
result = client.send_email(
    to="user@example.com",
    transactional_message_id="3",
    message_data={"first_name": "Alice", "year": 2026},
)

# Plain text
result = client.send_text(
    to="user@example.com",
    subject="Hello",
    body="Welcome aboard!",
)

# HTML
result = client.send_html(
    to="user@example.com",
    subject="Hello",
    html="<h1>Welcome!</h1>",
    reply_to="support@example.com",
)

print(result.delivery_id)
```

## Error Handling

By default a failed send raises `CustomerIOSendError`. The originating SDK
exception is preserved as `__cause__`, and the full `SendResult` is attached
as `.result`:

```python
from altissimo.customerio import CustomerIOClient, CustomerIOSendError

try:
    result = client.send_html(to="user@example.com", subject="Hi", html="<p>Hi</p>")
except CustomerIOSendError as exc:
    logger.error("Reset email failed (status=%s): %s", exc.status_code, exc)
else:
    logger.info("Reset email sent: delivery_id=%s", result.delivery_id)
```

For batch sends where one bad recipient should not abort the run, opt out and
check `result.ok` yourself:

```python
client = CustomerIOClient.from_env(raise_on_error=False)

for user in users:
    result = client.send_email(to=user.email, transactional_message_id="3")
    if not result.ok:
        failures.append((user.email, result.status_code, result.error))
```

`SendResult.raise_for_status()` converts a result to an exception on demand
(mirroring `requests.Response.raise_for_status`), which is handy when you want
swallow semantics in one place and raise semantics in another:

```python
client.send_html(to=..., subject=..., html=...).raise_for_status()
```

> **Note:** the library does not log send failures above `DEBUG` when
> `raise_on_error=True` — it has no recipient or template context worth
> logging from that frame, and a log there would make the failure look
> handled. Reporting is the caller's job.

## One-Click Unsubscribe (RFC 8058)

Gmail and Yahoo's bulk-sender rules expect notification and marketing mail to carry a
one-click unsubscribe. That needs **both** headers — `List-Unsubscribe` alone only produces
a plain link:

```python
client.send_email(
    to=user.email,
    transactional_message_id="12",
    message_data={"first_name": user.first_name},
    headers={
        "List-Unsubscribe": f"<https://api.example.com/email/unsubscribe?t={token}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    },
    # The opt-out of record is our own database, so Customer.io's global
    # `unsubscribed` flag (which tracks marketing) must not suppress this.
    send_to_unsubscribed=True,
)
```

Your endpoint must answer an **unauthenticated `POST`** with a `2xx` and no redirect — RFC 8058
forbids redirecting the POST, because browsers have historically turned redirected POSTs into
GETs. Providers will retry, so make it idempotent. Expect `GET`s on the same URL too: some
clients (Apple Mail, Thunderbird) render the header as a link rather than POSTing it, and mail
gateways and link scanners fetch URLs found in mail — so a `GET` should never mutate anything.

> **Note:** `send_to_unsubscribed` is `bool | None`. Leave it unset to inherit whatever the
> transactional message is configured with in the Customer.io dashboard; pass `False` to
> explicitly opt out. `False` is forwarded, not treated as unset.

### Tracking and message retention

Customer.io's dashboard defaults a new transactional message to open and click tracking
**on**, and to keeping the rendered body in delivery history. Neither can be changed through
Customer.io's API, but both can be overridden on each send:

```python
client.send_email(
    to=user.email,
    transactional_message_id="password_reset",
    message_data={"action_url": reset_link},
    # Click tracking rewrites links through a redirect, which can break one-time codes.
    tracked=False,
    # Keep the reset link out of delivery history.
    disable_message_retention=True,
)
```

Both are `bool | None`, like `send_to_unsubscribed`: unset inherits the message's dashboard
setting, and `False` is forwarded. `tracked` covers opens and clicks together.

`send_text()` and `send_html()` accept both too, but an inline send has no transactional
message to inherit from: unset there means Customer.io's own default, which is tracking
**on** and the body **retained**. Pass `tracked=False` and `disable_message_retention=True`
explicitly for inline mail that carries one-time links or codes.

## Configuration

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `CUSTOMERIO_API_KEY` | Customer.io App API key | *(required)* |
| `CUSTOMERIO_REGION` | Data center region (`us` or `eu`) | `us` |

### Constructor

```python
client = CustomerIOClient(
    app_api_key="your-api-key",
    region="us",  # "us" or "eu"
    default_from="noreply@lived.com",  # default sender
    max_retries=3,  # retry transient failures
    retry_delay=1.0,  # base delay (seconds)
    raise_on_error=True,  # raise CustomerIOSendError on failure (default)
)
```

## API Reference

### `CustomerIOClient`

| Method | Description |
|---|---|
| `CustomerIOClient(app_api_key, region?, default_from?, raise_on_error?)` | Create a client with an explicit API key |
| `CustomerIOClient.from_env(env_var?, region?, default_from?, raise_on_error?)` | Create a client from an environment variable |
| `send_email(to, transactional_message_id, message_data?, ...)` | Send a template-based transactional email |
| `send_text(to, subject, body, from_email?, reply_to?, ...)` | Send a plain-text email (inline content) |
| `send_html(to, subject, html, from_email?, reply_to?, ...)` | Send an HTML email (inline content) |

### `SendResult`

| Field | Type | Description |
|---|---|---|
| `ok` | `bool` | Whether the request succeeded |
| `delivery_id` | `str` | Delivery ID from Customer.io |
| `status_code` | `int` | HTTP status code (0 on exception) |
| `body` | `dict[str, Any]` | Response body |
| `error` | `str \| None` | Error message on failure |
| `exception` | `Exception \| None` | Originating SDK exception on failure |

| Method | Description |
|---|---|
| `raise_for_status(context?)` | Raise `CustomerIOSendError` if `ok` is `False`; no-op otherwise |

### Exceptions

| Exception | Raised when |
|---|---|
| `CustomerIOError` | Base class for all library errors |
| `CustomerIOImportError` | The `customerio` SDK is not installed |
| `CustomerIOSendError` | A send failed (carries `status_code` and `result`) |

## Architecture

```text
altissimo.customerio
├── __init__.py       # Public API surface
├── client.py         # CustomerIOClient with lazy SDK initialization
├── exceptions.py     # CustomerIOError, CustomerIOImportError, CustomerIOSendError
├── models.py         # EmailAddress, SendResult dataclasses
└── py.typed          # PEP 561 marker
```

## Development

```bash
# Install all dependencies
poetry sync

# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=altissimo --cov-report=term-missing

# Run linters
poetry run ruff check .
poetry run ruff format --check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed development guidelines.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Security

For reporting security vulnerabilities, see [SECURITY.md](SECURITY.md).

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
