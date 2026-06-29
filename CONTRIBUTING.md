# Contributing to altissimo-customerio

Thank you for considering contributing to `altissimo-customerio`! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.11+
- [Poetry 2.0+](https://python-poetry.org/docs/#installation)

### Getting Started

```bash
# Clone the repository
git clone https://github.com/altissimo-hq/customerio-python.git
cd customerio-python

# Install all dependencies (including dev and all optional extras)
poetry sync

# Install pre-commit hooks
poetry run pre-commit install

# Verify everything works
poetry run pytest
poetry run ruff check .
poetry run ruff format --check .
```

## Development Workflow

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=altissimo --cov-report=term-missing

# Run a specific test file
poetry run pytest tests/test_client.py

# Run a specific test
poetry run pytest tests/test_client.py::TestSendEmail::test_send_email_success
```

### Linting & Formatting

```bash
# Check for lint errors
poetry run ruff check .

# Auto-fix lint errors
poetry run ruff check --fix .

# Check formatting
poetry run ruff format --check .

# Auto-format
poetry run ruff format .
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. To run them manually:

```bash
poetry run pre-commit run --all-files
```

## Code Standards

- **Type hints**: All public APIs must have complete type annotations
- **Docstrings**: All public classes and methods must have docstrings
- **Tests**: All new features must include tests; aim for >90% coverage
- **Linting**: Code must pass `ruff check` and `ruff format` with the project's configuration

## Architecture

```text
altissimo.customerio
├── client.py         # CustomerIOClient with lazy SDK initialization
├── exceptions.py     # Exception hierarchy
├── models.py         # EmailAddress, SendResult dataclasses
└── py.typed          # PEP 561 marker
```

### Key Principles

1. **Lazy imports** — the `customerio` SDK is imported only when needed
2. **Consistent return types** — all send methods return `SendResult`
3. **No side effects** — constructing a client does not make network calls
4. **Optional dependency** — the package works without `customerio` installed (fails gracefully with a helpful message)

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with tests
4. Ensure all checks pass (`poetry run pytest && poetry run ruff check .`)
5. Commit with a descriptive message
6. Push to your fork and open a Pull Request

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
