# Wiring up a real data provider

The API (`wealth_lab/api.py`) is written against `providers.base.DataProvider`
and runs on `MockProvider` (returns nothing) until a real implementation is
registered.

## Finnhub is implemented - here's how to actually turn it on

`wealth_lab/providers/finnhub.py` is a real `DataProvider` implementation
against Finnhub's `/quote`, `/company-news`, `/stock/profile2`, and
`/stock/metric` endpoints - not a sketch. It's registered lazily (see
`providers/__init__.py`) so the default mock-only path never needs the
`requests` package installed.

**This has never made a real HTTP call.** This session has no outbound
network access to finnhub.io - the request/response mapping logic is
tested against mocked responses (`tests/test_finnhub_provider.py`), built
directly from Finnhub's documented field names, but not exercised against
the live API. Confirm it works the first time you deploy somewhere with
real network access, before trusting it.

To turn it on:

1. **Sign up.** https://finnhub.io/register - free tier is 60 calls/min,
   which is what this implementation is built against. This has to happen
   with your own account; it can't be done from inside a Claude Code
   session.
2. **Install the extra dependency.** `pip install -r requirements-live.txt`
   (adds `requests` on top of the base `requirements.txt`).
3. **Set two environment variables** wherever you actually run the API:
   ```
   WEALTH_LAB_PROVIDER=finnhub
   FINNHUB_API_KEY=<your key from step 1>
   ```
4. **Verify it for real** before trusting it in front of visitors:
   ```python
   from wealth_lab.providers.finnhub import FinnhubProvider
   p = FinnhubProvider()  # reads FINNHUB_API_KEY from the environment
   print(p.get_price("AAPL"))          # should be a real float
   print(p.get_fundamentals("AAPL"))   # should be a real Fundamentals
   print(p.get_news("AAPL"))           # should be recent real headlines
   print(p.get_quant_metrics("AAPL"))  # should be a real QuantMetrics (P/E, P/B, beta)
   ```
   If any of these come back `None`/empty unexpectedly, check your API key
   and Finnhub's rate limit before assuming the code is wrong.

Known gap: Finnhub's free tier doesn't expose total TTM revenue on
`/stock/profile2` (that needs `/stock/financials-reported`, a paid tier) -
`Fundamentals.revenue_ttm` is always `None` from this provider rather than
guessed from a per-share metric. `GET /theses/{symbol}` and the console
dashboard already treat missing fields as "not enough data," not zero, so
this doesn't need special-casing anywhere else.

`get_quant_metrics()` (P/E, P/B, beta via `/stock/metric?metric=all`) feeds
`scoring.live_quant_signals()`, which blends real numbers into the
valuation/risk category scores - see README.md's "Category scores are
0-100 too" section for what that does and why growth/catalyst/macro don't
get the same treatment.

## Want a different or additional provider?

Other options by what they cover, none integrated yet - implement
`DataProvider` against one the same way `finnhub.py` does, then
`register_provider("name", YourProviderClass)`:

| Need | Free-tier-friendly options |
|---|---|
| Price | Finnhub (done), Twelve Data, Alpha Vantage |
| News | Marketaux, Financial Modeling Prep, Benzinga |
| Fundamentals incl. revenue | Financial Modeling Prep, Alpha Vantage, or SEC's own `data.sec.gov` (free, no key, but XBRL data takes more parsing) |

## Cache before you scale

Every `/lookup/{symbol}` or `/research/{symbol}` call from every visitor
would otherwise re-hit the paid API. Add a cache (even a simple
time-bucketed in-memory dict, or Redis for multi-instance deployments)
in front of the provider calls once this serves real traffic - not
before, and not inside `DataProvider` itself, which should stay a thin,
honest wrapper around the API.

## What's still missing: `/research/{symbol}`'s signal classification

With `WEALTH_LAB_PROVIDER=finnhub` set, `POST /research/{symbol}` (see
`api.py`) now creates a real thesis skeleton for an unresearched ticker -
name/sector/market cap from `get_fundamentals()`, entry price from
`get_price()` - and logs its recent headlines as unclassified `other`
signals with the raw headline as the rationale, tagged so they're easy to
find and turn into real bullish/bearish signals later.

What it deliberately does NOT do is decide whether a headline is bullish
or bearish - that's classification work, not a provider concern, and it's
a real decision (a wrong automatic bull/bear call is worse than an
honestly-unclassified signal). The natural approach is a Claude API call
per article (or per batch) with a prompt asking for direction + category +
a one-line rationale, then `db.add_signal()` with the result - that needs
its own API key and its own accuracy tradeoffs to sign off on, so it's
intentionally left as a separate decision rather than built silently
alongside the provider integration.
