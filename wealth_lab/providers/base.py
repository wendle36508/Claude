"""The interface a live market-data/news provider must implement to power
automated research (`POST /research/{symbol}` in wealth_lab/api.py).

This environment has no general outbound network access from Python - only
an agent's own tool calls (WebSearch) can reach live data, and those can't
be invoked from a web request handler serving an arbitrary visitor. A real
deployment needs an actual implementation of this interface backed by a
paid or free-tier data API (Finnhub, Alpha Vantage, Marketaux, SEC's own
data.sec.gov, etc.) - see providers/README.md for what that takes. Until
one is wired up and registered in providers/__init__.py, every deployment
of this API runs on MockProvider, which honestly returns nothing rather
than fabricating data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class NewsItem:
    headline: str
    summary: str
    url: str
    published_at: str  # ISO 8601 timestamp
    source: str


@dataclass
class Fundamentals:
    name: Optional[str]
    sector: Optional[str]
    revenue_ttm: Optional[float]
    market_cap: Optional[float]


@dataclass
class QuantMetrics:
    """Real valuation/risk numbers, as opposed to Fundamentals' company
    facts - this is specifically what scoring.live_quant_signals() blends
    into the valuation/risk category scores. Kept separate from
    Fundamentals rather than added to it: those are "what is this
    company," these are "is it priced richly and how bumpy is it,"
    genuinely different questions with different callers."""
    pe_ttm: Optional[float]         # trailing P/E
    pb_ttm: Optional[float]         # price-to-book
    beta: Optional[float]           # vs. the provider's own market index
    week52_high: Optional[float]
    week52_low: Optional[float]


class DataProvider(ABC):
    @property
    @abstractmethod
    def is_live(self) -> bool:
        """False for a provider that cannot actually reach live data (the
        mock). Callers must check this and return an honest "not available"
        response rather than silently treating an empty result as "no news
        today" - those are different facts and must not be confused."""
        ...

    @abstractmethod
    def get_price(self, symbol: str) -> Optional[float]:
        """Latest known price for `symbol`, or None if unavailable."""
        ...

    @abstractmethod
    def get_news(self, symbol: str, since_hours: int = 48) -> list[NewsItem]:
        """Recent news items for `symbol` within the lookback window."""
        ...

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> Optional[Fundamentals]:
        """Basic company facts for `symbol`, or None if unavailable."""
        ...

    @abstractmethod
    def get_quant_metrics(self, symbol: str) -> Optional[QuantMetrics]:
        """P/E, P/B, beta, 52-week range for `symbol`, or None if
        unavailable. Feeds scoring.live_quant_signals() - real numbers
        blended into the valuation/risk category scores, not just signal
        tallies. Individual fields on the returned QuantMetrics can still
        be None if the provider doesn't have that one specifically."""
        ...
