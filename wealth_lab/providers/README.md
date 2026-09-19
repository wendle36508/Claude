# Wiring up a real data provider

The API (`wealth_lab/api.py`) is written against `providers.base.DataProvider`
and runs on `MockProvider` (returns nothing) until a real implementation is
registered. This is what that takes.

## 1. Pick a data source

None of these are integrated - pick based on your budget and what you
actually need:

| Need | Free-tier-friendly options |
|---|---|
| Price | Finnhub, Twelve Data, Alpha Vantage |
| News | Marketaux, Financial Modeling Prep, Benzinga |
| Fundamentals (revenue, market cap) | Financial Modeling Prep, Alpha Vantage, or SEC's own `data.sec.gov` (free, no key, but XBRL data takes more parsing) |

Sign up yourself and get an API key - this can't be done from inside a
Claude Code session.

## 2. Implement `DataProvider`

```python
# wealth_lab/providers/finnhub.py  (example - not implemented here)
import httpx
from wealth_lab.providers.base import DataProvider, Fundamentals, NewsItem

class FinnhubProvider(DataProvider):
    is_live = True

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.Client(base_url="https://finnhub.io/api/v1")

    def get_price(self, symbol):
        r = self.client.get("/quote", params={"symbol": symbol, "token": self.api_key})
        r.raise_for_status()
        return r.json().get("c")  # current price

    def get_news(self, symbol, since_hours=48):
        ...  # call /company-news, map to NewsItem, filter by since_hours

    def get_fundamentals(self, symbol):
        ...  # call /stock/profile2, map to Fundamentals
```

Handle the provider's own rate limits and errors inside these methods -
`api.py`'s caller only knows "got a value" or "got None."

## 3. Register it and set the env var

```python
# anywhere imported at app startup, e.g. wealth_lab/api.py
from wealth_lab.providers import register_provider
from wealth_lab.providers.finnhub import FinnhubProvider
register_provider("finnhub", FinnhubProvider)
```

```
WEALTH_LAB_PROVIDER=finnhub
FINNHUB_API_KEY=...          # read this in your provider's __init__, not here
```

## 4. Cache before you scale

Every `/lookup/{symbol}` or `/research/{symbol}` call from every visitor
would otherwise re-hit the paid API. Add a cache (even a simple
time-bucketed in-memory dict, or Redis for multi-instance deployments)
in front of the provider calls once this serves real traffic - not
before, and not inside `DataProvider` itself, which should stay a thin,
honest wrapper around the API.

## 5. `/research/{symbol}`'s missing piece

`get_news()` returns raw articles; turning those into the tracker's
bullish/bearish/neutral signals with a category and rationale is
classification work that isn't implemented yet. The natural approach is a
Claude API call per article (or per batch) with a prompt asking for
direction + category + a one-line rationale, then `db.add_signal()` with
the result. That's genuinely new code, not a provider concern - it
belongs in `api.py`'s `/research` handler, gated behind
`provider.is_live`.
