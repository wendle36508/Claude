"""Digest for a scheduled run: what needs attention, and how calibration looks.

Meant to be invoked periodically (daily/weekly) by a scheduler, not by hand,
and specifically at the START of that pass - it's the "what actually needs
a fresh price snapshot today" filter, not a general status report. It does
not fetch prices itself: this session's network is locked to package
registries, so there is no live market-data source to call from plain
Python. Instead it flags theses that have gone stale (no price check-in
recently) so whoever runs the scan - a human, or the agent driving the
daily research Routine - knows which symbols specifically need a fresh
price looked up, rather than re-checking every name's price every day
regardless of whether it's actually gone stale. A future live PriceProvider
plugs in at fetch_price() below; nothing else here needs to change.

This is deliberately the *only* place "is this thesis stale" gets decided -
the daily Routine calls `python -m wealth_lab.scan` for that list instead of
re-deriving its own notion of staleness from `list`/`portfolio` output.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from wealth_lab import db, report

STALE_AFTER_DAYS = 7


def fetch_price(symbol: str) -> float | None:
    """Extension point for a live data provider (Yahoo/Stooq/broker API/etc).

    Returns None when no live source is wired up, which is the current state
    of this environment - callers must not assume this ever succeeds here.
    A real implementation should return the latest price for `symbol` or
    raise, not return a placeholder value.
    """
    return None


def stale_theses(conn: sqlite3.Connection, days: int = STALE_AFTER_DAYS) -> list[sqlite3.Row]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for t in db.list_theses(conn, status="open"):
        snap = db.latest_snapshot(conn, t["id"])
        last = snap["recorded_at"] if snap else t["created_at"]
        if datetime.fromisoformat(last) < cutoff:
            out.append(t)
    return out


def run_scan(conn: sqlite3.Connection) -> str:
    lines = [f"=== wealth_lab scan @ {datetime.now(timezone.utc).isoformat(timespec='seconds')} ==="]

    open_theses = db.list_theses(conn, status="open")
    lines.append(f"open theses: {len(open_theses)}")

    stale = stale_theses(conn)
    if stale:
        lines.append(f"stale (no price check-in in {STALE_AFTER_DAYS}+ days) - fetch a fresh price and "
                      f"`snapshot` these {len(stale)} today:")
        for t in stale:
            lines.append(f"  #{t['id']} {t['symbol']}")
    else:
        lines.append("no stale theses - every open position has a recent price check-in")

    returns = report.thesis_returns(conn)
    if returns:
        hr = report.hit_rate(conn)
        lines.append(f"theses with tracked return: {len(returns)}")
        if hr:
            lines.append(f"hit rate on closed theses: {hr['wins']}/{hr['n_closed']} ({hr['hit_rate'] * 100:.0f}%)")

    return "\n".join(lines)


if __name__ == "__main__":
    with db.connect() as conn:
        print(run_scan(conn))
