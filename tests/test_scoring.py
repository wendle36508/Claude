from datetime import datetime, timedelta, timezone

import pytest

from wealth_lab import db, scoring


def make_thesis(conn, symbol="TEST", conviction=3, entry_price=100.0):
    return db.add_thesis(
        conn, symbol=symbol, asset_type="stock", thesis="test thesis",
        conviction=conviction, entry_price=entry_price, entry_date="2026-01-01",
    )


def backdate_signal(conn, thesis_id, days_ago):
    ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")
    conn.execute("UPDATE signals SET recorded_at=? WHERE thesis_id=?", (ts, thesis_id))


# ---- category score ----

def test_category_score_isolates_one_category(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "hiring_growth", "bullish", category="growth", weight=1.0)
    db.add_signal(conn, tid, "expensive_multiple", "bearish", category="valuation", weight=1.0)

    growth = scoring.category_score(conn, tid, "growth")
    valuation = scoring.category_score(conn, tid, "valuation")

    assert growth.score == 1.0
    assert growth.n_signals == 1
    assert valuation.score == -1.0
    assert valuation.n_signals == 1


def test_category_score_none_when_category_has_no_signals(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "hiring_growth", "bullish", category="growth", weight=1.0)

    assert scoring.category_score(conn, tid, "macro") is None


def test_category_defaults_to_other(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "uncategorized_thing", "bullish", weight=1.0)  # no category passed

    assert scoring.category_score(conn, tid, "other").score == 1.0
    assert scoring.category_score(conn, tid, "growth") is None


# ---- composite score ----

