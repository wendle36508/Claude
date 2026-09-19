"""A thin HTTP API over the wealth_lab engine (db/scoring/risk/ipo/portfolio),
so a real frontend - not just this repo's CLI or the static console
dashboard - can serve lookups to more than one person at once.

    uvicorn wealth_lab.api:app --reload

This is provider-ready, not live: every read endpoint reflects whatever is
already in the tracker's database (same data the CLI and console dashboard
use), and `POST /research/{symbol}` - the endpoint that would pull in a
*new*, not-yet-researched ticker - returns 503 until a real DataProvider is
registered (see providers/README.md). That's not a bug to fix later; it's
the honest state of an engine with no live data source wired up yet.

CORS is wide open (`allow_origins=["*"]`) for local development. Restrict
this to your actual frontend's origin before deploying anywhere real -
this API has no authentication and shouldn't be trusted to sit fully open
on the public internet as-is.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from wealth_lab import compare, db, export, ipo, portfolio, risk, scoring
from wealth_lab.providers import get_provider

app = FastAPI(title="Wealth Lab API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    provider = get_provider()
    return {
        "name": "Wealth Lab API",
        "live_data": provider.is_live,
        "provider": type(provider).__name__,
    }


@app.get("/theses")
def list_theses(status: str | None = Query(default=None)):
    with db.connect() as conn:
        return [dict(t) for t in db.list_theses(conn, status=status)]


@app.get("/theses/{symbol}")
def get_thesis(symbol: str):
    with db.connect() as conn:
        t = db.get_thesis_by_symbol(conn, symbol)
        if t is None:
            raise HTTPException(status_code=404, detail=f"{symbol.upper()} hasn't been researched yet")
        return export.thesis_snapshot(conn, t)


@app.get("/compare")
def compare_theses(
    status: str | None = Query(default=None),
    sort: str = Query(default="score"),
    ascending: bool = Query(default=False),
):
    if sort not in compare.SORTABLE_COLUMNS:
        raise HTTPException(status_code=400, detail=f"sort must be one of {compare.SORTABLE_COLUMNS}")
    with db.connect() as conn:
        rows = compare.build_comparison(conn, status=status)
        rows = compare.sort_rows(rows, by=sort, descending=not ascending)
        return [vars(r) for r in rows]


@app.get("/portfolio")
def get_portfolio():
    with db.connect() as conn:
        values = portfolio.current_values(conn)
        if not values:
            raise HTTPException(status_code=404, detail="no funded positions yet")
        return export.build_snapshot(conn)["portfolio"]


@app.get("/snapshot")
def get_snapshot():
    """Everything at once - the same shape as report/data.json, for a
    frontend that wants one call instead of several."""
    with db.connect() as conn:
        return export.build_snapshot(conn)


@app.post("/research/{symbol}")
def research_symbol(symbol: str):
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
    # Reachable once a real provider is registered; classification of raw
    # news into signals isn't implemented (see providers/README.md step 5).
    raise HTTPException(status_code=501, detail="live provider configured but auto-research isn't implemented yet")
