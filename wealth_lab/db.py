"""SQLite storage and queries for the research tracker.

Schema, in plain terms:
  theses    - one row per stock/IPO idea, with the entry price and conviction
  signals   - individual pieces of evidence attached to a thesis (insider
              buying, hiring growth, moat, valuation, ...), each bullish or
              bearish, so a thesis is never just one number
  snapshots - price/status check-ins over time, so realized return can be
              compared back against conviction and signals later
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# WEALTH_LAB_DB_PATH overrides this for a real deployment - the default path
# lives inside the repo checkout, which most hosts wipe on every redeploy.
# Point it at a mounted persistent volume instead (see DEPLOYMENT.md).
DB_PATH = Path(os.environ.get(
    "WEALTH_LAB_DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "tracker.db")
))

SIGNAL_CATEGORIES = ("growth", "valuation", "risk", "catalyst", "macro", "other")

# How much a signal counts, by the kind of evidence behind it. hard: numbers
# or actions the company or a regulator made official (reported results,
# guidance, signed deals, penalties). standard: analyst rating changes,
# management plans, insider trades. soft: price moves, valuation opinions,
# consensus snapshots, generic sector exposure.
SIGNAL_STRENGTHS = {"hard": 1.5, "standard": 1.0, "soft": 0.5}
THESIS_STATUSES = ("open", "closed_win", "closed_loss", "closed_flat")
CLOSED_STATUSES = ("closed_win", "closed_loss", "closed_flat")

SCHEMA = """
CREATE TABLE IF NOT EXISTS theses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('stock', 'ipo', 'etf', 'cash')),
    name TEXT,
    sector TEXT,
    thesis TEXT NOT NULL,
    conviction INTEGER NOT NULL CHECK (conviction BETWEEN 1 AND 5),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed_win', 'closed_loss', 'closed_flat')),
    entry_price REAL,
    entry_date TEXT,
    target_price REAL,
    horizon_days INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thesis_id INTEGER NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other'
        CHECK (category IN ('growth', 'valuation', 'risk', 'catalyst', 'macro', 'other')),
    direction TEXT NOT NULL CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    weight REAL NOT NULL DEFAULT 1.0,
    rationale TEXT,
    source TEXT,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thesis_id INTEGER NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    price REAL NOT NULL,
    note TEXT,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thesis_id INTEGER NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    sleeve TEXT NOT NULL CHECK (sleeve IN ('core_equity', 'core_bond', 'cash', 'satellite')),
    target_weight REAL NOT NULL CHECK (target_weight >= 0 AND target_weight <= 1),
    shares REAL NOT NULL,
    cost_basis REAL NOT NULL,
    opened_at TEXT NOT NULL,
    UNIQUE(thesis_id)
);

