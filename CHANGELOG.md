# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/altissimo-hq/customerio-python/releases/tag/v0.1.0
