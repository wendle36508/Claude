"""A computed composite score from a thesis's own logged signals, run
alongside (never instead of) the human conviction rating - plus a
confidence read on that score and a heuristic expected-return range.

Conviction is a gut call typed in at thesis creation and never revisited.
The composite score is mechanical: it turns each signal's direction and
weight into a number in [-1, 1] and averages them. The two are meant to be
compared, not merged - `compare_to_conviction` flags when the systematic
read of the evidence disagrees with the gut call, which is exactly the
moment worth a second look.

The weights that go into the composite score can come from three places,
all stackable:
  - manual: the --weight each signal was logged with (the default; this is
    "how much I judged this signal to matter" at the time).
  - learned: derived from report.signal_calibration_by_name - for a signal
    name observed enough times, how much its bullish calls actually beat
    its bearish calls in realized return. Needs real return history to mean
    anything; with little data it falls back to neutral.
  - decayed: every signal's weight (manual or learned) is discounted by its
    age - a signal logged six months ago should count for less than one
    logged this morning, because the world it described may have moved on.

confidence() and expected_return_range() are the "how sure is this, and
what's the plausible range" layer on top of the score. Read the module-level
constants below before trusting their output: the range in particular is a
self-consistent heuristic derived from the scoring engine's own inputs
(how much evidence, how much it agrees, how fresh it is), not a valuation
model - it does not know this company's multiple, growth rate, or discount
rate. calibrate_range_model() is the honest fix for that: once enough
theses have closed with a known outcome, the range's width gets fit from
what actually happened instead of from an assumed constant.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from wealth_lab import db, report

DEFAULT_WEIGHT = 1.0
MIN_OBSERVATIONS_TO_LEARN = 3
MAX_LEARNED_WEIGHT = 3.0

# Decay: a signal's weight halves every DECAY_HALF_LIFE_DAYS. 120 days is an
# assumption (roughly one earnings cycle), not a fitted value - a signal
# about a contract win probably ages slower than one about a stock's
# intraday move, but the model doesn't yet distinguish signal *types* by
# how fast they go stale, only by how old they are.
DECAY_HALF_LIFE_DAYS = 120.0

# Confidence: how much total (decayed) weight counts as "fully covered"
# evidence. 3.0 ~= three independent, full-weight signals. Below that,
# confidence scales down linearly with how little evidence there is.
TARGET_WEIGHT_FOR_FULL_COVERAGE = 3.0

# Expected-return range: assumed swing for a maximally bullish/bearish,
# maximally confident thesis over its horizon, and the extra width added at
# zero confidence. Both are placeholders until calibrate_range_model() has
# enough closed theses to fit them from real outcomes instead.
DEFAULT_MAX_SWING = 0.25
DEFAULT_UNCERTAINTY_MULTIPLIER = 0.40
MIN_THESES_TO_CALIBRATE_RANGE = 8


def _direction_sign(direction: str) -> float:
    return {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}[direction]


def _age_days(recorded_at: str, as_of: datetime) -> float:
    recorded = datetime.fromisoformat(recorded_at)
    return max((as_of - recorded).total_seconds() / 86400.0, 0.0)


def decay_factor(age_days: float, half_life_days: float = DECAY_HALF_LIFE_DAYS) -> float:
    return 0.5 ** (age_days / half_life_days)


@dataclass
class SignalContribution:
    name: str
    direction: str
    base_weight: float
    age_days: float
    decay: float
    effective_weight: float  # base_weight * decay
    contribution: float  # effective_weight * sign, before normalization


@dataclass
class ScoreResult:
    thesis_id: int
    score: float  # normalized weighted average in [-1, 1]
    n_signals: int
    total_effective_weight: float
    breakdown: list[SignalContribution]
    weights_used: str  # "manual" or "learned"


@dataclass
class ConfidenceResult:
    coverage: float  # how much evidence, relative to TARGET_WEIGHT_FOR_FULL_COVERAGE
    agreement: float  # how much the signals agree in direction (= |score|)
    recency: float  # weighted-average freshness of the contributing signals
    confidence: float  # coverage * agreement * recency, in [0, 1]
    band: str  # "low" / "medium" / "high"


@dataclass
class RangeResult:
    floor_return: float
    base_return: float
    ceiling_return: float
    floor_price: Optional[float]
    base_price: Optional[float]
    ceiling_price: Optional[float]
    source: str  # "default" or "calibrated"


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
    conn: sqlite3.Connection,
    thesis_id: int,
    signal_weights: Optional[dict[str, float]] = None,
    half_life_days: Optional[float] = DECAY_HALF_LIFE_DAYS,
    as_of: Optional[datetime] = None,
) -> Optional[ScoreResult]:
    """half_life_days=None disables decay (every signal counts at full
    weight regardless of age) - useful for inspecting the raw, undecayed
    score. as_of defaults to now; tests and the calibration model pass it
    explicitly so results don't drift with wall-clock time."""
    signals = db.list_signals(conn, thesis_id)
    if not signals:
        return None

    as_of = as_of or datetime.now(timezone.utc)
    breakdown = []
    weighted_sum = 0.0
    weight_total = 0.0
    for sig in signals:
        base_weight = signal_weights.get(sig["name"], DEFAULT_WEIGHT) if signal_weights else sig["weight"]
        age = _age_days(sig["recorded_at"], as_of)
        decay = decay_factor(age, half_life_days) if half_life_days is not None else 1.0
        effective_weight = base_weight * decay
        sign = _direction_sign(sig["direction"])
        contribution = effective_weight * sign
        breakdown.append(
            SignalContribution(
                name=sig["name"], direction=sig["direction"], base_weight=base_weight,
                age_days=age, decay=decay, effective_weight=effective_weight, contribution=contribution,
            )
        )
        weighted_sum += contribution
        weight_total += effective_weight

    score = weighted_sum / weight_total if weight_total > 0 else 0.0
    return ScoreResult(
        thesis_id=thesis_id,
        score=score,
        n_signals=len(signals),
        total_effective_weight=weight_total,
        breakdown=breakdown,
        weights_used="learned" if signal_weights else "manual",
    )


