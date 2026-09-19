from datetime import datetime, timedelta, timezone

from wealth_lab import db, scan


def make_thesis(conn, symbol="TEST"):
    return db.add_thesis(conn, symbol=symbol, asset_type="stock", thesis="t", conviction=3, entry_price=100.0)


def test_stale_theses_empty_for_fresh_snapshot(conn):
    tid = make_thesis(conn)
    db.add_snapshot(conn, tid, price=100.0)

    assert scan.stale_theses(conn) == []


def test_stale_theses_flags_thesis_with_old_snapshot(conn):
    tid = make_thesis(conn)
    snap_id = db.add_snapshot(conn, tid, price=100.0)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=scan.STALE_AFTER_DAYS + 1)).isoformat(timespec="seconds")
    conn.execute("UPDATE snapshots SET recorded_at = ? WHERE id = ?", (old_ts, snap_id))

    stale = scan.stale_theses(conn)

    assert [t["id"] for t in stale] == [tid]


def test_stale_theses_falls_back_to_created_at_with_no_snapshot(conn):
    tid = make_thesis(conn)  # no snapshot at all
    old_ts = (datetime.now(timezone.utc) - timedelta(days=scan.STALE_AFTER_DAYS + 1)).isoformat(timespec="seconds")
    conn.execute("UPDATE theses SET created_at = ? WHERE id = ?", (old_ts, tid))

    stale = scan.stale_theses(conn)

    assert [t["id"] for t in stale] == [tid]


def test_stale_theses_ignores_closed_theses(conn):
    tid = make_thesis(conn)
    snap_id = db.add_snapshot(conn, tid, price=100.0)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=scan.STALE_AFTER_DAYS + 1)).isoformat(timespec="seconds")
    conn.execute("UPDATE snapshots SET recorded_at = ? WHERE id = ?", (old_ts, snap_id))
    db.set_status(conn, tid, "closed_win")

    assert scan.stale_theses(conn) == []


def test_fetch_price_always_none_in_this_environment():
    assert scan.fetch_price("AAPL") is None


def test_run_scan_reports_no_stale_theses(conn):
    tid = make_thesis(conn)
    db.add_snapshot(conn, tid, price=100.0)

    output = scan.run_scan(conn)

    assert "no stale theses" in output


def test_run_scan_lists_stale_symbols(conn):
    tid = make_thesis(conn, "STALESYM")
    snap_id = db.add_snapshot(conn, tid, price=100.0)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=scan.STALE_AFTER_DAYS + 1)).isoformat(timespec="seconds")
    conn.execute("UPDATE snapshots SET recorded_at = ? WHERE id = ?", (old_ts, snap_id))

    output = scan.run_scan(conn)

    assert "STALESYM" in output