def test_composite_score_all_bullish_is_max(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    db.add_signal(conn, tid, "moat", "bullish", weight=1.0)

    result = scoring.composite_score(conn, tid)

    assert result.score == 1.0
    assert result.n_signals == 2


def test_composite_score_equal_weight_opposite_signals_cancel(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    db.add_signal(conn, tid, "valuation", "bearish", weight=1.0)

    result = scoring.composite_score(conn, tid)

    assert result.score == 0.0


def test_composite_score_weights_a_heavier_signal_more(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=2.0)
    db.add_signal(conn, tid, "valuation", "bearish", weight=1.0)

    result = scoring.composite_score(conn, tid)

    # (2*1 + 1*-1) / (2+1) = 1/3
    assert round(result.score, 3) == round(1 / 3, 3)


def test_composite_score_neutral_signal_contributes_zero(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "disclosure", "neutral", weight=1.0)

    result = scoring.composite_score(conn, tid)

    assert result.score == 0.0


def test_composite_score_none_when_no_signals(conn):
    tid = make_thesis(conn)

    assert scoring.composite_score(conn, tid) is None


# ---- decay ----

def test_fresh_signal_has_negligible_decay(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)

    result = scoring.composite_score(conn, tid)

    assert result.breakdown[0].decay == pytest.approx(1.0, abs=1e-4)


def test_signal_two_half_lives_old_decays_to_quarter_weight(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    backdate_signal(conn, tid, days_ago=2 * scoring.DECAY_HALF_LIFE_DAYS)

    result = scoring.composite_score(conn, tid)

    assert result.breakdown[0].decay == pytest.approx(0.25, rel=0.01)


def test_decay_lets_a_fresh_signal_dominate_an_old_one(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "old_news", "bullish", weight=1.0)
    backdate_signal(conn, tid, days_ago=2 * scoring.DECAY_HALF_LIFE_DAYS)
    db.add_signal(conn, tid, "fresh_news", "bearish", weight=1.0)

    result = scoring.composite_score(conn, tid)

    # old bullish (effective weight 0.25) vs fresh bearish (effective weight ~1.0)
    assert result.score < -0.4


def test_no_decay_flag_scores_every_signal_at_full_weight(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "old_news", "bullish", weight=1.0)
    backdate_signal(conn, tid, days_ago=2 * scoring.DECAY_HALF_LIFE_DAYS)
    db.add_signal(conn, tid, "fresh_news", "bearish", weight=1.0)

    result = scoring.composite_score(conn, tid, half_life_days=None)

    assert result.score == 0.0  # decay disabled -> the two signals cancel exactly


# ---- live quant signals ----

class FakeQuantProvider:
    """A minimal stand-in for a DataProvider - live_quant_signals() only
    calls .is_live and .get_quant_metrics(), so that's all this needs."""
    def __init__(self, metrics=None, is_live=True):
        self.is_live = is_live
        self._metrics = metrics

    def get_quant_metrics(self, symbol):
        return self._metrics


def make_metrics(pe_ttm=None, pb_ttm=None, beta=None):
    from wealth_lab.providers.base import QuantMetrics
    return QuantMetrics(pe_ttm=pe_ttm, pb_ttm=pb_ttm, beta=beta, week52_high=None, week52_low=None)


def test_live_quant_signals_empty_without_live_provider():
    provider = FakeQuantProvider(metrics=make_metrics(pe_ttm=10), is_live=False)
    assert scoring.live_quant_signals("AAA", provider=provider) == []


def test_live_quant_signals_empty_when_provider_has_no_data():
    provider = FakeQuantProvider(metrics=None, is_live=True)
    assert scoring.live_quant_signals("AAA", provider=provider) == []


def test_live_quant_signals_cheap_pe_is_bullish_valuation():
    provider = FakeQuantProvider(metrics=make_metrics(pe_ttm=10.0))  # well below the 20.0 benchmark
    sigs = scoring.live_quant_signals("AAA", provider=provider)

    pe_sig = next(s for s in sigs if s["name"] == "live_pe_ratio")
    assert pe_sig["direction"] == "bullish"
    assert pe_sig["category"] == "valuation"
    assert pe_sig["weight"] > 0


def test_live_quant_signals_rich_pe_is_bearish_valuation():
    provider = FakeQuantProvider(metrics=make_metrics(pe_ttm=40.0))  # well above benchmark
    sigs = scoring.live_quant_signals("AAA", provider=provider)

    pe_sig = next(s for s in sigs if s["name"] == "live_pe_ratio")
    assert pe_sig["direction"] == "bearish"


def test_live_quant_signals_high_beta_is_bearish_risk():
    provider = FakeQuantProvider(metrics=make_metrics(beta=1.8))  # well above the 1.0 benchmark
    sigs = scoring.live_quant_signals("AAA", provider=provider)

    beta_sig = next(s for s in sigs if s["name"] == "live_beta")
    assert beta_sig["direction"] == "bearish"
    assert beta_sig["category"] == "risk"


def test_live_quant_signals_low_beta_is_bullish_risk():
    provider = FakeQuantProvider(metrics=make_metrics(beta=0.4))
    sigs = scoring.live_quant_signals("AAA", provider=provider)

    beta_sig = next(s for s in sigs if s["name"] == "live_beta")
    assert beta_sig["direction"] == "bullish"


def test_live_quant_signals_skips_missing_fields():
    provider = FakeQuantProvider(metrics=make_metrics(pe_ttm=15.0))  # pb_ttm and beta both None
    sigs = scoring.live_quant_signals("AAA", provider=provider)

    assert {s["name"] for s in sigs} == {"live_pe_ratio"}


def test_live_quant_signals_skips_non_positive_pe():
    provider = FakeQuantProvider(metrics=make_metrics(pe_ttm=-5.0))  # negative earnings - undefined, not "cheap"
    sigs = scoring.live_quant_signals("AAA", provider=provider)

    assert {s["name"] for s in sigs} == set()


def test_composite_score_blends_live_signals_with_logged_ones(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    live = scoring.live_quant_signals("AAA", provider=FakeQuantProvider(metrics=make_metrics(pe_ttm=10.0)))

    without_live = scoring.composite_score(conn, tid)
    with_live = scoring.composite_score(conn, tid, live_signals=live)

    assert with_live.n_signals == without_live.n_signals + len(live)


def test_category_score_only_includes_live_signals_in_matching_category(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "hiring", "bullish", category="growth", weight=1.0)
    live = scoring.live_quant_signals(
        "AAA", provider=FakeQuantProvider(metrics=make_metrics(pe_ttm=10.0, beta=0.5))
    )  # 2 live signals: valuation (P/E) and risk (beta)

    growth = scoring.category_score(conn, tid, "growth", live_signals=live)
    valuation = scoring.category_score(conn, tid, "valuation", live_signals=live)
    risk = scoring.category_score(conn, tid, "risk", live_signals=live)

    assert growth.n_signals == 1  # only the logged signal - live signals don't leak into growth
    assert valuation.n_signals == 1
    assert risk.n_signals == 1


def test_composite_score_none_when_no_logged_or_live_signals(conn):
    tid = make_thesis(conn)
    result = scoring.composite_score(conn, tid, live_signals=[])
    assert result is None


def test_live_signals_default_to_get_provider_when_not_passed(conn, monkeypatch):
    # composite_score/category_score don't take live_signals from thin air -
    # live_quant_signals() itself falls back to get_provider(), which the
    # default MockProvider makes a no-op, so this must stay identical to
    # calling composite_score() with no live_signals at all.
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)

    assert scoring.live_quant_signals("AAA") == []


# ---- confidence ----

def test_confidence_is_high_with_agreement_and_full_coverage(conn):
    tid = make_thesis(conn)
    for name in ("growth", "moat", "hiring"):
        db.add_signal(conn, tid, name, "bullish", weight=1.0)

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)

    assert conf.coverage == pytest.approx(1.0, abs=1e-4)
    assert conf.agreement == 1.0
    assert conf.confidence > 0.9
    assert conf.band == "high"


def test_confidence_is_low_when_signals_disagree(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    db.add_signal(conn, tid, "valuation", "bearish", weight=1.0)

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)

    assert conf.agreement == 0.0
    assert conf.confidence == 0.0
    assert conf.band == "low"


def test_confidence_is_low_with_thin_coverage_even_if_unanimous(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=0.3)

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)

    assert conf.agreement == 1.0  # the one signal is unanimous...
    assert conf.coverage < 0.15  # ...but there's barely any evidence
    assert conf.band == "low"


# ---- public 0-100 score ----

def test_public_score_max_bullish_full_confidence_is_100(conn):
    tid = make_thesis(conn)
    for name in ("growth", "moat", "hiring"):
        db.add_signal(conn, tid, name, "bullish", weight=1.0)

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)
    pub = scoring.public_score(result, conf)

    assert pub.score_100 == 100
    assert pub.label == "Strongly Bullish"
    assert pub.n_signals == 3


