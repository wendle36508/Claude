"""Live DataProvider backed by Finnhub (https://finnhub.io).

This can't be exercised end-to-end from inside this sandboxed session -
there is no outbound network access to finnhub.io (or any external host)
from Python here, only this agent's own WebSearch/WebFetch tool calls can
reach the live web, and those aren't available to a running HTTP server's
request handler. Written directly against Finnhub's documented endpoint
shapes (/quote, /company-news, /stock/profile2 - see each method's
docstring), but the actual HTTP round trip has only been exercised via
mocked responses in tests, not a real call. Confirm it against the real
API the first time you deploy this somewhere with real network access
(see providers/README.md's live-deployment section).

Needs the `requests` package (requirements-live.txt, not the base
requirements.txt - kept out of the default install so MockProvider's path
has no extra dependency).

Free tier: 60 API calls/minute, covers everything used here. Sign up at
https://finnhub.io/register.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from wealth_lab.providers.base import DataProvider, Fundamentals, NewsItem

BASE_URL = "https://finnhub.io/api/v1"
REQUEST_TIMEOUT_SECONDS = 10


class FinnhubProvider(DataProvider):
    is_live = True

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FINNHUB_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FinnhubProvider needs an API key - set the FINNHUB_API_KEY env var "
                "or pass api_key= (sign up free at https://finnhub.io/register)"
            )
        self._session = requests.Session()

    def _get(self, path: str, **params) -> Optional[dict | list]:
        params["token"] = self.api_key
        try:
            r = self._session.get(f"{BASE_URL}{path}", params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            # A provider hiccup (rate limit, timeout, unknown symbol) is "no
            # data available" to callers, never a 500 - see DataProvider's
            # contract in base.py. Callers can't distinguish *why* it failed
            # from this return value alone, which is deliberate: they only
            # need to know whether to fall back to "not available."
            return None

    def get_price(self, symbol: str) -> Optional[float]:
        data = self._get("/quote", symbol=symbol.upper())
        if not data:
            return None
        price = data.get("c")
        # Finnhub returns c=0 (not an error) for an unrecognized symbol
        if not price:
            return None
        return float(price)

    def get_news(self, symbol: str, since_hours: int = 48) -> list[NewsItem]:
        to_date = datetime.now(timezone.utc).date()
        from_date = to_date - timedelta(days=max(1, since_hours // 24 + 1))
        data = self._get(
            "/company-news", symbol=symbol.upper(),
            **{"from": from_date.isoformat(), "to": to_date.isoformat()},
        )
        if not data:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        items = []
        for a in data:
            ts = a.get("datetime")
            if not ts:
                continue
            published = datetime.fromtimestamp(ts, tz=timezone.utc)
            if published < cutoff:
                continue
            items.append(NewsItem(
                headline=a.get("headline", ""),
                summary=a.get("summary", ""),
                url=a.get("url", ""),
                published_at=published.isoformat(),
                source=a.get("source") or "finnhub",
            ))
        return items

    def get_fundamentals(self, symbol: str) -> Optional[Fundamentals]:
        data = self._get("/stock/profile2", symbol=symbol.upper())
        if not data or not data.get("name"):
            return None
        return Fundamentals(
            name=data.get("name"),
            sector=data.get("finnhubIndustry"),
            # Finnhub's free tier doesn't expose total TTM revenue on this
            # endpoint (that's /stock/financials-reported, a paid tier) -
            # left None rather than approximated from per-share metrics.
            revenue_ttm=None,
            market_cap=data.get("marketCapitalization"),
        )
