"""IPO-specific analysis: where a pre-IPO thesis's disclosed valuation sits
against public comparables, and when its post-listing lockup actually
expires (the point where insiders can sell, which is a real, dated
overhang on the stock - not present for an already-public name, which is
why this lives separately from the general scoring model rather than as
another signal category).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median
from typing import Optional

from wealth_lab import db


@dataclass
class LockupStatus:
    expiry_date: Optional[str]
    is_estimate: bool  # True when based on expected_list_date rather than an actual listing
    days_until_expiry: Optional[int]  # negative if already past
    lockup_days: Optional[int]


def lockup_status(conn: sqlite3.Connection, thesis_id: int, as_of: Optional[date] = None) -> LockupStatus:
    as_of = as_of or date.today()
    details = db.get_ipo_details(conn, thesis_id)
    if details is None:
        return LockupStatus(expiry_date=None, is_estimate=False, days_until_expiry=None, lockup_days=None)

    lockup_days = details["lockup_days"]
    if details["actual_list_date"]:
        list_date = datetime.fromisoformat(details["actual_list_date"]).date()
        is_estimate = False
    elif details["expected_list_date"]:
        list_date = datetime.fromisoformat(details["expected_list_date"]).date()
        is_estimate = True
    else:
        return LockupStatus(expiry_date=None, is_estimate=False, days_until_expiry=None, lockup_days=lockup_days)

    expiry = list_date + timedelta(days=lockup_days)
    return LockupStatus(
        expiry_date=expiry.isoformat(),
        is_estimate=is_estimate,
        days_until_expiry=(expiry - as_of).days,
        lockup_days=lockup_days,
    )


@dataclass
class ValuationGap:
    ipo_multiple: Optional[float]
    peer_median: Optional[float]
    premium_to_peers: Optional[float]  # (ipo_multiple - peer_median) / peer_median
    n_comps: int
    metric: str


def valuation_gap(conn: sqlite3.Connection, thesis_id: int, metric: str = "ev_revenue") -> Optional[ValuationGap]:
    """None means there's not enough disclosed data to compute anything -
    same "insufficient data over fabricated precision" rule as the rest of
    this tracker. A result with n_comps=0 still tells you the IPO's own
    multiple; it just has no peer set logged yet to compare it against."""
    details = db.get_ipo_details(conn, thesis_id)
    if details is None or not details["disclosed_valuation"] or not details["disclosed_revenue"]:
        return None

    ipo_multiple = details["disclosed_valuation"] / details["disclosed_revenue"]
    comps = db.list_comparables(conn, thesis_id, metric=metric)
    if not comps:
        return ValuationGap(ipo_multiple=ipo_multiple, peer_median=None, premium_to_peers=None, n_comps=0, metric=metric)

    peer_values = [c["peer_multiple"] for c in comps]
    peer_med = median(peer_values)
    premium = (ipo_multiple - peer_med) / peer_med if peer_med else None
    return ValuationGap(
        ipo_multiple=ipo_multiple, peer_median=peer_med, premium_to_peers=premium,
        n_comps=len(comps), metric=metric,
    )
