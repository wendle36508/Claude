"""Portfolio construction and risk metrics on top of the thesis tracker.

A thesis is a piece of research; a position is a funded, sized allocation
built from one. Not every thesis becomes a position - the pre-IPO names
(ANTH, CBRS, DATABRICKS) stay research/watchlist entries with no shares
until they actually list, which mirrors how a real desk separates coverage
from holdings.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from wealth_lab import db


@dataclass
class PositionValue:
    thesis_id: int
    symbol: str
    sleeve: str
    target_weight: float
    shares: float
    cost_basis: float
    current_price: float
    market_value: float
    pct_return: float


def allocate(
    conn: sqlite3.Connection,
    total_capital: float,
    allocations: list[dict],
) -> None:
    """Fund a set of theses into positions.

    Each entry in `allocations`: {"thesis_id": int, "sleeve": str, "target_weight": float}.
    Cash positions (asset_type == 'cash') get shares == dollar amount, price treated as 1.0.
    """
    for alloc in allocations:
        thesis = db.get_thesis(conn, alloc["thesis_id"])
        if thesis is None:
            raise ValueError(f"no thesis #{alloc['thesis_id']}")
        dollars = total_capital * alloc["target_weight"]
        price = 1.0 if thesis["asset_type"] == "cash" else thesis["entry_price"]
        if price is None:
            raise ValueError(f"thesis #{thesis['id']} ({thesis['symbol']}) has no entry price")
        shares = dollars / price
        db.add_position(
            conn,
            thesis_id=alloc["thesis_id"],
            sleeve=alloc["sleeve"],
            target_weight=alloc["target_weight"],
            shares=shares,
            cost_basis=price,
        )


def current_values(conn: sqlite3.Connection) -> list[PositionValue]:
    out = []
    for p in db.list_positions(conn):
        if p["asset_type"] == "cash":
            current_price = 1.0
        else:
            snap = db.latest_snapshot(conn, p["thesis_id"])
            current_price = snap["price"] if snap else p["entry_price"]
        market_value = p["shares"] * current_price
        pct_return = (current_price - p["cost_basis"]) / p["cost_basis"] if p["cost_basis"] else 0.0
        out.append(
            PositionValue(
                thesis_id=p["thesis_id"],
                symbol=p["symbol"],
                sleeve=p["sleeve"],
                target_weight=p["target_weight"],
                shares=p["shares"],
                cost_basis=p["cost_basis"],
                current_price=current_price,
                market_value=market_value,
                pct_return=pct_return,
            )
        )
    return out


def total_value(values: list[PositionValue]) -> float:
    return sum(v.market_value for v in values)


def current_weights(values: list[PositionValue]) -> dict[str, float]:
    total = total_value(values)
    if total == 0:
        return {}
    return {v.symbol: v.market_value / total for v in values}


def sleeve_weights(values: list[PositionValue]) -> dict[str, float]:
    total = total_value(values)
    if total == 0:
        return {}
    buckets: dict[str, float] = {}
    for v in values:
        buckets[v.sleeve] = buckets.get(v.sleeve, 0.0) + v.market_value
    return {sleeve: mv / total for sleeve, mv in buckets.items()}


def herfindahl_index(values: list[PositionValue]) -> float:
    """Concentration measure: sum of squared weights. 1/n for n equal-weight
    positions (lower = more diversified); 1.0 if a single position is 100%."""
    weights = current_weights(values)
    return sum(w ** 2 for w in weights.values())


def portfolio_return(values: list[PositionValue], starting_capital: float) -> float:
    return (total_value(values) - starting_capital) / starting_capital
