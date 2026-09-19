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

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tracker.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS theses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('stock', 'ipo')),
    name TEXT,
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

CREATE INDEX IF NOT EXISTS idx_signals_thesis ON signals(thesis_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_thesis ON snapshots(thesis_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
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
    entry_price: Optional[float] = None,
    entry_date: Optional[str] = None,
    target_price: Optional[float] = None,
    horizon_days: Optional[int] = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO theses
           (symbol, asset_type, name, thesis, conviction, status,
            entry_price, entry_date, target_price, horizon_days, created_at)
           VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)""",
        (
            symbol.upper(),
            asset_type,
            name,
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
    rationale: Optional[str] = None,
    weight: float = 1.0,
    source: Optional[str] = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO signals (thesis_id, name, direction, weight, rationale, source, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (thesis_id, name, direction, weight, rationale, source, _now()),
    )
    return cur.lastrowid


def add_snapshot(
    conn: sqlite3.Connection, thesis_id: int, price: float, note: Optional[str] = None
) -> int:
    cur = conn.execute(
        "INSERT INTO snapshots (thesis_id, price, note, recorded_at) VALUES (?, ?, ?, ?)",
        (thesis_id, price, note, _now()),
    )
    return cur.lastrowid


def set_status(conn: sqlite3.Connection, thesis_id: int, status: str) -> None:
    conn.execute("UPDATE theses SET status = ? WHERE id = ?", (status, thesis_id))


def get_thesis(conn: sqlite3.Connection, thesis_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM theses WHERE id = ?", (thesis_id,)).fetchone()


def list_theses(conn: sqlite3.Connection, status: Optional[str] = None) -> list[sqlite3.Row]:
    if status:
        return conn.execute(
            "SELECT * FROM theses WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    return conn.execute("SELECT * FROM theses ORDER BY created_at DESC").fetchall()


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
