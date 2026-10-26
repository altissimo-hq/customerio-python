# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-10-23

First release published to PyPI, as `altissimo-customerio`. The import name is
unchanged (`altissimo.customerio`).

### Added

- `tracked` and `disable_message_retention` on `send_email()`, `send_text()` and
  `send_html()`, forwarded to Customer.io's per-send fields of the same names. Like
  `send_to_unsubscribed`, both are `bool | None`: unset inherits the transactional
  message's dashboard setting, and `False` is forwarded rather than treated as unset. They
  let a caller set tracking and body retention from code, since Customer.io's API cannot
  change a message's own settings.
- A publish workflow: tagged releases (`v*`) are tested, checked against the
  package version, built, and uploaded to PyPI through Trusted Publishing
  (environment `pypi`). Running it by hand uploads the current branch to
  TestPyPI (environment `testpypi`).
- Renovate configuration: a monthly grouped PR for minor/patch updates, monthly
  `poetry.lock` maintenance, and security fixes at any time. This replaces
  Dependabot.

### Changed

- The build requires `poetry-core>=2.2`, and CI uses Poetry 2.4.1 with actions
  pinned by commit.
- Dropped the License trove classifier (superseded by the SPDX `license`
  expression) and the redundant `[tool.poetry] name`.

## [0.3.1] - 2026-09-15

### Fixed

- Config and import errors were retried and relabelled as send failures. `send_email()`
  and the internal `_send_inline()` built the retry callable as
  `lambda r=request: self.client.send_email(r)`, so resolving `self.client` (which does
  the lazy API-key/region/import resolution) happened *inside* `_send_with_retry`'s `try`
  block. A missing `from_env()` API key or an uninstalled `customerio` SDK was caught
  there, given `status_code=0`, retried through the full backoff schedule, and finally
  raised as a misleading `CustomerIOSendError` instead of the `ValueError` /
  `CustomerIOImportError` it actually is. `client` is now resolved once before the retry
  loop, so config/import errors propagate immediately and unretried.
- `status_code` was always `0` for every real Customer.io send failure, so
  `_RETRYABLE_STATUS_CODES` classification was dead code — a permanent `400`/`401` burned
  the full retry/backoff schedule the same as a transient `500`. Root cause: the
  `customerio` SDK's `send_request` collapses every failure, network and HTTP alike, into
  one `CustomerIOException` that never sets a `.status_code` attribute — the status only
  survives as text inside the exception's message. `_build_error_result` now recovers it
  with a best-effort regex against that message shape (documented as fragile — it is not
  a stable contract of the `customerio` package); a failed match falls back to `0`, the
  same conservative "treat as transient" behavior this had before.
- `send_text()` interpolated the caller-supplied plain-text `body` directly into an HTML
  `<pre>` tag without escaping it, so text containing `<`, `>`, or `&` could inject markup
  into the rendered email instead of appearing as literal text. `body` is now passed
  through `html.escape()`.
- `_build_error_result`'s `.code` fallback trusted a `.code` attribute on any exception as
  an HTTP status. Removed: this SDK has no code path that sets it, so it only risked
  misreading an unrelated exception's `.code`.

### Chore

- Added `.github/dependabot.yml` for automated GitHub Actions and pip dependency updates.

## [0.3.0] - 2026-08-13

### Added

- `headers` parameter on `send_email()`, `send_text()` and `send_html()`, forwarded to the
  SDK's `SendEmailRequest`. The Customer.io API and the underlying `customerio` SDK have
  always supported custom headers; this wrapper silently dropped them, which made the
  RFC 8058 one-click unsubscribe pair (`List-Unsubscribe` plus
  `List-Unsubscribe-Post: List-Unsubscribe=One-Click`) impossible to send. Gmail and Yahoo
  require both headers to render their one-click unsubscribe button, so notification-class
  mail could not meet their bulk-sender rules.
- `send_to_unsubscribed` parameter on the same three methods, also previously dropped. Lets
  a caller override the setting per send rather than only per transactional message in the
  Customer.io dashboard — which matters when the opt-out of record lives in the caller's own
  database, so a marketing unsubscribe must not suppress notification mail. Typed
  `bool | None`: `None` leaves the field off the request so the transactional message's own
  configuration applies, and `False` is forwarded rather than quietly treated as unset.

## [0.2.0] - 2026-07-29

### Changed

- **BREAKING:** send failures now raise `CustomerIOSendError` by default instead of
  returning a `SendResult` with `ok=False`. Previously a failed send was
  indistinguishable from a successful one unless the caller remembered to check
  `result.ok` — and Python has no `must_use`, so nothing prompted them to. Pass
  `raise_on_error=False` to the constructor or `from_env()` to restore the previous
  behaviour for batch sends.
- `_build_error_result` no longer calls `logger.exception`. That log fired from a
  frame with no recipient, subject, or template context, so it was unactionable
  while making the failure look handled. Failures are now logged at `DEBUG` with
  `exc_info`, and reported to the caller instead — either as a raised exception or,
  in `raise_on_error=False` mode, as a `logger.warning` from the send method with
  full context.
- Retry warnings now include the recipient and the template or subject being sent.

### Added

- `CustomerIOSendError`, exported from `altissimo.customerio`. Carries
  `status_code` and the failed `result`, and chains the originating SDK exception
  as `__cause__`.
- `SendResult.raise_for_status(context?)` — mirrors
  `requests.Response.raise_for_status`; a no-op on success.
- `SendResult.exception` field preserving the originating SDK exception so callers
  can log or re-raise it with their own context.
- `raise_on_error` parameter on `CustomerIOClient(...)` and
  `CustomerIOClient.from_env(...)` (default `True`).
- README "Error Handling" section covering both modes.

## [0.1.0] - 2026-06-29

### Added

- `CustomerIOClient` class with lazy `APIClient` initialization
- `CustomerIOClient.from_env()` factory method (reads `CUSTOMERIO_API_KEY` from environment)
- `send_email()` method for transactional template emails
- `send_text()` method for plain-text emails (inline body)
- `send_html()` method for HTML emails (inline body)
- `SendResult` dataclass with `ok`, `delivery_id`, `status_code`, `body`, `error` fields
- `customerio` SDK as an optional dependency with lazy import and helpful error message
- Region support (`us` / `eu`) via constructor or `CUSTOMERIO_REGION` environment variable
- `py.typed` marker for PEP 561 typed package support
- Poetry 2 build system with `src/altissimo/customerio/` namespace layout
- Ruff linting and formatting configuration
- Pytest setup with unit tests
- Pre-commit hooks configuration
- GitHub Actions CI workflow (lint, test matrix 3.11–3.13, build verification)
