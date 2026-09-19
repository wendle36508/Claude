"""One-time, reviewable record of how the paper portfolio was actually built.

Run once from a fresh database: `python -m wealth_lab.seed_portfolio`.

Construction logic, in plain terms:
  - Core (50%): SPY + BND + cash. This is the risk-managed base a wealth
    manager would insist on regardless of how good any single thesis looks -
    it's what keeps one bad call from being the whole story.
  - Satellite (50%): the four funded AI-infrastructure theses already
    researched in wealth_lab (CRWV, NBIS, VRT, SNDK). Sizing within the
    satellite sleeve is signal-informed, not equal-weight: SNDK carries the
    smallest weight because its own logged signal (`parabolic_extension`)
    flags a blow-off-top risk profile, while CRWV/NBIS get the largest
    weights on stronger growth/backlog signals.
  - ANTH, CBRS, DATABRICKS stay research/watchlist theses with no funded
    position - they're pre-IPO, so there's nothing to buy yet.
"""

from __future__ import annotations

from wealth_lab import db, portfolio

STARTING_CAPITAL = 100_000.0

CORE_ALLOCATIONS = [
    # (symbol, name, sector, thesis, entry_price, sleeve, target_weight)
    ("SPY", "SPDR S&P 500 ETF Trust", "Broad Market Equity Index", "Broad US equity core; the ballast that keeps this from being an AI-only bet.", 761.69, "core_equity", 0.30),
    ("BND", "Vanguard Total Bond Market ETF", "Fixed Income Index", "Core fixed income; dampens volatility and is the standard multi-asset diversifier a stock-only portfolio lacks.", 71.94, "core_bond", 0.15),
    ("CASH", "Cash", "Cash", "Liquidity buffer for rebalancing and to avoid being forced to sell into a drawdown.", None, "cash", 0.05),
]

# thesis symbols already logged in wealth_lab, weighted by their own signals
SATELLITE_WEIGHTS = {
    "CRWV": 0.15,
    "NBIS": 0.15,
    "VRT": 0.12,
    "SNDK": 0.08,
}


def run() -> None:
    with db.connect() as conn:
        allocations = []

        for symbol, name, sector, thesis_text, entry_price, sleeve, weight in CORE_ALLOCATIONS:
            asset_type = "cash" if symbol == "CASH" else "etf"
            thesis_id = db.add_thesis(
                conn,
                symbol=symbol,
                asset_type=asset_type,
                thesis=thesis_text,
                conviction=5,
                name=name,
                sector=sector,
                entry_price=entry_price,
                entry_date="2026-09-19",
            )
            allocations.append({"thesis_id": thesis_id, "sleeve": sleeve, "target_weight": weight})

        for row in db.list_theses(conn):
            if row["symbol"] in SATELLITE_WEIGHTS:
                allocations.append(
                    {
                        "thesis_id": row["id"],
                        "sleeve": "satellite",
                        "target_weight": SATELLITE_WEIGHTS[row["symbol"]],
                    }
                )

        total_weight = sum(a["target_weight"] for a in allocations)
        assert abs(total_weight - 1.0) < 1e-9, f"weights must sum to 1.0, got {total_weight}"

        portfolio.allocate(conn, STARTING_CAPITAL, allocations)
        print(f"seeded portfolio: {len(allocations)} positions, ${STARTING_CAPITAL:,.0f} starting capital")


if __name__ == "__main__":
    run()
