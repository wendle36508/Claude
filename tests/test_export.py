from wealth_lab import db, export, portfolio, scoring
from wealth_lab.providers.base import QuantMetrics


def test_build_snapshot_empty_db_has_no_portfolio(conn):
    snapshot = export.build_snapshot(conn)

    assert snapshot["portfolio"] is None
    assert snapshot["theses"] == []


def test_build_snapshot_includes_thesis_with_signals_and_position(conn):
    tid = db.add_thesis(
        conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3,
        entry_price=100.0, entry_date="2026-01-01", sector="Test Sector",
    )
    db.add_signal(conn, tid, "growth", "bullish", category="growth", weight=1.0, source="http://example.com")
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])

    snapshot = export.build_snapshot(conn)

    assert snapshot["portfolio"]["total_value"] == 1000.0
    t = snapshot["theses"][0]
    assert t["symbol"] == "AAA"
    assert t["sector"] == "Test Sector"
    assert t["score"]["value"] == 1.0
    assert t["public_score"]["value"] == 67  # one fresh signal -> confidence-shrunk, not maxed to 100
    assert t["public_score"]["label"] == "Bullish"
    assert t["category_scores"]["growth"]["value"] == 1.0
    assert t["category_scores"]["growth"]["public_score"]["value"] == 67
    assert t["category_scores"]["growth"]["public_score"]["label"] == "Bullish"
    assert t["position"]["market_value"] == 1000.0
    assert len(t["signals"]) == 1
    assert t["signals"][0]["source"] == "http://example.com"
    assert t["news"] == {"live": False, "items": []}


def test_build_snapshot_handles_thesis_with_no_signals(conn):
    db.add_thesis(conn, symbol="BBB", asset_type="stock", thesis="t", conviction=3)

    snapshot = export.build_snapshot(conn)

    t = snapshot["theses"][0]
    assert t["score"] is None
    assert t["public_score"] is None
    assert t["category_scores"] == {}


def test_thesis_snapshot_blends_in_live_quant_signals(conn, monkeypatch):
    class FakeLiveProvider:
        is_live = True
        def get_quant_metrics(self, symbol):
            return QuantMetrics(pe_ttm=10.0, pb_ttm=None, beta=None, week52_high=None, week52_low=None)

    monkeypatch.setattr(scoring, "get_provider", lambda: FakeLiveProvider())

    tid = db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3)
    db.add_signal(conn, tid, "hiring", "bullish", category="growth", weight=1.0)
    t = db.get_thesis(conn, tid)

    snap = export.thesis_snapshot(conn, t)

    # 1 logged growth signal + 1 live valuation (P/E) signal = 2 total
    assert snap["score"]["n_signals"] == 2
    assert snap["category_scores"]["valuation"]["n_signals"] == 1
    assert snap["category_scores"]["valuation"]["value"] > 0  # cheap P/E -> bullish valuation
    assert "growth" in snap["category_scores"]  # the logged signal is untouched


def test_build_snapshot_is_json_serializable(conn):
    import json

    tid = db.add_thesis(
        conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3,
        entry_price=100.0, entry_date="2026-01-01",
    )
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])

    json.dumps(export.build_snapshot(conn))  # raises if anything isn't serializable