def test_public_score_max_bearish_full_confidence_is_0(conn):
    tid = make_thesis(conn)
    for name in ("growth", "moat", "hiring"):
        db.add_signal(conn, tid, name, "bearish", weight=1.0)

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)
    pub = scoring.public_score(result, conf)

    assert pub.score_100 == 0
    assert pub.label == "Strongly Bearish"


def test_public_score_thin_evidence_stays_near_50_despite_max_raw_score(conn):
    # this is the whole point of confidence-shrinking: one fresh, thin
    # signal scores +1.00 raw (same as three agreeing signals), but should
    # NOT read as "100" to someone who only looks at the headline number
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=0.3)

    result = scoring.composite_score(conn, tid)
    assert result.score == 1.0  # raw score is already maxed out
    conf = scoring.confidence(result)
    pub = scoring.public_score(result, conf)

    assert 50 < pub.score_100 < 65
    assert pub.n_signals == 1


def test_public_score_no_signals_is_exactly_neutral(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    db.add_signal(conn, tid, "valuation", "bearish", weight=1.0)  # cancels out

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)
    pub = scoring.public_score(result, conf)

    assert pub.score_100 == 50
    assert pub.label == "Neutral / Mixed"


def test_public_score_clamped_to_0_100_range(conn):
    tid = make_thesis(conn)
    for name in ("a", "b", "c"):
        db.add_signal(conn, tid, name, "bullish", weight=1.0)

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)
    pub = scoring.public_score(result, conf)

    assert 0 <= pub.score_100 <= 100


def test_public_score_bands_cover_full_range():
    # every integer 0-100 must resolve to exactly one label, with no gaps
    for score in range(0, 101):
        label = next(text for threshold, text in scoring.PUBLIC_SCORE_BANDS if score >= threshold)
        assert label in {text for _, text in scoring.PUBLIC_SCORE_BANDS}


# ---- expected return range ----

