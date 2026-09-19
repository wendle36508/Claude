import pytest

from wealth_lab import providers
from wealth_lab.providers.mock import MockProvider


def test_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("WEALTH_LAB_PROVIDER", raising=False)
    assert isinstance(providers.get_provider(), MockProvider)


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("WEALTH_LAB_PROVIDER", "not_a_real_provider")
    with pytest.raises(ValueError, match="unknown provider"):
        providers.get_provider()


def test_finnhub_lazily_registered_without_importing_requests_eagerly(monkeypatch):
    # providers/__init__.py must not import wealth_lab.providers.finnhub (and
    # therefore `requests`) unless WEALTH_LAB_PROVIDER=finnhub is actually set -
    # the mock-only default path has no extra dependency.
    monkeypatch.setenv("WEALTH_LAB_PROVIDER", "finnhub")
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    from wealth_lab.providers.finnhub import FinnhubProvider

    provider = providers.get_provider()

    assert isinstance(provider, FinnhubProvider)
    assert provider.is_live is True
