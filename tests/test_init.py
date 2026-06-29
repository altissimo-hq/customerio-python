"""Tests for the altissimo.customerio public API surface."""

from __future__ import annotations


class TestPublicAPI:
    """Verify that the public API is importable and consistent."""

    def test_imports(self) -> None:
        from altissimo.customerio import (
            CustomerIOClient,
            CustomerIOError,
            CustomerIOImportError,
            EmailAddress,
            SendResult,
        )

        assert CustomerIOClient is not None
        assert CustomerIOError is not None
        assert CustomerIOImportError is not None
        assert EmailAddress is not None
        assert SendResult is not None

    def test_version_exists(self) -> None:
        from altissimo.customerio import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_all_is_accurate(self) -> None:
        import altissimo.customerio as mod

        for name in mod.__all__:
            assert hasattr(mod, name), f"__all__ lists '{name}' but it is not defined"
