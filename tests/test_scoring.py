from wealth_lab import db, scoring


def make_thesis(conn, symbol="TEST", conviction=3, entry_price=100.0):
    return db.add_thesis(
        conn, symbol=symbol, asset_type="stock", thesis="test thesis",
        conviction=conviction, entry_price=entry_price, entry_date="2026-01-01",
    )


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
