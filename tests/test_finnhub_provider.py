"""Tests against mocked HTTP responses - this environment has no network
access to finnhub.io, so these verify the request/response mapping logic
(URL shape, field mapping, error handling), not that the real API behaves
as documented. See wealth_lab/providers/finnhub.py's module docstring."""

from datetime import datetime, timedelta, timezone

import pytest
import requests

from wealth_lab.providers.finnhub import FinnhubProvider


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._json


@pytest.fixture
def provider():
    return FinnhubProvider(api_key="test-key")


def test_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        FinnhubProvider()


def test_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "from-env")
    p = FinnhubProvider()
    assert p.api_key == "from-env"


def test_is_live():
    assert FinnhubProvider(api_key="x").is_live is True


def test_get_price_maps_current_price_field(provider, monkeypatch):
    monkeypatch.setattr(
        provider._session, "get",
        lambda url, params, timeout: FakeResponse({"c": 231.5, "h": 235, "l": 229, "o": 230, "pc": 229.8, "t": 123}),
    )
    assert provider.get_price("AAPL") == 231.5


def test_get_price_none_when_symbol_unrecognized(provider, monkeypatch):
    # Finnhub returns c=0 (not an HTTP error) for an unknown symbol
    monkeypatch.setattr(provider._session, "get", lambda url, params, timeout: FakeResponse({"c": 0}))
    assert provider.get_price("NOTASYMBOL") is None


def test_get_price_none_on_request_failure(provider, monkeypatch):
    def raise_error(url, params, timeout):
        raise requests.ConnectionError("boom")
    monkeypatch.setattr(provider._session, "get", raise_error)
    assert provider.get_price("AAPL") is None


def test_get_price_none_on_http_error(provider, monkeypatch):
    monkeypatch.setattr(provider._session, "get", lambda url, params, timeout: FakeResponse({}, status_code=429))
    assert provider.get_price("AAPL") is None


def test_get_news_maps_fields_and_filters_by_recency(provider, monkeypatch):
    now = datetime.now(timezone.utc)
    fresh_ts = int(now.timestamp())
    stale_ts = int((now - timedelta(hours=200)).timestamp())
    monkeypatch.setattr(
        provider._session, "get",
        lambda url, params, timeout: FakeResponse([
            {"headline": "fresh", "summary": "s1", "url": "http://x/1", "datetime": fresh_ts, "source": "Reuters"},
            {"headline": "stale", "summary": "s2", "url": "http://x/2", "datetime": stale_ts, "source": "AP"},
        ]),
    )
    items = provider.get_news("AAPL", since_hours=48)
    assert len(items) == 1
    assert items[0].headline == "fresh"
    assert items[0].source == "Reuters"
    assert items[0].url == "http://x/1"


def test_get_news_empty_when_no_data(provider, monkeypatch):
    monkeypatch.setattr(provider._session, "get", lambda url, params, timeout: FakeResponse(None))
    assert provider.get_news("AAPL") == []


def test_get_fundamentals_maps_fields(provider, monkeypatch):
    monkeypatch.setattr(
        provider._session, "get",
        lambda url, params, timeout: FakeResponse(
            {"name": "Apple Inc", "finnhubIndustry": "Technology", "marketCapitalization": 3500000.0}
        ),
    )
    f = provider.get_fundamentals("AAPL")
    assert f.name == "Apple Inc"
    assert f.sector == "Technology"
    assert f.market_cap == 3500000.0
    assert f.revenue_ttm is None  # not available on Finnhub's free tier


def test_get_fundamentals_none_when_symbol_unknown(provider, monkeypatch):
    monkeypatch.setattr(provider._session, "get", lambda url, params, timeout: FakeResponse({}))
    assert provider.get_fundamentals("NOTASYMBOL") is None
