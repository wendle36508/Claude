"""A computed composite score from a thesis's own logged signals, run
alongside (never instead of) the human conviction rating.

Conviction is a gut call typed in at thesis creation and never revisited.
The composite score is mechanical: it turns each signal's direction and
weight into a number in [-1, 1] and averages them. The two are meant to be
compared, not merged - `compare_to_conviction` flags when the systematic
read of the evidence disagrees with the gut call, which is exactly the
moment worth a second look.

The weights that go into the composite score can come from two places:
  - manual: the --weight each signal was logged with (the default; this is
    "how much I judged this signal to matter" at the time).
  - learned: derived from report.signal_calibration_by_name - for a signal
    name observed enough times, how much its bullish calls actually beat
    its bearish calls in realized return. This is where the system is
    supposed to get smarter than the person using it, but it needs real
    return history to do that. With as little data as this tracker
    currently has, learned weights mostly fall back to neutral (1.0) - the
    machinery is real, the learning isn't yet.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from wealth_lab import db, report

DEFAULT_WEIGHT = 1.0
MIN_OBSERVATIONS_TO_LEARN = 3
MAX_LEARNED_WEIGHT = 3.0


def _direction_sign(direction: str) -> float:
    return {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}[direction]


@dataclass
class SignalContribution:
    name: str
    direction: str
    weight: float
    contribution: float  # weight * sign, before normalization


@dataclass
class ScoreResult:
    thesis_id: int
    score: float  # normalized weighted average in [-1, 1]
    n_signals: int
    breakdown: list[SignalContribution]
    weights_used: str  # "manual" or "learned"


def learned_signal_weights(conn: sqlite3.Connection, min_n: int = MIN_OBSERVATIONS_TO_LEARN) -> dict[str, float]:
    """Derive a trust weight per signal *name* from historical calibration.

    weight = clip(|avg_return(bullish) - avg_return(bearish)| * 10, 0.25, MAX_LEARNED_WEIGHT)

    A signal name needs at least `min_n` total observations across both
    directions before it gets anything other than the default weight - with
    only a handful of theses logged, that threshold will rarely be met, and
    this correctly returns close to nothing until it is.
    """
    returns = report.thesis_returns(conn)
    by_name = report.signal_calibration_by_name(conn, returns)

    weights: dict[str, float] = {}
    for name, by_direction in by_name.items():
        total_n = sum(d["n"] for d in by_direction.values())
        if total_n < min_n:
            continue
        bull = by_direction.get("bullish", {}).get("avg_return")
        bear = by_direction.get("bearish", {}).get("avg_return")
        if bull is None or bear is None:
            # only one side has ever fired for this signal - no spread to learn from yet
            continue
        spread = abs(bull - bear)
        weights[name] = min(max(spread * 10, 0.25), MAX_LEARNED_WEIGHT)
    return weights


def composite_score(
    conn: sqlite3.Connection, thesis_id: int, signal_weights: Optional[dict[str, float]] = None
) -> Optional[ScoreResult]:
    signals = db.list_signals(conn, thesis_id)
    if not signals:
        return None

    breakdown = []
    weighted_sum = 0.0
    weight_total = 0.0
    for sig in signals:
        weight = signal_weights.get(sig["name"], DEFAULT_WEIGHT) if signal_weights else sig["weight"]
        sign = _direction_sign(sig["direction"])
        contribution = weight * sign
        breakdown.append(
            SignalContribution(name=sig["name"], direction=sig["direction"], weight=weight, contribution=contribution)
        )
        weighted_sum += contribution
        weight_total += weight

    score = weighted_sum / weight_total if weight_total > 0 else 0.0
    return ScoreResult(
        thesis_id=thesis_id,
        score=score,
        n_signals=len(signals),
        breakdown=breakdown,
        weights_used="learned" if signal_weights else "manual",
    )


def score_bucket(score: float) -> str:
    if score <= -0.5:
        return "bearish"
    if score < 0.5:
        return "mixed/neutral"
    return "bullish"


def score_calibration(conn: sqlite3.Connection, signal_weights: Optional[dict[str, float]] = None) -> dict[str, dict]:
    """Average realized return bucketed by composite score, mirroring
    report.conviction_calibration - lets the two be compared directly to see
    which one the returns actually agreed with."""
    returns = report.thesis_returns(conn)
    buckets: dict[str, list[float]] = {}
    for r in returns:
        result = composite_score(conn, r.thesis_id, signal_weights=signal_weights)
        if result is None:
            continue
        buckets.setdefault(score_bucket(result.score), []).append(r.pct_return)
    return {
        bucket: {"n": len(vals), "avg_return": sum(vals) / len(vals)}
        for bucket, vals in buckets.items()
    }


def compare_to_conviction(conn: sqlite3.Connection, thesis_id: int, result: ScoreResult) -> dict:
    thesis = db.get_thesis(conn, thesis_id)
    conviction_normalized = (thesis["conviction"] - 3) / 2  # 1..5 -> -1..1
    delta = result.score - conviction_normalized
    return {
        "conviction": thesis["conviction"],
        "conviction_normalized": conviction_normalized,
        "signal_score": result.score,
        "delta": delta,
        "agrees": abs(delta) < 0.5,
    }
