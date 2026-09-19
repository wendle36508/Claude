from wealth_lab import db, portfolio


def snapshot_on(conn, thesis_id, date, price):
    snap_id = db.add_snapshot(conn, thesis_id, price)
    conn.execute("UPDATE snapshots SET recorded_at = ? WHERE id = ?", (f"{date}T00:00:00", snap_id))


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


# ---- value_series (forward-fill) ----

def test_value_series_forward_fills_a_position_with_no_new_snapshot(conn):
    tid_a = db.add_thesis(conn, symbol="A", asset_type="stock", thesis="t", conviction=3, entry_price=100.0, entry_date="2026-01-01")
    tid_b = db.add_thesis(conn, symbol="B", asset_type="stock", thesis="t", conviction=3, entry_price=50.0, entry_date="2026-01-01")
    portfolio.allocate(conn, 1000.0, [
        {"thesis_id": tid_a, "sleeve": "satellite", "target_weight": 0.5},
        {"thesis_id": tid_b, "sleeve": "satellite", "target_weight": 0.5},
    ])
    # only A gets a new snapshot on day 10; B never updates past its entry
    snapshot_on(conn, tid_a, "2026-01-11", 120.0)

    series = dict(portfolio.value_series(conn))

    # day 0: A=5 shares*100 + B=10 shares*50 = 500+500=1000
    assert round(series["2026-01-01"], 2) == 1000.0
    # day 10: A=5*120=600, B still forward-filled at 50 -> 10*50=500 -> total 1100
    assert round(series["2026-01-11"], 2) == 1100.0


def test_value_series_includes_cash_at_constant_value(conn):
    tid_stock = db.add_thesis(conn, symbol="A", asset_type="stock", thesis="t", conviction=3, entry_price=100.0, entry_date="2026-01-01")
    tid_cash = db.add_thesis(conn, symbol="CASH", asset_type="cash", thesis="t", conviction=5)
    portfolio.allocate(conn, 1000.0, [
        {"thesis_id": tid_stock, "sleeve": "satellite", "target_weight": 0.9},
        {"thesis_id": tid_cash, "sleeve": "cash", "target_weight": 0.1},
    ])
    snapshot_on(conn, tid_stock, "2026-01-11", 200.0)  # doubled

    series = dict(portfolio.value_series(conn))

    assert round(series["2026-01-01"], 2) == 1000.0  # 900 stock + 100 cash
    assert round(series["2026-01-11"], 2) == 1900.0  # 1800 stock + 100 cash unchanged


# ---- portfolio_risk_metrics ----

def test_portfolio_risk_metrics_insufficient_with_thin_history(conn):
    tid = db.add_thesis(conn, symbol="A", asset_type="stock", thesis="t", conviction=3, entry_price=100.0, entry_date="2026-01-01")
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])

    m = portfolio.portfolio_risk_metrics(conn)

    assert m.sufficient is False


def test_portfolio_risk_metrics_sufficient_with_enough_dates(conn):
    tid = db.add_thesis(conn, symbol="A", asset_type="stock", thesis="t", conviction=3, entry_price=100.0, entry_date="2026-01-01")
    portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])
    snapshot_on(conn, tid, "2026-01-11", 105.0)
    snapshot_on(conn, tid, "2026-01-21", 98.0)

    m = portfolio.portfolio_risk_metrics(conn)

    assert m.sufficient is True
    assert m.volatility is not None
    assert m.max_drawdown is not None


# ---- naive volatility upper bound ----

def test_naive_volatility_includes_cash_at_zero_and_excludes_thin_positions(conn):
    tid_stock = db.add_thesis(conn, symbol="A", asset_type="stock", thesis="t", conviction=3, entry_price=100.0, entry_date="2026-01-01")
    tid_cash = db.add_thesis(conn, symbol="CASH", asset_type="cash", thesis="t", conviction=5)
    portfolio.allocate(conn, 1000.0, [
        {"thesis_id": tid_stock, "sleeve": "satellite", "target_weight": 0.5},
        {"thesis_id": tid_cash, "sleeve": "cash", "target_weight": 0.5},
    ])
    # tid_stock has only its entry snapshot -> insufficient own history, excluded
    # cash always counts at 0 vol

    est = portfolio.naive_volatility_upper_bound(conn)

    assert est is not None
    assert est.weighted_volatility == 0.0
    assert est.n_positions_included == 1
    assert round(est.covered_weight, 2) == 0.5  # only cash's half counted


def test_naive_volatility_none_with_no_positions(conn):
    assert portfolio.naive_volatility_upper_bound(conn) is None
