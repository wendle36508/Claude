"""Builds a single JSON snapshot of everything the CLI can show - every
thesis with its full score/confidence/range/risk breakdown and signals,
plus portfolio-level metrics - for the console dashboard to render.

    python -m wealth_lab.export                  # writes report/data.json
    python -m wealth_lab.export --out path.json

This function (thesis_snapshot -> build_snapshot) backs two different
things: this module's own CLI, which writes the static report/data.json
that a published Claude Artifact falls back to (it can't reach a live
API - see providers/README.md), and api.py's GET /snapshot, which the
API's own GET /dashboard route calls live on every request. Re-run this
CLI and republish data.json when you want the *static* fallback to
reflect current data; the live route needs nothing re-run, it queries
the database directly on each request.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from wealth_lab import db, ipo, portfolio, risk, scoring, sizing
from wealth_lab.providers import get_provider

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "report" / "data.json"
BENCHMARK_SYMBOL = "SPY"

# Process-local cache for live prices, same reasoning and shape as
# scoring.py's _LIVE_QUANT_CACHE - keeps a dashboard tracking 30+ stocks
# from burning through a free Finnhub key's 60-calls/minute limit on a
# single page load. A price is at most this many seconds stale.
_LIVE_PRICE_CACHE: dict[str, tuple[float, "float | None"]] = {}
LIVE_PRICE_CACHE_TTL_SECONDS = 60.0


def _live_price(symbol: str, provider) -> "float | None":
    if not provider.is_live:
        return None
    key = symbol.upper()
    now = time.monotonic()
    cached = _LIVE_PRICE_CACHE.get(key)
    if cached is not None and now - cached[0] < LIVE_PRICE_CACHE_TTL_SECONDS:
        return cached[1]
    price = provider.get_price(symbol)
    _LIVE_PRICE_CACHE[key] = (now, price)
    return price


def thesis_snapshot(conn, t) -> dict:
    snap = db.latest_snapshot(conn, t["id"])
    stored_price = snap["price"] if snap else t["entry_price"]
    live_price = _live_price(t["symbol"], get_provider())
    latest_price = live_price if live_price is not None else stored_price
    return_pct = None
    if t["entry_price"] and latest_price is not None:
        return_pct = (latest_price - t["entry_price"]) / t["entry_price"]

    pos = db.get_position_for_thesis(conn, t["id"])
    position = None
    if pos:
        market_value = pos["shares"] * (1.0 if t["asset_type"] == "cash" else (latest_price or 0))
        position = {
            "sleeve": pos["sleeve"],
            "target_weight": pos["target_weight"],
            "shares": pos["shares"],
            "cost_basis": pos["cost_basis"],
            "market_value": market_value,
        }

    # Fetched once and reused for the overall score and every category below,
    # so a live provider (once actually deployed - see providers/README.md)
    # only gets hit once per thesis, not once per category. [] with the
    # default MockProvider - see scoring.live_quant_signals()'s docstring.
    live_signals = scoring.live_quant_signals(t["symbol"])

    result = scoring.composite_score(conn, t["id"], live_signals=live_signals)
    score = public_score = confidence = rng = None
    category_scores = {}
    if result is not None:
        conf = scoring.confidence(result)
        pub = scoring.public_score(result, conf)
        range_result = scoring.expected_return_range(conn, result, conf, entry_price=t["entry_price"])
        score = {"value": result.score, "n_signals": result.n_signals, "weights_used": result.weights_used}
        public_score = {"value": pub.score_100, "label": pub.label, "n_signals": pub.n_signals}
        confidence = {
            "value": conf.confidence, "band": conf.band,
            "coverage": conf.coverage, "agreement": conf.agreement, "recency": conf.recency,
        }
        rng = {
            "floor": range_result.floor_return, "base": range_result.base_return,
            "ceiling": range_result.ceiling_return, "floor_price": range_result.floor_price,
            "base_price": range_result.base_price, "ceiling_price": range_result.ceiling_price,
            "source": range_result.source,
        }
        for category in db.SIGNAL_CATEGORIES:
            cat_result = scoring.category_score(conn, t["id"], category, live_signals=live_signals)
            if cat_result is not None:
                cat_conf = scoring.confidence(cat_result)
                cat_pub = scoring.public_score(cat_result, cat_conf)
                category_scores[category] = {
                    "value": cat_result.score, "n_signals": cat_result.n_signals,
                    "public_score": {"value": cat_pub.score_100, "label": cat_pub.label},
                }

    rm = risk.compute_risk_metrics(conn, t["id"])
    risk_metrics = {
        "sufficient": rm.sufficient, "n_snapshots": rm.n_snapshots, "n_returns": rm.n_returns,
        "volatility": rm.volatility, "sharpe": rm.sharpe, "max_drawdown": rm.max_drawdown,
    }

    signals = [
        {
            "name": s["name"], "category": s["category"], "direction": s["direction"],
            "weight": s["weight"], "rationale": s["rationale"], "source": s["source"],
            "recorded_at": s["recorded_at"],
        }
        for s in db.list_signals(conn, t["id"])
    ]

    ipo_block = None
    if t["asset_type"] == "ipo":
        details = db.get_ipo_details(conn, t["id"])
        if details is not None:
            lockup = ipo.lockup_status(conn, t["id"])
            gap = ipo.valuation_gap(conn, t["id"])
            ipo_block = {
                "disclosed_valuation": details["disclosed_valuation"],
                "disclosed_revenue": details["disclosed_revenue"],
                "expected_list_date": details["expected_list_date"],
                "actual_list_date": details["actual_list_date"],
                "notes": details["notes"],
                "lockup": {
                    "expiry_date": lockup.expiry_date, "is_estimate": lockup.is_estimate,
                    "days_until_expiry": lockup.days_until_expiry,
                },
                "valuation_gap": (
                    {
                        "ipo_multiple": gap.ipo_multiple, "peer_median": gap.peer_median,
                        "premium_to_peers": gap.premium_to_peers, "n_comps": gap.n_comps, "metric": gap.metric,
                    }
                    if gap else None
                ),
                "comparables": [
                    {"peer_symbol": c["peer_symbol"], "peer_name": c["peer_name"],
                     "metric": c["metric"], "peer_multiple": c["peer_multiple"], "source": c["source"]}
                    for c in db.list_comparables(conn, t["id"])
                ],
            }

    return {
        "id": t["id"], "symbol": t["symbol"], "name": t["name"], "sector": t["sector"],
        "asset_type": t["asset_type"], "status": t["status"], "conviction": t["conviction"],
        "thesis": t["thesis"],
        "entry_price": t["entry_price"], "entry_date": t["entry_date"],
        "latest_price": latest_price, "return_pct": return_pct,
        "position": position,
        "score": score, "public_score": public_score,
        "confidence": confidence, "range": rng, "category_scores": category_scores,
        "risk": risk_metrics,
        "signals": signals,
        "ipo": ipo_block,
        # Real-time headlines need a live provider (see providers/README.md) -
        # `live: false` here is the honest state until WEALTH_LAB_PROVIDER=finnhub
        # is actually deployed; the console dashboard shows this as "not
        # connected yet" rather than leaving the section looking broken or
        # silently reusing signal rationale as if it were a news feed.
        "news": {"live": False, "items": []},
    }


def build_snapshot(conn) -> dict:
    values = portfolio.current_values(conn)
    benchmark = db.get_thesis_by_symbol(conn, BENCHMARK_SYMBOL)
    benchmark_id = benchmark["id"] if benchmark else None
    starting_capital = 100_000.0  # matches seed_portfolio.py; the only place this is assumed

    portfolio_block = None
    if values:
        total = portfolio.total_value(values)
        rm = portfolio.portfolio_risk_metrics(conn, benchmark_thesis_id=benchmark_id)
        naive = portfolio.naive_volatility_upper_bound(conn)
        sizing_suggestions = [
            {
                "symbol": s.symbol, "conviction_magnitude": s.conviction_magnitude,
                "current_weight": s.current_weight, "suggested_weight": s.suggested_weight,
                "delta": s.delta,
            }
            for s in sizing.satellite_sizing(conn)
        ]
        portfolio_block = {
            "starting_capital": starting_capital,
            "total_value": total,
            "return_since_inception": portfolio.portfolio_return(values, starting_capital),
            "hhi": portfolio.herfindahl_index(values),
            "sleeve_weights": portfolio.sleeve_weights(values),
            "risk": {
                "sufficient": rm.sufficient, "volatility": rm.volatility, "sharpe": rm.sharpe,
                "max_drawdown": rm.max_drawdown, "beta_vs_benchmark": rm.beta_vs_benchmark,
                "n_snapshots": rm.n_snapshots,
            },
            "naive_volatility": (
                {
                    "weighted_volatility": naive.weighted_volatility,
                    "covered_weight": naive.covered_weight,
                    "n_positions_included": naive.n_positions_included,
                }
                if naive else None
            ),
            "sizing_suggestions": sizing_suggestions,
        }

    theses = [thesis_snapshot(conn, t) for t in db.list_theses(conn)]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "portfolio": portfolio_block,
        "theses": theses,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    with db.connect() as conn:
        snapshot = build_snapshot(conn)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, indent=2))
    print(f"wrote snapshot ({len(snapshot['theses'])} theses) to {args.out}")


if __name__ == "__main__":
    main()
