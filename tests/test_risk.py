from datetime import datetime, timedelta

from wealth_lab import db, risk

BASE_DATE = datetime(2026, 1, 1)


def make_thesis(conn, symbol="TEST"):
    return db.add_thesis(conn, symbol=symbol, asset_type="stock", thesis="t", conviction=3, entry_price=100.0)


def add_dated_snapshot(conn, thesis_id, days_after_base, price):
    snap_id = db.add_snapshot(conn, thesis_id, price)
    ts = (BASE_DATE + timedelta(days=days_after_base)).isoformat(timespec="seconds")
    conn.execute("UPDATE snapshots SET recorded_at = ? WHERE id = ?", (ts, snap_id))


# ---- price series / returns ----

def test_price_series_is_chronological(conn):
    tid = make_thesis(conn)
    add_dated_snapshot(conn, tid, 30, 110.0)
    add_dated_snapshot(conn, tid, 0, 100.0)
    add_dated_snapshot(conn, tid, 60, 121.0)

    series = risk.price_series(conn, tid)

    assert [p for _, p in series] == [100.0, 110.0, 121.0]


def test_periodic_returns_computed_correctly(conn):
    tid = make_thesis(conn)
    for day, price in [(0, 100.0), (30, 110.0), (60, 121.0)]:
        add_dated_snapshot(conn, tid, day, price)

    returns = risk.periodic_returns(risk.price_series(conn, tid))

    assert returns == [0.10, 0.10]  # exact: 110/100-1, 121/110-1


def test_periodic_returns_empty_with_one_snapshot(conn):
    tid = make_thesis(conn)
    add_dated_snapshot(conn, tid, 0, 100.0)

    assert risk.periodic_returns(risk.price_series(conn, tid)) == []


# ---- annualization ----

def test_inferred_periods_per_year_from_monthly_snapshots(conn):
    tid = make_thesis(conn)
    for day in (0, 30, 60, 90):
        add_dated_snapshot(conn, tid, day, 100.0)

    ppy = risk.inferred_periods_per_year(risk.price_series(conn, tid))

    assert round(ppy, 1) == round(365.25 / 30, 1)  # ~12.2 periods/year


def test_inferred_periods_per_year_none_with_one_snapshot(conn):
    tid = make_thesis(conn)
    add_dated_snapshot(conn, tid, 0, 100.0)

    assert risk.inferred_periods_per_year(risk.price_series(conn, tid)) is None


# ---- volatility / sharpe ----

def test_volatility_zero_for_constant_returns(conn):
    tid = make_thesis(conn)
    for day, price in [(0, 100.0), (30, 110.0), (60, 121.0)]:  # exactly +10% each period
        add_dated_snapshot(conn, tid, day, price)

    returns = risk.periodic_returns(risk.price_series(conn, tid))

    assert risk.volatility(returns, periods_per_year=12) == 0.0


def test_volatility_positive_for_varying_returns(conn):
    tid = make_thesis(conn)
    for day, price in [(0, 100.0), (30, 120.0), (60, 108.0)]:  # +20%, -10%
        add_dated_snapshot(conn, tid, day, price)

    returns = risk.periodic_returns(risk.price_series(conn, tid))

    assert risk.volatility(returns, periods_per_year=12) > 0


def test_sharpe_none_with_insufficient_returns(conn):
    tid = make_thesis(conn)
    add_dated_snapshot(conn, tid, 0, 100.0)
    add_dated_snapshot(conn, tid, 30, 110.0)  # only 1 return

    returns = risk.periodic_returns(risk.price_series(conn, tid))

    assert risk.sharpe_ratio(returns, periods_per_year=12) is None


def test_sharpe_positive_when_mean_return_beats_risk_free(conn):
    returns = [0.05, 0.03, 0.06, 0.02]

    sharpe = risk.sharpe_ratio(returns, periods_per_year=12, risk_free_rate=0.0)

    assert sharpe > 0


