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

from wealth_lab import db, risk


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


def value_series(conn: sqlite3.Connection) -> list[tuple[str, float]]:
    """Reconstruct total portfolio value at every date any position has a
    snapshot, forward-filling each other position's price from its own most
    recent known point (its last snapshot, or its entry price/date before
    any snapshot exists). Caveat: a date where only one position actually
    got a fresh snapshot still understates that day's true portfolio-wide
    movement, since other positions may have moved too without an
    observation to show it - this series is only as fresh as each
    position's own last snapshot, not a true daily mark."""
    per_position: list[tuple[float, list[tuple[str, float]], str]] = []  # (shares, sorted points, asset_type)
    all_dates: set[str] = set()

    for p in db.list_positions(conn):
        if p["asset_type"] == "cash":
            per_position.append((p["shares"], [], "cash"))
            continue
        thesis = db.get_thesis(conn, p["thesis_id"])
        points = dict(risk.price_series(conn, p["thesis_id"]))
        if thesis["entry_price"] is not None and thesis["entry_date"]:
            points.setdefault(thesis["entry_date"], thesis["entry_price"])
        sorted_points = sorted(points.items())
        per_position.append((p["shares"], sorted_points, p["asset_type"]))
        all_dates.update(points.keys())

    series = []
    for d in sorted(all_dates):
        total = 0.0
        for shares, points, asset_type in per_position:
            if asset_type == "cash":
                total += shares * 1.0
                continue
            price_at_or_before = None
            for pd, price in points:
                if pd <= d:
                    price_at_or_before = price
                else:
                    break
            if price_at_or_before is not None:
                total += shares * price_at_or_before
        series.append((d, total))
    return series


def portfolio_risk_metrics(
    conn: sqlite3.Connection, benchmark_thesis_id: Optional[int] = None, risk_free_rate: float = 0.0
) -> risk.RiskMetrics:
    """Real, correlation-aware risk metrics for the whole portfolio, built
    from value_series() - see its docstring for the forward-fill staleness
    caveat. This is the actual number; naive_volatility_upper_bound() below
    is a quick sanity check against it, not a replacement for it."""
    series = value_series(conn)
    benchmark_series = risk.price_series(conn, benchmark_thesis_id) if benchmark_thesis_id is not None else None
    return risk.metrics_from_series(series, benchmark_series, risk_free_rate)


@dataclass
class NaiveVolatilityEstimate:
    weighted_volatility: float
    covered_weight: float  # fraction of current portfolio value this estimate is based on
    n_positions_included: int


def naive_volatility_upper_bound(conn: sqlite3.Connection) -> Optional[NaiveVolatilityEstimate]:
    """Weighted average of each position's OWN volatility (current
    market-value weight), ignoring how positions move together. This
    overstates true portfolio risk whenever positions aren't perfectly
    correlated - which is the entire point of diversifying - so it's a
    quick upper-bound sanity check against portfolio_risk_metrics()'s real,
    correlation-aware number, not a substitute for it. Cash is included at
    exactly 0 volatility by definition; any other position without enough
    of its own price history is excluded, and covered_weight says how much
    of the portfolio (by current value) the estimate actually rests on."""
    values = current_values(conn)
    weights = current_weights(values)
    if not weights:
        return None

    weighted_sum = 0.0
    covered_weight = 0.0
    n_included = 0
    for v in values:
        thesis = db.get_thesis(conn, v.thesis_id)
        if thesis["asset_type"] == "cash":
            vol = 0.0
        else:
            vol = risk.compute_risk_metrics(conn, v.thesis_id).volatility
        if vol is None:
            continue
        w = weights[v.symbol]
        weighted_sum += w * vol
        covered_weight += w
        n_included += 1

    if covered_weight == 0:
        return None
    return NaiveVolatilityEstimate(
        weighted_volatility=weighted_sum / covered_weight,
        covered_weight=covered_weight,
        n_positions_included=n_included,
    )
