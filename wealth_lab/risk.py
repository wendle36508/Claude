"""Real risk metrics computed from snapshot price history: volatility,
Sharpe ratio, max drawdown, and beta against a benchmark thesis (SPY).

Everything here needs an actual return *series* - two or more price
observations over time - not a single point. With this tracker's current
history (most positions have one snapshot: inception), that means most
calls come back as "insufficient data" rather than a number, which is the
correct behavior, not a bug: a volatility estimate from one data point is
not a volatility estimate. As the daily research Routine logs more
snapshots, these start returning real numbers without any code changing.

Two simplifications, stated plainly rather than hidden in the math:
  - Returns are simple period-over-period returns, not log returns, and
    Sharpe's "annualized mean" is periods_per_year * mean(returns), not a
    compounded annual growth rate - both approximations are standard for a
    quick estimate but understate compounding over longer horizons.
  - Snapshots are irregular (logged whenever the research Routine runs, not
    on a fixed calendar), so periods_per_year is inferred from the average
    gap between the snapshots actually taken, not assumed to be 252
    (trading days) or 365.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from statistics import mean, stdev
from typing import Optional

from wealth_lab import db

MIN_SNAPSHOTS_FOR_VOLATILITY = 3  # >=2 returns
MIN_ALIGNED_POINTS_FOR_BETA = 4  # >=3 paired returns


def price_series(conn: sqlite3.Connection, thesis_id: int) -> list[tuple[str, float]]:
    """(date, price) pairs from snapshots, chronological, one per calendar
    date (last snapshot wins if there were several the same day)."""
    by_date: dict[str, float] = {}
    for snap in db.list_snapshots(conn, thesis_id):
        by_date[snap["recorded_at"][:10]] = snap["price"]
    return sorted(by_date.items())


def periodic_returns(series: list[tuple[str, float]]) -> list[float]:
    prices = [p for _, p in series]
    return [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]


def inferred_periods_per_year(series: list[tuple[str, float]]) -> Optional[float]:
    if len(series) < 2:
        return None
    dates = [datetime.fromisoformat(d) for d, _ in series]
    span_days = (dates[-1] - dates[0]).days
    if span_days <= 0:
        return None
    avg_gap_days = span_days / (len(series) - 1)
    return 365.25 / avg_gap_days


def volatility(returns: list[float], periods_per_year: float) -> Optional[float]:
    if len(returns) < 2:
        return None
    return stdev(returns) * (periods_per_year ** 0.5)


def sharpe_ratio(returns: list[float], periods_per_year: float, risk_free_rate: float = 0.0) -> Optional[float]:
    if len(returns) < 2:
        return None
    vol = volatility(returns, periods_per_year)
    if not vol:
        return None
    annualized_mean = mean(returns) * periods_per_year
    return (annualized_mean - risk_free_rate) / vol


def max_drawdown(series: list[tuple[str, float]]) -> Optional[float]:
    if len(series) < 2:
        return None
    peak = series[0][1]
    worst = 0.0
    for _, price in series:
        peak = max(peak, price)
        worst = min(worst, (price - peak) / peak)
    return worst


def aligned_returns_from_series(
    series_a: list[tuple[str, float]], series_b: list[tuple[str, float]]
) -> tuple[list[float], list[float]]:
    """Paired period-over-period returns for two (date, price) series,
    computed only over calendar dates where both have a point - so a
    return here reflects the same time window on both sides. Works for any
    two series, not just single positions - a reconstructed portfolio value
    series lines up with this exactly as well as one thesis's price_series does."""
    a = dict(series_a)
    b = dict(series_b)
    common_dates = sorted(set(a) & set(b))
    if len(common_dates) < 2:
        return [], []
    prices_a = [a[d] for d in common_dates]
    prices_b = [b[d] for d in common_dates]
    returns_a = [(prices_a[i] - prices_a[i - 1]) / prices_a[i - 1] for i in range(1, len(prices_a))]
    returns_b = [(prices_b[i] - prices_b[i - 1]) / prices_b[i - 1] for i in range(1, len(prices_b))]
    return returns_a, returns_b


def aligned_returns(
    conn: sqlite3.Connection, thesis_id: int, benchmark_thesis_id: int
) -> tuple[list[float], list[float]]:
    """Paired period-over-period returns for a thesis and a benchmark thesis,
    computed only over calendar dates where both have a snapshot."""
    return aligned_returns_from_series(price_series(conn, thesis_id), price_series(conn, benchmark_thesis_id))


def beta(returns_asset: list[float], returns_benchmark: list[float]) -> Optional[float]:
    if len(returns_asset) < 2 or len(returns_asset) != len(returns_benchmark):
        return None
    benchmark_var = stdev(returns_benchmark) ** 2
    if benchmark_var == 0:
        return None
    asset_mean = mean(returns_asset)
    bench_mean = mean(returns_benchmark)
    n = len(returns_asset)
    covariance = sum(
        (a - asset_mean) * (b - bench_mean) for a, b in zip(returns_asset, returns_benchmark)
    ) / (n - 1)
    return covariance / benchmark_var


@dataclass
class RiskMetrics:
    n_snapshots: int
    n_returns: int
    periods_per_year: Optional[float]
    volatility: Optional[float]
    sharpe: Optional[float]
    max_drawdown: Optional[float]
    beta_vs_benchmark: Optional[float]
    n_aligned_returns: int
    sufficient: bool  # False when volatility/sharpe/drawdown are None for lack of history


def metrics_from_series(
    series: list[tuple[str, float]],
    benchmark_series: Optional[list[tuple[str, float]]] = None,
    risk_free_rate: float = 0.0,
) -> RiskMetrics:
    """The generic engine behind compute_risk_metrics: works on any (date,
    price) series, not just a single position's - a reconstructed portfolio
    value series plugs in exactly the same way."""
    returns = periodic_returns(series)
    periods_per_year = inferred_periods_per_year(series)

    vol = sharpe = dd = None
    if len(returns) >= 2 and periods_per_year:
        vol = volatility(returns, periods_per_year)
        sharpe = sharpe_ratio(returns, periods_per_year, risk_free_rate)
    if len(series) >= 2:
        dd = max_drawdown(series)

    b = None
    n_aligned = 0
    if benchmark_series is not None:
        ra, rb = aligned_returns_from_series(series, benchmark_series)
        n_aligned = len(ra)
        if n_aligned >= 2:
            b = beta(ra, rb)

    return RiskMetrics(
        n_snapshots=len(series),
        n_returns=len(returns),
        periods_per_year=periods_per_year,
        volatility=vol,
        sharpe=sharpe,
        max_drawdown=dd,
        beta_vs_benchmark=b,
        n_aligned_returns=n_aligned,
        sufficient=len(series) >= MIN_SNAPSHOTS_FOR_VOLATILITY,
    )


def compute_risk_metrics(
    conn: sqlite3.Connection,
    thesis_id: int,
    benchmark_thesis_id: Optional[int] = None,
    risk_free_rate: float = 0.0,
) -> RiskMetrics:
    series = price_series(conn, thesis_id)
    benchmark_series = None
    if benchmark_thesis_id is not None and benchmark_thesis_id != thesis_id:
        benchmark_series = price_series(conn, benchmark_thesis_id)
    return metrics_from_series(series, benchmark_series, risk_free_rate)