def test_sharpe_negative_when_mean_return_is_negative(conn):
    returns = [-0.05, -0.03, -0.06, -0.02]

    sharpe = risk.sharpe_ratio(returns, periods_per_year=12, risk_free_rate=0.0)

    assert sharpe < 0


# ---- max drawdown ----

def test_max_drawdown_from_known_series(conn):
    tid = make_thesis(conn)
    for day, price in [(0, 100.0), (10, 120.0), (20, 90.0), (30, 110.0)]:
        add_dated_snapshot(conn, tid, day, price)

    dd = risk.max_drawdown(risk.price_series(conn, tid))

    assert round(dd, 4) == round((90.0 - 120.0) / 120.0, 4)  # -0.25


def test_max_drawdown_zero_for_monotonic_rise(conn):
    tid = make_thesis(conn)
    for day, price in [(0, 100.0), (10, 110.0), (20, 120.0)]:
        add_dated_snapshot(conn, tid, day, price)

    assert risk.max_drawdown(risk.price_series(conn, tid)) == 0.0


def test_max_drawdown_none_with_one_snapshot(conn):
    tid = make_thesis(conn)
    add_dated_snapshot(conn, tid, 0, 100.0)

    assert risk.max_drawdown(risk.price_series(conn, tid)) is None


# ---- beta ----

def test_beta_is_two_for_a_doubled_series(conn):
    tid_a = make_thesis(conn, "ASSET")
    tid_b = make_thesis(conn, "BENCH")
    bench_prices = [100.0, 105.0, 102.9, 108.045]  # +5%, -2%, +5%
    asset_prices = [100.0, 110.0, 105.6, 116.16]   # +10%, -4%, +10% (exactly 2x benchmark moves)
    for day, (bp, ap) in enumerate(zip(bench_prices, asset_prices)):
        add_dated_snapshot(conn, tid_b, day * 10, bp)
        add_dated_snapshot(conn, tid_a, day * 10, ap)

    ra, rb = risk.aligned_returns(conn, tid_a, tid_b)
    b = risk.beta(ra, rb)

    assert round(b, 4) == 2.0


def test_beta_none_with_no_overlapping_dates(conn):
    tid_a = make_thesis(conn, "ASSET")
    tid_b = make_thesis(conn, "BENCH")
    add_dated_snapshot(conn, tid_a, 0, 100.0)
    add_dated_snapshot(conn, tid_a, 10, 105.0)
    add_dated_snapshot(conn, tid_b, 100, 200.0)  # no shared dates with asset
    add_dated_snapshot(conn, tid_b, 110, 210.0)

    ra, rb = risk.aligned_returns(conn, tid_a, tid_b)

    assert ra == [] and rb == []
    assert risk.beta(ra, rb) is None


# ---- compute_risk_metrics (integration) ----

def test_compute_risk_metrics_insufficient_with_one_snapshot(conn):
    tid = make_thesis(conn)
    add_dated_snapshot(conn, tid, 0, 100.0)

    m = risk.compute_risk_metrics(conn, tid)

    assert m.sufficient is False
    assert m.volatility is None
    assert m.sharpe is None


def test_compute_risk_metrics_sufficient_and_includes_beta(conn):
    tid_a = make_thesis(conn, "ASSET")
    tid_b = make_thesis(conn, "SPY")
    for day, (ap, bp) in enumerate(zip([100.0, 108.0, 103.0, 112.0], [100.0, 104.0, 101.5, 106.0])):
        add_dated_snapshot(conn, tid_a, day * 10, ap)
        add_dated_snapshot(conn, tid_b, day * 10, bp)

    m = risk.compute_risk_metrics(conn, tid_a, benchmark_thesis_id=tid_b)

    assert m.sufficient is True
    assert m.volatility is not None
    assert m.sharpe is not None
    assert m.max_drawdown is not None
    assert m.beta_vs_benchmark is not None
