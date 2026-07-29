# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.2.0]: https://github.com/altissimo-hq/customerio-python/releases/tag/v0.2.0
[0.1.0]: https://github.com/altissimo-hq/customerio-python/releases/tag/v0.1.0
