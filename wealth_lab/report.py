"""Calibration reporting: did conviction and individual signals actually predict returns?

This is the feedback loop the tracker exists for. It doesn't try to be a
backtester — it just honestly compares what you believed (conviction,
signals) against what happened (snapshot price vs entry price), so the
signal set can be pruned and reweighted over time instead of staying fixed.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from statistics import mean
from typing import Optional

from wealth_lab import db


@dataclass
class ThesisReturn:
    thesis_id: int
    symbol: str
    conviction: int
    status: str
    entry_price: float
    latest_price: float
    pct_return: float


def thesis_returns(conn: sqlite3.Connection) -> list[ThesisReturn]:
    out: list[ThesisReturn] = []
    for row in db.list_theses(conn):
        if row["entry_price"] is None:
            continue
        snap = db.latest_snapshot(conn, row["id"])
        if snap is None:
            continue
        pct = (snap["price"] - row["entry_price"]) / row["entry_price"]
        out.append(
            ThesisReturn(
                thesis_id=row["id"],
                symbol=row["symbol"],
                conviction=row["conviction"],
                status=row["status"],
                entry_price=row["entry_price"],
                latest_price=snap["price"],
                pct_return=pct,
            )
        )
    return out


def conviction_calibration(returns: list[ThesisReturn]) -> dict[int, dict]:
    """Average return per conviction level (1-5). A well-calibrated tracker
    should show returns rising with conviction; if it doesn't, conviction
    scoring itself is the thing to fix next."""
    buckets: dict[int, list[float]] = {}
    for r in returns:
        buckets.setdefault(r.conviction, []).append(r.pct_return)
    return {
        level: {"n": len(vals), "avg_return": mean(vals)}
        for level, vals in sorted(buckets.items())
    }


def signal_calibration(conn: sqlite3.Connection, returns: list[ThesisReturn]) -> dict[str, dict]:
    """Average return of theses grouped by (signal name, direction). Lets you
    see, e.g., whether 'insider_buying: bullish' theses actually outperformed
    'insider_buying: bearish' or neutral ones — the signal-level version of
    the conviction check above."""
    return_by_thesis = {r.thesis_id: r.pct_return for r in returns}
    buckets: dict[str, list[float]] = {}
    for r in returns:
        for sig in db.list_signals(conn, r.thesis_id):
            key = f"{sig['name']}:{sig['direction']}"
            buckets.setdefault(key, []).append(return_by_thesis[r.thesis_id])
    return {
        key: {"n": len(vals), "avg_return": mean(vals)}
        for key, vals in sorted(buckets.items())
    }


def signal_calibration_by_name(conn: sqlite3.Connection, returns: list[ThesisReturn]) -> dict[str, dict[str, dict]]:
    """Same data as signal_calibration, grouped by signal name first and
    direction second - e.g. {"hiring_growth": {"bullish": {...}, "bearish": {...}}}.
    This is what scoring.py needs to ask "when this signal type has fired
    bullish vs bearish, which side was actually right?" per name."""
    return_by_thesis = {r.thesis_id: r.pct_return for r in returns}
    buckets: dict[str, dict[str, list[float]]] = {}
    for r in returns:
        for sig in db.list_signals(conn, r.thesis_id):
            buckets.setdefault(sig["name"], {}).setdefault(sig["direction"], []).append(
                return_by_thesis[r.thesis_id]
            )
    return {
        name: {
            direction: {"n": len(vals), "avg_return": mean(vals)}
            for direction, vals in directions.items()
        }
        for name, directions in buckets.items()
    }


def hit_rate(conn: sqlite3.Connection) -> Optional[dict]:
    closed = [t for t in db.list_theses(conn) if t["status"] in ("closed_win", "closed_loss", "closed_flat")]
    if not closed:
        return None
    wins = sum(1 for t in closed if t["status"] == "closed_win")
    return {"n_closed": len(closed), "wins": wins, "hit_rate": wins / len(closed)}
