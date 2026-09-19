"""Builds a single JSON snapshot of everything the CLI can show - every
thesis with its full score/confidence/range/risk breakdown and signals,
plus portfolio-level metrics - for the dashboard artifact to render.

    python -m wealth_lab.export                  # writes report/data.json
    python -m wealth_lab.export --out path.json

The dashboard is a static page: it has no backend, so it reads this file
instead of querying the database live. Re-run this and republish the
artifact's data.json whenever the tracker data changes and you want the
dashboard to reflect it - the HTML/JS itself doesn't need to change.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from wealth_lab import db, portfolio, risk, scoring

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "report" / "data.json"
BENCHMARK_SYMBOL = "SPY"


def _thesis_snapshot(conn, t) -> dict:
    snap = db.latest_snapshot(conn, t["id"])
    latest_price = snap["price"] if snap else t["entry_price"]
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

    result = scoring.composite_score(conn, t["id"])
    score = confidence = rng = None
    category_scores = {}
    if result is not None:
        conf = scoring.confidence(result)
        range_result = scoring.expected_return_range(conn, result, conf, entry_price=t["entry_price"])
        score = {"value": result.score, "n_signals": result.n_signals, "weights_used": result.weights_used}
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
            cat_result = scoring.category_score(conn, t["id"], category)
            if cat_result is not None:
                category_scores[category] = {"value": cat_result.score, "n_signals": cat_result.n_signals}

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

    return {
        "id": t["id"], "symbol": t["symbol"], "name": t["name"], "sector": t["sector"],
        "asset_type": t["asset_type"], "status": t["status"], "conviction": t["conviction"],
        "thesis": t["thesis"],
        "entry_price": t["entry_price"], "entry_date": t["entry_date"],
        "latest_price": latest_price, "return_pct": return_pct,
        "position": position,
        "score": score, "confidence": confidence, "range": rng, "category_scores": category_scores,
        "risk": risk_metrics,
        "signals": signals,
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
        }

    theses = [_thesis_snapshot(conn, t) for t in db.list_theses(conn)]

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
