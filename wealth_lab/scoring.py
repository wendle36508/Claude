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

live_quant_signals() is a fourth input, alongside manual/learned/decayed
weights above: real P/E, P/B, and beta from a live DataProvider, turned
into synthetic valuation/risk signals and blended into composite_score()/
category_score() through the exact same weighted-average engine every
logged signal already goes through - not a second formula. It's the only
part of this module that talks to a live provider, and it degrades to
exactly today's behavior (nothing added) with the default MockProvider or
any symbol the provider has no data for.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from wealth_lab import db, report
from wealth_lab.providers import get_provider

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

# Public-facing 0-100 score bands, in descending order (checked top to
# bottom). Deliberately not "Buy"/"Sell" - this tool says elsewhere it isn't
# investment advice, and a 0-100 number with a buy/sell label on it reads
# like advice regardless of the disclaimer. These describe what the
# evidence leans toward, not what to do about it.
PUBLIC_SCORE_BANDS = (
    (80, "Strongly Bullish"),
    (65, "Bullish"),
    (45, "Neutral / Mixed"),
    (30, "Bearish"),
    (0, "Strongly Bearish"),
)

# Reference points live_quant_signals() measures a stock's P/E and P/B
# against to decide bullish/bearish and by how much. Flat, unsegmented
# benchmarks - "roughly what an average large-cap looks like," not
# sector-adjusted or fitted to anything - so a capital-intensive utility
# and a software company get compared to the same yardstick. Documented
# here so the choice is auditable, not hidden inside a formula.
LIVE_BENCHMARK_PE = 20.0
LIVE_BENCHMARK_PB = 3.0
LIVE_BENCHMARK_BETA = 1.0
LIVE_SIGNAL_WEIGHT = 1.0  # matches DEFAULT_WEIGHT - a live reading counts the same as one manually logged signal
MIN_LIVE_SIGNAL_MAGNITUDE = 0.1  # floor so a near-benchmark reading still counts as weak evidence, not zero


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


@dataclass
class PublicScoreResult:
    score_100: int  # 0-100, 50 = neutral/no clear read
    label: str  # plain-language band, e.g. "Bullish"
    n_signals: int  # how many signals the score is based on, shown alongside
                     # the number since a shrunk score alone can't distinguish
                     # "genuinely mixed evidence" from "barely any evidence"


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


def _quant_reading_to_signal(name: str, category: str, deviation: float, as_of: datetime) -> dict:
    """deviation is (benchmark - actual) / benchmark for a "lower is
    bullish" metric like P/E, already sign-flipped by the caller for a
    "higher is bullish" one - so positive deviation always means bullish
    here. Clipped to [-1, 1] and floored at MIN_LIVE_SIGNAL_MAGNITUDE so
    a reading exactly at the benchmark still registers as weak evidence
    rather than contributing nothing."""
    magnitude = max(min(abs(deviation), 1.0), MIN_LIVE_SIGNAL_MAGNITUDE)
    direction = "bullish" if deviation > 0 else "bearish" if deviation < 0 else "neutral"
    return {
        "name": name, "category": category, "direction": direction,
        "weight": LIVE_SIGNAL_WEIGHT * magnitude,
        "rationale": None, "source": None,
        "recorded_at": as_of.isoformat(),
    }


def live_quant_signals(symbol: str, provider=None, as_of: Optional[datetime] = None) -> list[dict]:
    """Real P/E, P/B, and beta - fetched live via a DataProvider and turned
    into synthetic signal dicts with the same shape db.list_signals() rows
    have, so composite_score()/category_score() can blend them into the
    existing weighted-average engine instead of needing a second formula.
    Each one is timestamped as of right now, so it always decays as fresh -
    that's the actual sense in which this is "live": every call re-derives
    it from the provider, nothing is cached or stored in the database.

    Only valuation (P/E, P/B) and risk (beta) get a live signal. Finnhub's
    free tier has no reliable forward-looking or revenue-growth numbers to
    honestly turn into a growth/catalyst/macro signal, so those categories
    stay exactly what they are today: whatever's actually been researched
    and logged - this never fabricates evidence for a category real data
    isn't available for.

    Returns [] - never raises, never fabricates - when: no live provider is
    configured (provider.is_live is False, the default MockProvider case),
    the provider has no data for this symbol, or a metric field is missing
    or non-positive (a P/E from negative earnings isn't "cheap," it's
    undefined for this heuristic, so it's skipped rather than misread)."""
    if provider is None:
        provider = get_provider()
    if not provider.is_live:
        return []

    metrics = provider.get_quant_metrics(symbol)
    if metrics is None:
        return []

    as_of = as_of or datetime.now(timezone.utc)
    out = []

    if metrics.pe_ttm is not None and metrics.pe_ttm > 0:
        deviation = (LIVE_BENCHMARK_PE - metrics.pe_ttm) / LIVE_BENCHMARK_PE
        out.append(_quant_reading_to_signal("live_pe_ratio", "valuation", deviation, as_of))

    if metrics.pb_ttm is not None and metrics.pb_ttm > 0:
        deviation = (LIVE_BENCHMARK_PB - metrics.pb_ttm) / LIVE_BENCHMARK_PB
        out.append(_quant_reading_to_signal("live_price_to_book", "valuation", deviation, as_of))

    if metrics.beta is not None:
        # same "lower is bullish" shape as P/E and P/B: higher beta = more
        # volatile = riskier = bearish in the risk category's convention
        # (bearish there means "a risk factor"), so a beta below the
        # benchmark is the bullish (less-risky) direction
        deviation = (LIVE_BENCHMARK_BETA - metrics.beta) / LIVE_BENCHMARK_BETA
        out.append(_quant_reading_to_signal("live_beta", "risk", deviation, as_of))

    return out


