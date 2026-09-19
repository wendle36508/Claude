import pytest

from wealth_lab import db, portfolio, sizing


def make_satellite(conn, symbol, target_weight, entry_price=100.0):
    tid = db.add_thesis(
        conn, symbol=symbol, asset_type="stock", thesis="t", conviction=3,
        entry_price=entry_price, entry_date="2026-01-01",
    )
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": target_weight}])
    return tid


def test_empty_without_satellite_positions(conn):
    assert sizing.satellite_sizing(conn) == []


def test_ignores_non_satellite_sleeves(conn):
    tid = db.add_thesis(conn, symbol="CASH", asset_type="cash", thesis="t", conviction=5)
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "cash", "target_weight": 1.0}])

    assert sizing.satellite_sizing(conn) == []


def test_preserves_total_satellite_weight(conn):
    tid_a = make_satellite(conn, "A", 0.3)
    tid_b = make_satellite(conn, "B", 0.2)
    db.add_signal(conn, tid_a, "growth", "bullish", weight=1.0)
    db.add_signal(conn, tid_b, "growth", "bullish", weight=1.0)

    suggestions = sizing.satellite_sizing(conn)

    assert sum(s.suggested_weight for s in suggestions) == pytest.approx(0.5)


def test_all_weight_goes_to_the_only_thesis_with_conviction(conn):
    tid_a = make_satellite(conn, "STRONG", 0.25)
    tid_b = make_satellite(conn, "CANCELS", 0.25)
    db.add_signal(conn, tid_a, "growth", "bullish", weight=1.0)  # score +1.0
    db.add_signal(conn, tid_b, "growth", "bullish", weight=1.0)  # cancels out
    db.add_signal(conn, tid_b, "risk", "bearish", weight=1.0)

    suggestions = {s.symbol: s for s in sizing.satellite_sizing(conn)}

    assert suggestions["CANCELS"].conviction_magnitude == 0.0
    assert suggestions["CANCELS"].suggested_weight == 0.0
    assert suggestions["STRONG"].suggested_weight == pytest.approx(0.5)  # gets the whole sleeve


def test_equal_split_fallback_when_no_thesis_has_any_signal(conn):
    make_satellite(conn, "A", 0.3)
    make_satellite(conn, "B", 0.2)

    suggestions = sizing.satellite_sizing(conn)

    assert all(s.suggested_weight == pytest.approx(0.25) for s in suggestions)  # 0.5 total / 2 positions


def test_delta_is_suggested_minus_current(conn):
    tid = make_satellite(conn, "A", 0.4)
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)

    s = sizing.satellite_sizing(conn)[0]

    assert s.delta == pytest.approx(s.suggested_weight - 0.4)


def test_respects_explicit_satellite_total_weight_override(conn):
    make_satellite(conn, "A", 0.3)
    make_satellite(conn, "B", 0.2)

    suggestions = sizing.satellite_sizing(conn, satellite_total_weight=0.8)

    assert sum(s.suggested_weight for s in suggestions) == pytest.approx(0.8)
