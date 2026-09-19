"""Tracks coverage of the lookup tool's target universe (S&P 500) against
what's actually been researched in the tracker database.

"Every publicly tradeable stock" isn't buildable by hand at real research
depth - see universe_sp500.csv's commit message. S&P 500 is the honest,
bounded stand-in for "every stock that matters," confirmed with the user.
This module answers the two questions that scope depends on: how much of
it is covered so far, and what should get researched next - so the daily
Routine (and anyone checking progress) has a single source of truth for
both, the same way scan.py is the single source of truth for staleness.

Coverage counts a symbol as covered if *any* thesis exists for it,
regardless of status (open or closed) - re-researching a closed-out name
isn't what this tracks; scan.py's staleness check handles freshness of
already-open theses separately.
"""

from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from wealth_lab import db

UNIVERSE_PATH = Path(__file__).resolve().parent / "universe_sp500.csv"


@dataclass
class UniverseEntry:
    symbol: str
    name: str
    sector: str


@dataclass
class CoverageReport:
    total: int
    researched: int
    remaining: int
    by_sector: dict[str, tuple[int, int]]  # sector -> (researched, total)

    @property
    def pct(self) -> float:
        return (self.researched / self.total * 100) if self.total else 0.0


def load_universe(path: Path | None = None) -> list[UniverseEntry]:
    path = path or UNIVERSE_PATH
    with open(path, newline="", encoding="utf-8") as f:
        return [
            UniverseEntry(symbol=row["symbol"].upper(), name=row["name"], sector=row["sector"])
            for row in csv.DictReader(f)
        ]


def researched_symbols(conn: sqlite3.Connection) -> set[str]:
    return {t["symbol"].upper() for t in db.list_theses(conn)}


def coverage(conn: sqlite3.Connection, universe: list[UniverseEntry] | None = None) -> CoverageReport:
    universe = universe if universe is not None else load_universe()
    have = researched_symbols(conn)

    by_sector_total: dict[str, int] = defaultdict(int)
    by_sector_researched: dict[str, int] = defaultdict(int)
    for e in universe:
        by_sector_total[e.sector] += 1
        if e.symbol in have:
            by_sector_researched[e.sector] += 1

    by_sector = {
        sector: (by_sector_researched[sector], total) for sector, total in sorted(by_sector_total.items())
    }
    researched = sum(r for r, _ in by_sector.values())
    return CoverageReport(
        total=len(universe), researched=researched, remaining=len(universe) - researched, by_sector=by_sector
    )


def next_batch(
    conn: sqlite3.Connection, n: int = 10, universe: list[UniverseEntry] | None = None
) -> list[UniverseEntry]:
    """The next N unresearched names, round-robin across sectors rather than
    in file order - so a batch (and coverage generally) grows breadth-first
    across the market instead of exhausting one GICS sector before touching
    the next, since the CSV happens to be grouped by sector already."""
    universe = universe if universe is not None else load_universe()
    have = researched_symbols(conn)

    by_sector: dict[str, list[UniverseEntry]] = defaultdict(list)
    for e in universe:
        if e.symbol not in have:
            by_sector[e.sector].append(e)

    queues = [by_sector[s] for s in sorted(by_sector)]
    batch: list[UniverseEntry] = []
    i = 0
    while len(batch) < n and any(queues):
        q = queues[i % len(queues)]
        if q:
            batch.append(q.pop(0))
        i += 1
        if i > 10 * n + len(queues):  # safety valve, should never trigger
            break
    return batch[:n]


if __name__ == "__main__":
    with db.connect() as conn:
        report = coverage(conn)
        print(f"S&P 500 coverage: {report.researched}/{report.total} ({report.pct:.1f}%)")
        for sector, (have, total) in report.by_sector.items():
            print(f"  {sector:<28} {have:>3}/{total}")
        nxt = next_batch(conn, n=10)
        if nxt:
            print("\nnext up:")
            for e in nxt:
                print(f"  {e.symbol:<6} {e.name} ({e.sector})")
