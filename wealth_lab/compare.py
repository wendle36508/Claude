"""A side-by-side view across every thesis - one row each, every metric its
own column. Deliberately not a single blended ranking number: composite
score, confidence, expected return range, and volatility answer different
questions (direction of the evidence, how much to trust it, plausible
range, how bumpy the ride), and collapsing them into one score would hide
which of those is actually driving a high or low rank. Sort by whichever
column matters for the question being asked.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from wealth_lab import db, risk, scoring

SORTABLE_COLUMNS = (
    "symbol", "conviction", "score", "public_score", "confidence", "floor", "ceiling", "volatility",
)


@dataclass
class ComparisonRow:
    thesis_id: int
    symbol: str
    sector: Optional[str]
    status: str
    conviction: int
    score: Optional[float]
    public_score: Optional[int]  # 0-100, confidence-shrunk - see scoring.public_score()
    public_score_label: Optional[str]
    confidence: Optional[float]
    confidence_band: Optional[str]
    floor_return: Optional[float]
    base_return: Optional[float]
    ceiling_return: Optional[float]
    volatility: Optional[float]


def build_comparison(conn: sqlite3.Connection, status: Optional[str] = None) -> list[ComparisonRow]:
    rows = []
    for t in db.list_theses(conn, status=status):
        result = scoring.composite_score(conn, t["id"])
        conf = scoring.confidence(result) if result else None
        pub = scoring.public_score(result, conf) if result else None
        rng = scoring.expected_return_range(conn, result, conf, entry_price=t["entry_price"]) if result else None
        vol = risk.compute_risk_metrics(conn, t["id"]).volatility

        rows.append(
            ComparisonRow(
                thesis_id=t["id"],
                symbol=t["symbol"],
                sector=t["sector"],
                status=t["status"],
                conviction=t["conviction"],
                score=result.score if result else None,
                public_score=pub.score_100 if pub else None,
                public_score_label=pub.label if pub else None,
                confidence=conf.confidence if conf else None,
                confidence_band=conf.band if conf else None,
                floor_return=rng.floor_return if rng else None,
                base_return=rng.base_return if rng else None,
                ceiling_return=rng.ceiling_return if rng else None,
                volatility=vol,
            )
        )
    return rows


def sort_rows(rows: list[ComparisonRow], by: str, descending: bool = True) -> list[ComparisonRow]:
    if by not in SORTABLE_COLUMNS:
        raise ValueError(f"sort column must be one of {SORTABLE_COLUMNS}, got {by!r}")

    key_map = {
        "symbol": lambda r: r.symbol,
        "conviction": lambda r: r.conviction,
        "score": lambda r: r.score,
        "public_score": lambda r: r.public_score,
        "confidence": lambda r: r.confidence,
        "floor": lambda r: r.floor_return,
        "ceiling": lambda r: r.ceiling_return,
        "volatility": lambda r: r.volatility,
    }
    key = key_map[by]

    # Missing data sorts last regardless of direction - a thesis with no
    # signals yet shouldn't read as "worst score", it should read as "no
    # score", so it's excluded from the ranked part and appended after.
    with_value = [r for r in rows if key(r) is not None]
    without_value = [r for r in rows if key(r) is None]
    with_value.sort(key=key, reverse=descending)
    return with_value + without_value