def confidence(result: ScoreResult) -> ConfidenceResult:
    coverage = min(result.total_effective_weight / TARGET_WEIGHT_FOR_FULL_COVERAGE, 1.0)
    agreement = abs(result.score)

    if result.total_effective_weight > 0:
        recency = sum(c.decay * c.effective_weight for c in result.breakdown) / result.total_effective_weight
    else:
        recency = 0.0

    conf = coverage * agreement * recency
    band = "low" if conf < 0.33 else "medium" if conf < 0.66 else "high"
    return ConfidenceResult(coverage=coverage, agreement=agreement, recency=recency, confidence=conf, band=band)


def calibrate_range_model(conn: sqlite3.Connection, min_n: int = MIN_THESES_TO_CALIBRATE_RANGE) -> Optional[dict]:
    """Fit max_swing from real outcomes: the average realized |return| per
    unit of |composite score|, across every thesis that has both a score and
    a tracked return. Returns None (use the DEFAULT_* constants instead)
    until at least `min_n` theses qualify - with this tracker's current
    history, that's every call for a long while, which is the honest state
    to be in rather than fitting a line through three points."""
    returns = report.thesis_returns(conn)
    ratios = []
    for r in returns:
        result = composite_score(conn, r.thesis_id)
        if result is None or result.score == 0:
            continue
        ratios.append(abs(r.pct_return) / abs(result.score))

    if len(ratios) < min_n:
        return None
    return {"max_swing": sum(ratios) / len(ratios), "n": len(ratios)}


def expected_return_range(
    conn: sqlite3.Connection, result: ScoreResult, conf: ConfidenceResult, entry_price: Optional[float] = None
) -> RangeResult:
    """A confidence-scaled expected-return band, not a valuation model: it
    knows nothing about earnings, multiples, or discount rates. High
    confidence narrows the band toward the base estimate; low confidence
    widens it. See calibrate_range_model() for how the width is meant to
    stop being a guess."""
    fitted = calibrate_range_model(conn)
    max_swing = fitted["max_swing"] if fitted else DEFAULT_MAX_SWING
    source = "calibrated" if fitted else "default"

    base_return = result.score * max_swing
    width = (1 - conf.confidence) * DEFAULT_UNCERTAINTY_MULTIPLIER
    floor_return = base_return - width
    ceiling_return = base_return + width

    return RangeResult(
        floor_return=floor_return,
        base_return=base_return,
        ceiling_return=ceiling_return,
        floor_price=entry_price * (1 + floor_return) if entry_price else None,
        base_price=entry_price * (1 + base_return) if entry_price else None,
        ceiling_price=entry_price * (1 + ceiling_return) if entry_price else None,
        source=source,
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