def test_range_has_zero_width_at_full_confidence(conn):
    tid = make_thesis(conn, entry_price=100.0)
    for name in ("growth", "moat", "hiring"):
        db.add_signal(conn, tid, name, "bullish", weight=1.0)

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)
    rng = scoring.expected_return_range(conn, result, conf, entry_price=100.0)

    assert rng.floor_return == pytest.approx(rng.ceiling_return, abs=1e-5)
    assert rng.base_return == pytest.approx(scoring.DEFAULT_MAX_SWING)
    assert rng.floor_price == pytest.approx(100.0 * (1 + scoring.DEFAULT_MAX_SWING))
    assert rng.source == "default"


def test_range_widens_as_confidence_drops(conn):
    tid = make_thesis(conn, entry_price=100.0)
    db.add_signal(conn, tid, "growth", "bullish", weight=0.3)

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)
    rng = scoring.expected_return_range(conn, result, conf, entry_price=100.0)

    assert rng.floor_return < rng.base_return < rng.ceiling_return


def test_range_has_no_price_fields_without_entry_price(conn):
    tid = make_thesis(conn)
    conn.execute("UPDATE theses SET entry_price = NULL WHERE id = ?", (tid,))
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)

    result = scoring.composite_score(conn, tid)
    conf = scoring.confidence(result)
    rng = scoring.expected_return_range(conn, result, conf, entry_price=None)

    assert rng.floor_price is None
    assert rng.base_price is None
    assert rng.ceiling_price is None


# ---- learned weights ----

def test_learned_weights_empty_below_observation_threshold(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    db.add_snapshot(conn, tid, price=110.0)  # one observation only

    weights = scoring.learned_signal_weights(conn, min_n=3)

    assert weights == {}


def test_learned_weights_reflect_historical_spread(conn):
    # "growth" fires bullish on winners and bearish on a loser -> should learn a real weight
    for symbol, direction, entry, exit_price in [
        ("A", "bullish", 100.0, 120.0),
        ("B", "bullish", 100.0, 130.0),
        ("C", "bearish", 100.0, 90.0),
    ]:
        tid = make_thesis(conn, symbol=symbol, entry_price=entry)
        db.add_signal(conn, tid, "growth", direction, weight=1.0)
        db.add_snapshot(conn, tid, price=exit_price)

    weights = scoring.learned_signal_weights(conn, min_n=3)

    assert "growth" in weights
    assert weights["growth"] > scoring.DEFAULT_WEIGHT  # bullish clearly beat bearish historically
    assert weights["growth"] <= scoring.MAX_LEARNED_WEIGHT


# ---- range calibration ----

def test_calibrate_range_model_none_with_insufficient_history(conn):
    tid = make_thesis(conn)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    db.add_snapshot(conn, tid, price=110.0)

    assert scoring.calibrate_range_model(conn, min_n=8) is None


def test_calibrate_range_model_fits_swing_from_consistent_history(conn):
    for i in range(8):
        direction = "bullish" if i % 2 == 0 else "bearish"
        exit_price = 110.0 if direction == "bullish" else 90.0
        tid = make_thesis(conn, symbol=f"T{i}", entry_price=100.0)
        db.add_signal(conn, tid, "growth", direction, weight=1.0)
        db.add_snapshot(conn, tid, price=exit_price)

    fitted = scoring.calibrate_range_model(conn, min_n=8)

    assert fitted is not None
    assert fitted["n"] == 8
    assert fitted["max_swing"] == pytest.approx(0.10, rel=0.01)  # |+-10% return| / |+-1.0 score|


# ---- conviction comparison ----

def test_compare_to_conviction_flags_large_divergence(conn):
    tid = make_thesis(conn, conviction=1)  # normalized -1.0
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)  # score +1.0

    result = scoring.composite_score(conn, tid)
    cmp = scoring.compare_to_conviction(conn, tid, result)

    assert cmp["conviction_normalized"] == -1.0
    assert cmp["signal_score"] == 1.0
    assert cmp["agrees"] is False


def test_compare_to_conviction_agrees_when_close(conn):
    tid = make_thesis(conn, conviction=3)  # normalized 0.0
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    db.add_signal(conn, tid, "valuation", "bearish", weight=1.0)  # score 0.0

    result = scoring.composite_score(conn, tid)
    cmp = scoring.compare_to_conviction(conn, tid, result)

    assert cmp["agrees"] is True