def _score_signals(
    thesis_id: int,
    signals: list,
    signal_weights: Optional[dict[str, float]],
    half_life_days: Optional[float],
    as_of: datetime,
) -> Optional[ScoreResult]:
    if not signals:
        return None

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


def composite_score(
    conn: sqlite3.Connection,
    thesis_id: int,
    signal_weights: Optional[dict[str, float]] = None,
    half_life_days: Optional[float] = DECAY_HALF_LIFE_DAYS,
    as_of: Optional[datetime] = None,
    live_signals: Optional[list[dict]] = None,
) -> Optional[ScoreResult]:
    """half_life_days=None disables decay (every signal counts at full
    weight regardless of age) - useful for inspecting the raw, undecayed
    score. as_of defaults to now; tests and the calibration model pass it
    explicitly so results don't drift with wall-clock time. live_signals,
    from live_quant_signals(), are blended in alongside the logged ones
    through this same weighted-average engine - pass None (the default)
    to score on logged signals only, exactly today's behavior."""
    signals = list(db.list_signals(conn, thesis_id)) + list(live_signals or [])
    return _score_signals(thesis_id, signals, signal_weights, half_life_days, as_of or datetime.now(timezone.utc))


def category_score(
    conn: sqlite3.Connection,
    thesis_id: int,
    category: str,
    signal_weights: Optional[dict[str, float]] = None,
    half_life_days: Optional[float] = DECAY_HALF_LIFE_DAYS,
    as_of: Optional[datetime] = None,
    live_signals: Optional[list[dict]] = None,
) -> Optional[ScoreResult]:
    """Same math as composite_score, restricted to one signal category
    (growth / valuation / risk / catalyst / macro / other) - the "growth
    potential" or "risk" sub-score for a thesis, not just one overall
    number. Returns None if no signals (logged or live) fall in that
    category. live_signals works the same as in composite_score() - pass
    the same list here and to composite_score() so both see the same live
    reading rather than fetching it twice."""
    signals = [s for s in db.list_signals(conn, thesis_id) if s["category"] == category]
    signals += [s for s in (live_signals or []) if s["category"] == category]
    return _score_signals(thesis_id, signals, signal_weights, half_life_days, as_of or datetime.now(timezone.utc))


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


def public_score(result: ScoreResult, conf: ConfidenceResult) -> PublicScoreResult:
    """The -1..+1 composite score, confidence-shrunk and rescaled to 0-100
    for readers who aren't going to cross-reference a separate confidence
    field. score_100 = 50 + (raw_score * confidence * 50): a maximally
    bullish score with full confidence hits 100, but a single thin,
    just-logged signal - which scores +1.00 raw exactly like six agreeing
    signals over three months does - only nudges the 0-100 number a little
    past 50, because its confidence is still low. Zero signals or exactly
    canceling ones both land on precisely 50, which is why n_signals rides
    along: 50 from no evidence and 50 from genuinely mixed evidence are
    different claims, and the label alone can't tell a reader which.

    This does not replace composite_score()'s -1..+1 output - that's still
    what calibration, backtesting, and compare_to_conviction() use. This is
    a presentation-layer number derived from it, for the parts of the app
    (the public dashboard) where a lay reader needs one easy number rather
    than a score/confidence pair to reason about themselves."""
    score_100 = round(50 + (result.score * conf.confidence * 50))
    score_100 = max(0, min(100, score_100))
    label = next(text for threshold, text in PUBLIC_SCORE_BANDS if score_100 >= threshold)
    return PublicScoreResult(score_100=score_100, label=label, n_signals=result.n_signals)


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
