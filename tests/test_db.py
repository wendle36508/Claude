import os
import subprocess
import sys
from pathlib import Path

import pytest

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


# ---- input validation ----

def test_add_thesis_rejects_non_positive_entry_price(conn):
    with pytest.raises(ValueError):
        db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3, entry_price=-10.0)
    with pytest.raises(ValueError):
        db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3, entry_price=0.0)


def test_add_thesis_rejects_non_positive_target_price(conn):
    with pytest.raises(ValueError):
        db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3, target_price=-1.0)


def test_add_thesis_allows_none_prices(conn):
    tid = db.add_thesis(conn, symbol="AAA", asset_type="cash", thesis="t", conviction=5)
    assert tid is not None


def test_add_signal_rejects_non_positive_weight(conn):
    tid = db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3)
    with pytest.raises(ValueError):
        db.add_signal(conn, tid, "growth", "bullish", weight=-1.0)
    with pytest.raises(ValueError):
        db.add_signal(conn, tid, "growth", "bullish", weight=0.0)


def test_add_signal_rejects_invalid_direction(conn):
    tid = db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3)
    with pytest.raises(ValueError):
        db.add_signal(conn, tid, "growth", "upward")


def test_add_snapshot_rejects_non_positive_price(conn):
    tid = db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3)
    with pytest.raises(ValueError):
        db.add_snapshot(conn, tid, price=-50.0)
    with pytest.raises(ValueError):
        db.add_snapshot(conn, tid, price=0.0)


def test_set_ipo_details_rejects_non_positive_figures(conn):
    tid = db.add_thesis(conn, symbol="AAA", asset_type="ipo", thesis="t", conviction=3)
    with pytest.raises(ValueError):
        db.set_ipo_details(conn, tid, disclosed_valuation=-1.0)
    with pytest.raises(ValueError):
        db.set_ipo_details(conn, tid, disclosed_revenue=-1.0)
    with pytest.raises(ValueError):
        db.set_ipo_details(conn, tid, lockup_days=0)


def test_db_path_env_var_override_is_read_at_import(tmp_path):
    # DB_PATH is a module-level constant computed at import time from
    # WEALTH_LAB_DB_PATH, so this exercises a fresh interpreter rather than
    # monkeypatching db.DB_PATH directly (which every other test does, and
    # which wouldn't prove the env var itself is wired up).
    override = tmp_path / "custom" / "tracker.db"
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-c", "from wealth_lab import db; print(db.DB_PATH)"],
        env={**os.environ, "WEALTH_LAB_DB_PATH": str(override)},
        cwd=str(repo_root),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(override)
