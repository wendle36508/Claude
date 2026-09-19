# wealth_lab

A research tracker for stock and IPO theses, built as an evolving tool
rather than a one-shot "find the best stock" script. The point isn't a
single ranked list — it's a feedback loop: log a thesis with the individual
signals behind it (not just a 10-K skim), check in on price over time, and
periodically see which signals and conviction levels actually predicted
returns, so the research process itself improves.

## Model

- **Thesis** - a stock or IPO idea: symbol, entry price/date, conviction
  (1-5), optional target price and time horizon.
- **Signal** - one piece of evidence attached to a thesis (`insider_buying`,
  `hiring_growth`, `moat`, `valuation`, `management_quality`, whatever you're
  researching), each marked bullish/bearish/neutral with a rationale. A
  thesis can carry as many signals as you've actually researched.
- **Snapshot** - a price check-in over time, so realized return can later be
  compared against conviction and signals.

## Usage

```
python -m wealth_lab add NVDA stock "AI datacenter capex still early" \
    --conviction 4 --entry-price 120 --entry-date 2026-06-01 --target-price 180

python -m wealth_lab signal 1 hiring_growth bullish \
    --rationale "job postings up 40% YoY in data center roles"

python -m wealth_lab snapshot 1 132.50 --note "post Q2 earnings"

python -m wealth_lab list
python -m wealth_lab show 1
python -m wealth_lab report   # conviction/signal calibration vs realized return
python -m wealth_lab.scan     # digest: stale theses, current hit rate
```

Data lives in a local SQLite file at `data/tracker.db` (git-ignored).

## Composite scoring: the model, not just the log

Conviction (1-5) is a gut call typed in once, at thesis creation, and never
revisited. `wealth_lab/scoring.py` computes a second, mechanical number from
the same signals already logged: each signal's direction (bullish/bearish/
neutral) and weight combine into a score in [-1, 1], normalized by total
weight so a thesis with more signals doesn't automatically score more
extreme.

```
python -m wealth_lab score 1              # composite score using manually-set signal weights
python -m wealth_lab score 1 --learned    # same, but weights come from historical calibration
```

The two numbers are meant to be compared, not merged - `score` flags when
the systematic read of the evidence disagrees with the gut call. `--learned`
swaps in weights derived from `report.signal_calibration_by_name`: for a
signal name with enough observed history, how much its bullish calls have
actually out-returned its bearish ones. That's the self-improvement loop
closing - but it needs real return history to mean anything, and with only
a handful of theses logged so far, most signal names fall back to a neutral
weight until there's enough data. The machinery is real; the learning isn't,
yet. `python -m wealth_lab report` shows both calibrations side by side
(return by conviction level vs. return by composite score bucket) so which
one is actually predictive is a question the data answers, not an assumption.

## Portfolio construction

`wealth_lab/portfolio.py` sizes funded positions into sleeves
(`core_equity` / `core_bond` / `cash` / `satellite`) with target weights,
and computes current allocation, concentration (Herfindahl-Hirschman
Index), and return since inception from live snapshots. `python -m
wealth_lab portfolio` shows current vs. target weights and risk metrics.
`wealth_lab/seed_portfolio.py` is a reviewable record of how the current
portfolio was actually built and sized.

## Tests

```
pip install pytest
pytest tests/
```

Covers the scoring engine and portfolio math - the parts where a silent
bug would quietly produce a wrong number nobody would notice.

## Why signals instead of one score

Fundamentals (10-Ks, P&Ls) are one input among several. The signal model is
meant to hold things like insider Form 4 buying, institutional 13F flow,
hiring/job-posting growth, patent filings, management transcript sentiment,
and for IPOs, S-1 comparables and lockup expiration timing. Add a signal
type by just naming it when you log one — nothing to register in code.

## Network limitation in this environment

This session's outbound network is restricted to package registries, so
there's no live price or filings feed wired up here — `wealth_lab/scan.py`
has a single extension point, `fetch_price()`, documented in that file,
where a live provider (a market-data API, a broker feed, an EDGAR client)
plugs in once run somewhere with broader network access. Until then, prices
and signals are logged by hand or imported from data you pull yourself.

## Roadmap ideas (not yet built)

- A live `fetch_price()` implementation once run with real network access.
- An IPO-specific thesis helper (S-1 comparables, lockup calendar).
- A scheduled scan (e.g. via a Claude Code Routine) that runs `scan.py`
  daily and reports stale theses or notable signal changes.
- Signal weighting informed by `report.py`'s calibration output, instead of
  a flat weight of 1.0 for everything.
