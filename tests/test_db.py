from wealth_lab import db


def test_get_thesis_by_symbol_finds_it(conn):
    db.add_thesis(conn, symbol="aapl", asset_type="stock", thesis="t", conviction=3)

    found = db.get_thesis_by_symbol(conn, "AAPL")  # case-insensitive lookup

    assert found is not None
    assert found["symbol"] == "AAPL"


def test_get_thesis_by_symbol_returns_none_when_missing(conn):
    assert db.get_thesis_by_symbol(conn, "NOPE") is None


def test_get_thesis_by_symbol_returns_most_recent(conn):
    db.add_thesis(conn, symbol="DUP", asset_type="stock", thesis="first", conviction=3)
    second_id = db.add_thesis(conn, symbol="DUP", asset_type="stock", thesis="second", conviction=3)

    found = db.get_thesis_by_symbol(conn, "DUP")

    assert found["id"] == second_id


def test_add_signal_rejects_invalid_category(conn):
    tid = db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3)

    try:
        db.add_signal(conn, tid, "growth", "bullish", category="not_a_real_category")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_get_position_for_thesis_returns_none_when_unfunded(conn):
    tid = db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3)

    assert db.get_position_for_thesis(conn, tid) is None
