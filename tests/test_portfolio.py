from wealth_lab import db, portfolio


def test_allocate_computes_shares_from_weight_and_price(conn):
    tid = db.add_thesis(
        conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3,
        entry_price=50.0, entry_date="2026-01-01",
    )

    portfolio.allocate(conn, total_capital=1000.0, allocations=[
        {"thesis_id": tid, "sleeve": "satellite", "target_weight": 0.5},
    ])

    values = portfolio.current_values(conn)
    assert len(values) == 1
    assert values[0].shares == 10.0  # $500 / $50


def test_cash_position_prices_at_one_dollar(conn):
    tid = db.add_thesis(conn, symbol="CASH", asset_type="cash", thesis="t", conviction=5)

    portfolio.allocate(conn, total_capital=1000.0, allocations=[
        {"thesis_id": tid, "sleeve": "cash", "target_weight": 0.1},
    ])

    values = portfolio.current_values(conn)
    assert values[0].shares == 100.0
    assert values[0].market_value == 100.0


def test_current_values_falls_back_to_entry_price_without_snapshot(conn):
    tid = db.add_thesis(
        conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3,
        entry_price=50.0, entry_date="2026-01-01",
    )
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])

    values = portfolio.current_values(conn)

    assert values[0].current_price == 50.0
    assert values[0].pct_return == 0.0


def test_current_values_uses_latest_snapshot_over_entry_price(conn):
    tid = db.add_thesis(
        conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3,
        entry_price=50.0, entry_date="2026-01-01",
    )
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])
    db.add_snapshot(conn, tid, price=60.0)

    values = portfolio.current_values(conn)

    assert values[0].current_price == 60.0
    assert round(values[0].pct_return, 2) == 0.20


def test_herfindahl_index_equal_weight_positions(conn):
    ids = [
        db.add_thesis(conn, symbol=s, asset_type="stock", thesis="t", conviction=3, entry_price=10.0, entry_date="2026-01-01")
        for s in ("A", "B", "C", "D")
    ]
    portfolio.allocate(conn, 1000.0, [
        {"thesis_id": tid, "sleeve": "satellite", "target_weight": 0.25} for tid in ids
    ])

    values = portfolio.current_values(conn)
    hhi = portfolio.herfindahl_index(values)

    assert round(hhi, 4) == 0.25  # 4 * (0.25 ** 2)


def test_herfindahl_index_single_position_is_one(conn):
    tid = db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3, entry_price=10.0, entry_date="2026-01-01")
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])

    values = portfolio.current_values(conn)

    assert portfolio.herfindahl_index(values) == 1.0


def test_portfolio_return_reflects_price_moves(conn):
    tid = db.add_thesis(
        conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3,
        entry_price=100.0, entry_date="2026-01-01",
    )
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])
    db.add_snapshot(conn, tid, price=110.0)

    values = portfolio.current_values(conn)
    ret = portfolio.portfolio_return(values, starting_capital=1000.0)

    assert round(ret, 2) == 0.10
