import pytest

from wealth_lab import compare, db


def make_thesis(conn, symbol, conviction=3, entry_price=100.0):
    return db.add_thesis(
        conn, symbol=symbol, asset_type="stock", thesis="t",
        conviction=conviction, entry_price=entry_price, entry_date="2026-01-01",
    )


def test_build_comparison_includes_every_thesis(conn):
    make_thesis(conn, "A")
    make_thesis(conn, "B")

    rows = compare.build_comparison(conn)

    assert {r.symbol for r in rows} == {"A", "B"}


def test_row_has_none_score_when_no_signals_logged(conn):
    make_thesis(conn, "A")

    rows = compare.build_comparison(conn)

    assert rows[0].score is None
    assert rows[0].confidence is None


def test_row_has_score_when_signals_exist(conn):
    tid = make_thesis(conn, "A")
    db.add_signal(conn, tid, "growth", "bullish", weight=1.0)

    rows = compare.build_comparison(conn)

    assert rows[0].score == 1.0
    assert rows[0].confidence is not None


def test_status_filter_only_returns_matching_theses(conn):
    tid = make_thesis(conn, "A")
    make_thesis(conn, "B")
    db.set_status(conn, tid, "closed_win")

    rows = compare.build_comparison(conn, status="closed_win")

    assert [r.symbol for r in rows] == ["A"]


def test_sort_by_score_descending(conn):
    tid_a = make_thesis(conn, "A")
    tid_b = make_thesis(conn, "B")
    db.add_signal(conn, tid_a, "growth", "bearish", weight=1.0)  # score -1.0
    db.add_signal(conn, tid_b, "growth", "bullish", weight=1.0)  # score +1.0

    rows = compare.sort_rows(compare.build_comparison(conn), by="score", descending=True)

    assert [r.symbol for r in rows] == ["B", "A"]


def test_sort_ascending_reverses_order(conn):
    tid_a = make_thesis(conn, "A")
    tid_b = make_thesis(conn, "B")
    db.add_signal(conn, tid_a, "growth", "bearish", weight=1.0)
    db.add_signal(conn, tid_b, "growth", "bullish", weight=1.0)

    rows = compare.sort_rows(compare.build_comparison(conn), by="score", descending=False)

    assert [r.symbol for r in rows] == ["A", "B"]


def test_rows_with_missing_data_sort_last_regardless_of_direction(conn):
    make_thesis(conn, "NO_SIGNALS")  # score stays None
    tid_b = make_thesis(conn, "HAS_SIGNAL")
    db.add_signal(conn, tid_b, "growth", "bearish", weight=1.0)  # score -1.0, still a real value

    descending = compare.sort_rows(compare.build_comparison(conn), by="score", descending=True)
    ascending = compare.sort_rows(compare.build_comparison(conn), by="score", descending=False)

    assert descending[-1].symbol == "NO_SIGNALS"
    assert ascending[-1].symbol == "NO_SIGNALS"


def test_sort_rejects_unknown_column(conn):
    make_thesis(conn, "A")

    with pytest.raises(ValueError):
        compare.sort_rows(compare.build_comparison(conn), by="not_a_real_column")
