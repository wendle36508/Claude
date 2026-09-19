from wealth_lab import db, export, portfolio


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
    assert t["category_scores"]["growth"]["value"] == 1.0
    assert t["position"]["market_value"] == 1000.0
    assert len(t["signals"]) == 1
    assert t["signals"][0]["source"] == "http://example.com"


def test_build_snapshot_handles_thesis_with_no_signals(conn):
    db.add_thesis(conn, symbol="BBB", asset_type="stock", thesis="t", conviction=3)

    snapshot = export.build_snapshot(conn)

    t = snapshot["theses"][0]
    assert t["score"] is None
    assert t["category_scores"] == {}


def test_build_snapshot_is_json_serializable(conn):
    import json

    tid = db.add_thesis(
        conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3,
        entry_price=100.0, entry_date="2026-01-01",
    )
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])

    json.dumps(export.build_snapshot(conn))  # raises if anything isn't serializable
