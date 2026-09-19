"""A thin HTTP API over the wealth_lab engine (db/scoring/risk/ipo/portfolio),
so a real frontend - not just this repo's CLI or the static console
dashboard - can serve lookups to more than one person at once.

    uvicorn wealth_lab.api:app --reload
    # interactive docs at http://127.0.0.1:8000/docs

This is provider-ready, and can be made live: every read endpoint reflects
whatever is already in the tracker's database (same data the CLI and
console dashboard use). `POST /research/{symbol}` - the endpoint that pulls
in a *new*, not-yet-researched ticker - returns 503 with the default
MockProvider, but does real work once `WEALTH_LAB_PROVIDER=finnhub` (or
another registered provider) is configured: see providers/README.md. It
creates a thesis skeleton (name/sector/entry price from the provider) and
logs recent headlines as unclassified signals - it deliberately does not
decide bullish/bearish on its own; see providers/README.md for why.

CORS is wide open (`allow_origins=["*"]`) for local development. Restrict
this to your actual frontend's origin before deploying anywhere real -
this API has no authentication and shouldn't be trusted to sit fully open
on the public internet as-is.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from wealth_lab import compare, db, export, portfolio, universe
from wealth_lab.providers import get_provider

ThesisStatus = Literal["open", "closed_win", "closed_loss", "closed_flat"]

app = FastAPI(
    title="Wealth Lab API",
    version="0.1.0",
    description=(
        "Read-only HTTP access to the wealth_lab research tracker - the same "
        "scoring, risk, and portfolio engine the CLI and console dashboard use. "
        "See the module docstring in wealth_lab/api.py for what this is and "
        "isn't (not live data, no auth, CORS wide open for local dev)."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"], summary="API info and provider status")
def root():
    """Confirms the API is up and reports which data provider is active -
    always MockProvider (`live_data: false`) until a real one is wired up."""
    provider = get_provider()
    return {
        "name": "Wealth Lab API",
        "live_data": provider.is_live,
        "provider": type(provider).__name__,
    }


@app.get("/theses", tags=["research"], summary="List all theses")
def list_theses(
    status: ThesisStatus | None = Query(default=None, description="Only return theses in this status"),
):
    """Every logged thesis (funded positions and pre-IPO watchlist alike),
    newest first. Raw thesis rows - use GET /theses/{symbol} for the full
    computed view (score, confidence, risk, signals)."""
    with db.connect() as conn:
        return [dict(t) for t in db.list_theses(conn, status=status)]


@app.get("/theses/{symbol}", tags=["research"], summary="Full lookup for one ticker")
def get_thesis(symbol: str):
    """Everything known about one symbol: thesis, sector, price/return,
    portfolio position, composite score/confidence/range, category
    sub-scores, risk metrics, IPO details (if applicable), and every
    signal with its source. 404 if it hasn't been researched yet - this
    only reads what's already logged, it doesn't fetch anything live."""
    with db.connect() as conn:
        t = db.get_thesis_by_symbol(conn, symbol)
        if t is None:
            raise HTTPException(status_code=404, detail=f"{symbol.upper()} hasn't been researched yet")
        return export.thesis_snapshot(conn, t)


@app.get("/compare", tags=["research"], summary="Every thesis side by side")
def compare_theses(
    status: ThesisStatus | None = Query(default=None, description="Only include theses in this status"),
    sort: str = Query(default="score", description=f"Column to sort by, one of {compare.SORTABLE_COLUMNS}"),
    ascending: bool = Query(default=False, description="Sort ascending instead of descending"),
):
    """One row per thesis with score, confidence, expected range, and
    volatility as separate columns - deliberately not blended into one
    ranking number. Missing data always sorts last, regardless of
    direction."""
    if sort not in compare.SORTABLE_COLUMNS:
        raise HTTPException(status_code=400, detail=f"sort must be one of {compare.SORTABLE_COLUMNS}")
    with db.connect() as conn:
        rows = compare.build_comparison(conn, status=status)
        rows = compare.sort_rows(rows, by=sort, descending=not ascending)
        return [vars(r) for r in rows]


@app.get("/portfolio", tags=["portfolio"], summary="Current portfolio allocation and risk")
def get_portfolio():
    """Total value, return since inception, sleeve weights, concentration
    (HHI), real + naive volatility, and confidence-driven sizing
    suggestions (comparison only, never auto-applied). 404 if nothing's
    funded yet."""
    with db.connect() as conn:
        values = portfolio.current_values(conn)
        if not values:
            raise HTTPException(status_code=404, detail="no funded positions yet")
        return export.build_snapshot(conn)["portfolio"]


@app.get("/universe", tags=["research"], summary="S&P 500 research coverage")
def get_universe():
    """How much of the S&P 500 - the lookup tool's bounded stand-in for
    'every stock' - has been researched so far, overall and by sector, plus
    the next unresearched names in round-robin sector order. Same numbers
    `python -m wealth_lab universe-status`/`universe-next` print, for a
    frontend that wants to show buildout progress rather than just the
    theses that already exist."""
    with db.connect() as conn:
        report = universe.coverage(conn)
        nxt = universe.next_batch(conn, n=10)
        return {
            "total": report.total,
            "researched": report.researched,
            "remaining": report.remaining,
            "pct": report.pct,
            "by_sector": {s: {"researched": r, "total": t} for s, (r, t) in report.by_sector.items()},
            "next_up": [{"symbol": e.symbol, "name": e.name, "sector": e.sector} for e in nxt],
        }


@app.get("/snapshot", tags=["research"], summary="Everything at once")
def get_snapshot():
    """The full JSON snapshot - same shape as report/data.json and what
    the console dashboard renders. One call instead of several for a
    frontend that wants the whole picture at once."""
    with db.connect() as conn:
        return export.build_snapshot(conn)


@app.post(
    "/research/{symbol}",
    tags=["research"],
    summary="Auto-create a thesis skeleton for a new ticker from live data",
    responses={
        503: {"description": "No live data provider configured - see providers/README.md"},
        404: {"description": "Provider is live but has no data for this symbol"},
        409: {"description": "This symbol already has a thesis - use GET /theses/{symbol} instead"},
    },
)
def research_symbol(symbol: str):
    """Pulls in a ticker with no existing thesis: fetches price/fundamentals/
    news from the configured DataProvider and logs a new thesis - name,
    sector, and entry price from the provider, recent headlines logged as
    unclassified 'other' signals (rationale is the raw headline) rather
    than guessed as bullish/bearish. See providers/README.md for why
    direction classification is a separate, not-yet-built decision. 503
    with the default MockProvider (no live provider configured)."""
    provider = get_provider()
    if not provider.is_live:
        raise HTTPException(
            status_code=503,
            detail=(
                f"No live data provider configured (running {type(provider).__name__}). "
                "This deployment can't research new tickers on its own yet - "
                "see providers/README.md to wire one up."
            ),
        )

    symbol = symbol.upper()
    with db.connect() as conn:
        if db.get_thesis_by_symbol(conn, symbol) is not None:
            raise HTTPException(status_code=409, detail=f"{symbol} already has a thesis - see GET /theses/{symbol}")

        fundamentals = provider.get_fundamentals(symbol)
        price = provider.get_price(symbol)
        if fundamentals is None and price is None:
            raise HTTPException(status_code=404, detail=f"{type(provider).__name__} has no data for {symbol}")

        thesis_id = db.add_thesis(
            conn, symbol=symbol, asset_type="stock",
            thesis=(
                "Auto-created from live provider data, not yet reviewed. Conviction below is a "
                "placeholder, not an actual rating - recent headlines are logged unclassified "
                "(see the 'other' category signals) pending a real bullish/bearish judgment call."
            ),
            conviction=3,
            name=fundamentals.name if fundamentals else None,
            sector=fundamentals.sector if fundamentals else None,
            entry_price=price,
            entry_date=datetime.now(timezone.utc).date().isoformat() if price is not None else None,
        )

        news = provider.get_news(symbol)
        for item in news:
            db.add_signal(
                conn, thesis_id, name="unclassified_news", direction="neutral", category="other",
                rationale=item.headline, source=item.url,
            )

        return {
            "thesis_id": thesis_id,
            "symbol": symbol,
            "name": fundamentals.name if fundamentals else None,
            "sector": fundamentals.sector if fundamentals else None,
            "market_cap": fundamentals.market_cap if fundamentals else None,
            "entry_price": price,
            "unclassified_news_logged": len(news),
            "note": "conviction and thesis text are placeholders, and news is logged unclassified - "
                    "review and reclassify before trusting the score. See providers/README.md.",
        }
