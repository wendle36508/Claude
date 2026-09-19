from datetime import date

import pytest

from wealth_lab import db, ipo


def make_ipo_thesis(conn, symbol="PREIPO"):
    return db.add_thesis(conn, symbol=symbol, asset_type="ipo", thesis="t", conviction=3)


# ---- lockup status ----

def test_lockup_status_none_with_no_ipo_details(conn):
    tid = make_ipo_thesis(conn)

    status = ipo.lockup_status(conn, tid)

    assert status.expiry_date is None
    assert status.days_until_expiry is None


def test_lockup_status_estimated_from_expected_list_date(conn):
    tid = make_ipo_thesis(conn)
    db.set_ipo_details(conn, tid, expected_list_date="2026-10-01", lockup_days=180)

    status = ipo.lockup_status(conn, tid, as_of=date(2026, 9, 19))

    assert status.is_estimate is True
    assert status.expiry_date == "2027-03-30"  # 2026-10-01 + 180 days
    assert status.days_until_expiry == (date(2027, 3, 30) - date(2026, 9, 19)).days


def test_lockup_status_real_once_actual_list_date_set(conn):
    tid = make_ipo_thesis(conn)
    db.set_ipo_details(conn, tid, expected_list_date="2026-10-01", actual_list_date="2026-10-15", lockup_days=90)

    status = ipo.lockup_status(conn, tid, as_of=date(2026, 9, 19))

    assert status.is_estimate is False
    assert status.expiry_date == "2027-01-13"  # 2026-10-15 + 90 days


def test_lockup_status_negative_days_once_expired(conn):
    tid = make_ipo_thesis(conn)
    db.set_ipo_details(conn, tid, actual_list_date="2026-01-01", lockup_days=90)

    status = ipo.lockup_status(conn, tid, as_of=date(2026, 6, 1))

    assert status.days_until_expiry < 0


def test_set_ipo_details_is_an_upsert(conn):
    tid = make_ipo_thesis(conn)
    db.set_ipo_details(conn, tid, expected_list_date="2026-10-01", disclosed_valuation=1000.0)
    db.set_ipo_details(conn, tid, expected_list_date="2026-11-15", disclosed_valuation=1200.0)

    details = db.get_ipo_details(conn, tid)

    assert details["expected_list_date"] == "2026-11-15"
    assert details["disclosed_valuation"] == 1200.0


# ---- valuation gap ----

def test_valuation_gap_none_without_disclosed_figures(conn):
    tid = make_ipo_thesis(conn)

    assert ipo.valuation_gap(conn, tid) is None


def test_valuation_gap_computes_ipo_multiple(conn):
    tid = make_ipo_thesis(conn)
    db.set_ipo_details(conn, tid, disclosed_valuation=24_500_000_000, disclosed_revenue=510_000_000)

    gap = ipo.valuation_gap(conn, tid)

    assert gap.ipo_multiple == pytest.approx(48.04, rel=0.01)
    assert gap.n_comps == 0
    assert gap.peer_median is None


def test_valuation_gap_computes_premium_to_peer_median(conn):
    tid = make_ipo_thesis(conn)
    db.set_ipo_details(conn, tid, disclosed_valuation=1000.0, disclosed_revenue=100.0)  # 10x
    db.add_comparable(conn, tid, "PEERA", 5.0)
    db.add_comparable(conn, tid, "PEERB", 15.0)  # median = 10

    gap = ipo.valuation_gap(conn, tid)

    assert gap.peer_median == 10.0
    assert gap.premium_to_peers == 0.0  # dead even with peer median
    assert gap.n_comps == 2


def test_valuation_gap_respects_metric_filter(conn):
    tid = make_ipo_thesis(conn)
    db.set_ipo_details(conn, tid, disclosed_valuation=1000.0, disclosed_revenue=100.0)
    db.add_comparable(conn, tid, "PEERA", 5.0, metric="ev_revenue")
    db.add_comparable(conn, tid, "PEERB", 999.0, metric="ev_ebitda")

    gap = ipo.valuation_gap(conn, tid, metric="ev_revenue")

    assert gap.n_comps == 1
    assert gap.peer_median == 5.0