CREATE TABLE IF NOT EXISTS ipo_details (
    thesis_id INTEGER PRIMARY KEY REFERENCES theses(id) ON DELETE CASCADE,
    expected_list_date TEXT,
    actual_list_date TEXT,
    lockup_days INTEGER NOT NULL DEFAULT 180,
    disclosed_valuation REAL,
    disclosed_revenue REAL,
    notes TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comparables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ipo_thesis_id INTEGER NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    peer_symbol TEXT NOT NULL,
    peer_name TEXT,
    metric TEXT NOT NULL DEFAULT 'ev_revenue',
    peer_multiple REAL NOT NULL,
    source TEXT,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_thesis ON signals(thesis_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_thesis ON snapshots(thesis_id);
CREATE INDEX IF NOT EXISTS idx_positions_thesis ON positions(thesis_id);
CREATE INDEX IF NOT EXISTS idx_comparables_thesis ON comparables(ipo_thesis_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    # Read the module-level DB_PATH at call time, not as a bound default -
    # a bound default is evaluated once at import time, which would make
    # monkeypatching db.DB_PATH in tests (or any runtime override) silently
    # no-op.
    if db_path is None:
        db_path = DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass
class Thesis:
    id: int
    symbol: str
    asset_type: str
    name: Optional[str]
    sector: Optional[str]
    thesis: str
    conviction: int
    status: str
    entry_price: Optional[float]
    entry_date: Optional[str]
    target_price: Optional[float]
    horizon_days: Optional[int]
    created_at: str


def add_thesis(
    conn: sqlite3.Connection,
    symbol: str,
    asset_type: str,
    thesis: str,
    conviction: int,
    name: Optional[str] = None,
    sector: Optional[str] = None,
    entry_price: Optional[float] = None,
    entry_date: Optional[str] = None,
    target_price: Optional[float] = None,
    horizon_days: Optional[int] = None,
) -> int:
    if entry_price is not None and entry_price <= 0:
        raise ValueError(f"entry_price must be positive, got {entry_price}")
    if target_price is not None and target_price <= 0:
        raise ValueError(f"target_price must be positive, got {target_price}")
    cur = conn.execute(
        """INSERT INTO theses
           (symbol, asset_type, name, sector, thesis, conviction, status,
            entry_price, entry_date, target_price, horizon_days, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)""",
        (
            symbol.upper(),
            asset_type,
            name,
            sector,
            thesis,
            conviction,
            entry_price,
            entry_date,
            target_price,
            horizon_days,
            _now(),
        ),
    )
    return cur.lastrowid


def add_signal(
    conn: sqlite3.Connection,
    thesis_id: int,
    name: str,
    direction: str,
    category: str = "other",
    rationale: Optional[str] = None,
    weight: float = 1.0,
    source: Optional[str] = None,
) -> int:
    if category not in SIGNAL_CATEGORIES:
        raise ValueError(f"category must be one of {SIGNAL_CATEGORIES}, got {category!r}")
    if direction not in ("bullish", "bearish", "neutral"):
        raise ValueError(f"direction must be one of ('bullish', 'bearish', 'neutral'), got {direction!r}")
    if weight <= 0:
        raise ValueError(f"weight must be positive, got {weight}")
    cur = conn.execute(
        """INSERT INTO signals (thesis_id, name, category, direction, weight, rationale, source, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (thesis_id, name, category, direction, weight, rationale, source, _now()),
    )
    return cur.lastrowid


def add_snapshot(
    conn: sqlite3.Connection, thesis_id: int, price: float, note: Optional[str] = None
) -> int:
    if price <= 0:
        raise ValueError(f"price must be positive, got {price}")
    cur = conn.execute(
        "INSERT INTO snapshots (thesis_id, price, note, recorded_at) VALUES (?, ?, ?, ?)",
        (thesis_id, price, note, _now()),
    )
    return cur.lastrowid


def set_status(conn: sqlite3.Connection, thesis_id: int, status: str) -> None:
    conn.execute("UPDATE theses SET status = ? WHERE id = ?", (status, thesis_id))


def get_thesis(conn: sqlite3.Connection, thesis_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM theses WHERE id = ?", (thesis_id,)).fetchone()


def get_thesis_by_symbol(conn: sqlite3.Connection, symbol: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM theses WHERE symbol = ? ORDER BY created_at DESC, id DESC LIMIT 1", (symbol.upper(),)
    ).fetchone()


def list_theses(conn: sqlite3.Connection, status: Optional[str] = None) -> list[sqlite3.Row]:
    if status:
        return conn.execute(
            "SELECT * FROM theses WHERE status = ? ORDER BY created_at DESC, id DESC", (status,)
        ).fetchall()
    return conn.execute("SELECT * FROM theses ORDER BY created_at DESC, id DESC").fetchall()


def list_signals(conn: sqlite3.Connection, thesis_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM signals WHERE thesis_id = ? ORDER BY recorded_at", (thesis_id,)
    ).fetchall()


def list_snapshots(conn: sqlite3.Connection, thesis_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM snapshots WHERE thesis_id = ? ORDER BY recorded_at", (thesis_id,)
    ).fetchall()


def latest_snapshot(conn: sqlite3.Connection, thesis_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM snapshots WHERE thesis_id = ? ORDER BY recorded_at DESC LIMIT 1",
        (thesis_id,),
    ).fetchone()


def add_position(
    conn: sqlite3.Connection,
    thesis_id: int,
    sleeve: str,
    target_weight: float,
    shares: float,
    cost_basis: float,
) -> int:
    cur = conn.execute(
        """INSERT INTO positions (thesis_id, sleeve, target_weight, shares, cost_basis, opened_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (thesis_id, sleeve, target_weight, shares, cost_basis, _now()),
    )
    return cur.lastrowid


def list_positions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT positions.*, theses.symbol, theses.asset_type, theses.entry_price
           FROM positions JOIN theses ON theses.id = positions.thesis_id
           ORDER BY positions.sleeve, positions.target_weight DESC"""
    ).fetchall()


def get_position_for_thesis(conn: sqlite3.Connection, thesis_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM positions WHERE thesis_id = ?", (thesis_id,)).fetchone()


def set_ipo_details(
    conn: sqlite3.Connection,
    thesis_id: int,
    expected_list_date: Optional[str] = None,
    actual_list_date: Optional[str] = None,
    lockup_days: int = 180,
    disclosed_valuation: Optional[float] = None,
    disclosed_revenue: Optional[float] = None,
    notes: Optional[str] = None,
) -> None:
    """Upsert - set_ipo_details is meant to be called again as new facts
    come in (a filing gets an actual date, a valuation gets revised), not
    just once at creation."""
    if disclosed_valuation is not None and disclosed_valuation <= 0:
        raise ValueError(f"disclosed_valuation must be positive, got {disclosed_valuation}")
    if disclosed_revenue is not None and disclosed_revenue <= 0:
        raise ValueError(f"disclosed_revenue must be positive, got {disclosed_revenue}")
    if lockup_days <= 0:
        raise ValueError(f"lockup_days must be positive, got {lockup_days}")
    conn.execute(
        """INSERT INTO ipo_details
               (thesis_id, expected_list_date, actual_list_date, lockup_days,
                disclosed_valuation, disclosed_revenue, notes, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(thesis_id) DO UPDATE SET
               expected_list_date=excluded.expected_list_date,
               actual_list_date=excluded.actual_list_date,
               lockup_days=excluded.lockup_days,
               disclosed_valuation=excluded.disclosed_valuation,
               disclosed_revenue=excluded.disclosed_revenue,
               notes=excluded.notes,
               updated_at=excluded.updated_at""",
        (thesis_id, expected_list_date, actual_list_date, lockup_days,
         disclosed_valuation, disclosed_revenue, notes, _now()),
    )


def get_ipo_details(conn: sqlite3.Connection, thesis_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM ipo_details WHERE thesis_id = ?", (thesis_id,)).fetchone()


def add_comparable(
    conn: sqlite3.Connection,
    ipo_thesis_id: int,
    peer_symbol: str,
    peer_multiple: float,
    peer_name: Optional[str] = None,
    metric: str = "ev_revenue",
    source: Optional[str] = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO comparables (ipo_thesis_id, peer_symbol, peer_name, metric, peer_multiple, source, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ipo_thesis_id, peer_symbol.upper(), peer_name, metric, peer_multiple, source, _now()),
    )
    return cur.lastrowid


def list_comparables(
    conn: sqlite3.Connection, ipo_thesis_id: int, metric: Optional[str] = None
) -> list[sqlite3.Row]:
    if metric:
        return conn.execute(
            "SELECT * FROM comparables WHERE ipo_thesis_id = ? AND metric = ? ORDER BY peer_symbol",
            (ipo_thesis_id, metric),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM comparables WHERE ipo_thesis_id = ? ORDER BY metric, peer_symbol", (ipo_thesis_id,)
    ).fetchall()
