"""The only provider wired up by default. Returns nothing for everything -
this environment has no general network access from Python, so there is no
honest way to return real data here. Exists so the API layer has a concrete
dependency to run against and is fully testable without a network call,
and so the "provider unavailable" shape every caller must handle is
exercised from day one instead of being an untested code path.
"""

from __future__ import annotations

from typing import Optional

from wealth_lab.providers.base import DataProvider, Fundamentals, NewsItem, QuantMetrics


class MockProvider(DataProvider):
    is_live = False

    def get_price(self, symbol: str) -> Optional[float]:
        return None

    def get_news(self, symbol: str, since_hours: int = 48) -> list[NewsItem]:
        return []

    def get_fundamentals(self, symbol: str) -> Optional[Fundamentals]:
        return None

    def get_quant_metrics(self, symbol: str) -> Optional[QuantMetrics]:
        return None
