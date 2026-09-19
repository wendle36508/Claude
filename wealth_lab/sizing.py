"""Confidence-driven position sizing: what score x confidence would
suggest for satellite weights, computed and shown next to the actual
current weights - not applied.

This only re-splits weight *within* the satellite sleeve's existing total -
it doesn't touch the core sleeve (that's structural risk management, not a
signal-driven decision - see seed_portfolio.py) and it doesn't decide which
theses belong in the sleeve, only how much of the sleeve's pie each already-
funded one should get.

Deliberately not auto-applied. With only a handful of theses and one day of
signals, this formula can produce a real, sharp result - e.g. a position
whose bullish and bearish signals currently cancel to a 0.00 score gets a
conviction_magnitude of exactly 0, meaning the formula would zero it out
entirely in favor of whichever name currently has the clearest evidence.
That's the formula working correctly on the data it has, not a bug - but
it's also exactly the kind of day-one artifact that shouldn't move real
capital before more signal history exists to check it against.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from wealth_lab import db, scoring


@dataclass
class SizingSuggestion:
    thesis_id: int
    symbol: str
    conviction_magnitude: float  # |score| * confidence, in [0, 1]
    current_weight: float
    suggested_weight: float
    delta: float  # suggested - current


def satellite_sizing(
    conn: sqlite3.Connection, satellite_total_weight: Optional[float] = None
) -> list[SizingSuggestion]:
    positions = [p for p in db.list_positions(conn) if p["sleeve"] == "satellite"]
    if not positions:
        return []

    if satellite_total_weight is None:
        satellite_total_weight = sum(p["target_weight"] for p in positions)

    magnitudes = {}
    for p in positions:
        result = scoring.composite_score(conn, p["thesis_id"])
        if result is None:
            magnitudes[p["thesis_id"]] = 0.0
            continue
        conf = scoring.confidence(result)
        magnitudes[p["thesis_id"]] = abs(result.score) * conf.confidence

    total_magnitude = sum(magnitudes.values())

    suggestions = []
    for p in positions:
        mag = magnitudes[p["thesis_id"]]
        if total_magnitude > 0:
            suggested = mag / total_magnitude * satellite_total_weight
        else:
            # no differentiation available yet - equal split rather than an
            # arbitrary favorite, and rather than dividing by zero
            suggested = satellite_total_weight / len(positions)
        suggestions.append(
            SizingSuggestion(
                thesis_id=p["thesis_id"], symbol=p["symbol"],
                conviction_magnitude=mag, current_weight=p["target_weight"],
                suggested_weight=suggested, delta=suggested - p["target_weight"],
            )
        )
    return suggestions
