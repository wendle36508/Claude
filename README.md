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
python -m wealth_lab score 1 --no-decay   # disable age-based decay, score every signal at full weight
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

**Decay.** Every signal's weight is discounted by its age (half-life 120
days by default), so a six-month-old signal counts for less than one from
this morning without ever being deleted. `--no-decay` shows the undiscounted
score for comparison.

**Confidence.** A separate [0,1] read on how much to trust the score itself,
built from three factors: *coverage* (how much evidence has fired, relative
to ~3 full-weight signals), *agreement* (how much the signals agree in
direction - two signals that cancel out score the same as zero signals but
should not be trusted the same amount, and confidence is what tells them
apart), and *recency* (how fresh the contributing evidence is). All three
multiply together, so thin evidence or real disagreement or stale signals
each independently pull confidence down.

**Expected return range.** `score` also prints a floor/base/ceiling return
(and, with an entry price, a price range), centered on the composite score
and widened automatically as confidence drops - a high-confidence thesis
gets a tight band, a contested one gets a wide one. This is a heuristic
derived from the scoring engine's own inputs, explicitly **not** a
valuation model - it has no earnings, multiple, or discount-rate inputs.
`scoring.calibrate_range_model()` is the honest fix: once enough theses
have closed with a known outcome, the band's width gets fit from what
actually happened (the realized-return-per-unit-of-score ratio) instead of
from the assumed `DEFAULT_MAX_SWING` constant. Until there's enough history
it correctly returns nothing and the default constant is used - the report
says which one is in effect.

## The public score: 0-100, for readers who aren't pricing options for a living

The -1..+1 composite score above is an analyst's number. `scoring.public_score()`
turns it into a **0-100 score** (50 = neutral, 100 = maximally bullish, 0 =
maximally bearish) meant to be read at a glance, with a plain-language label
(Strongly Bullish / Bullish / Neutral / Mixed / Bearish / Strongly Bearish -
deliberately not "Buy"/"Sell," since a number with a buy/sell label on it
reads like advice regardless of the disclaimer next to it).

It isn't just the composite score rescaled. It's **shrunk toward 50 by
confidence** first: `score_100 = 50 + (raw_score * confidence * 50)`. A single
signal logged yesterday scores +1.00 raw - identical to six signals that have
agreed for three months - so rescaling the raw number alone would show both
as "100." Shrinking by confidence means the thin one lands closer to 55-65
instead, so the headline number itself carries the "how sure is this" signal
that would otherwise require checking a separate confidence field a casual
reader won't know to look for. Zero signals and signals that exactly cancel
both land on precisely 50 - which is why the score is always shown with how
many signals it's based on, since "50 from no evidence" and "50 from
genuinely mixed evidence" are different claims the number alone can't tell
apart.

This is a presentation-layer transform, not a replacement: `composite_score()`'s
-1..+1 output is still what calibration, backtesting, and `compare_to_conviction()`
use internally. `public_score()` is what the console dashboard, the comparison
table, and (once live) the public site lead with - the CLI's `score`/`lookup`/
`compare` commands show both, SCORE (0-100) first and the technical RAW/confidence
breakdown underneath for anyone who wants it.

Worth knowing if a lot of the tracked names read as "Neutral / Mixed" (50):
that happens whenever a thesis has an equal weight of bullish and bearish
signals, which is common in this tracker's research pattern (mix bull and
bear, don't cherry-pick one side) - it's the model correctly reporting
genuinely balanced evidence, not a scoring bug.

## Compare theses side by side

```
python -m wealth_lab compare                    # every thesis, one row each, sorted by score
python -m wealth_lab compare --sort confidence
python -m wealth_lab compare --sort volatility --ascending
```

Deliberately **not** a single blended ranking number. Composite score,
confidence, expected floor/base/ceiling, and volatility each answer a
different question (direction of the evidence / how much to trust it /
plausible range / how bumpy the ride), and folding them into one score
would hide which of those is actually driving a high or low rank. Every
metric stays its own column; `--sort` picks which one orders the table.
Missing data (`—`) always sorts last regardless of direction - a thesis
with no signals yet reads as "no score," not as "worst score."

## Look up a ticker

```
python -m wealth_lab lookup NVDA
```

One view of everything already known about a symbol: thesis, sector, price
and return since entry, portfolio position (or "watchlist only"), the 0-100
public score (see below) alongside the composite score/confidence/range it's
derived from, a **per-category breakdown** (growth,
valuation, risk, catalyst, macro - `category_score()` in scoring.py runs
the same scoring math restricted to one signal category, so "growth
potential" and "risk" are separate numbers, not folded into one), and every
signal with its source.

This only reads what's already in the tracker - it can't fetch live news or
prices itself (there's no general internet access from plain Python in this
environment, only the agent's own search tool calls can reach the live
web). For a ticker that hasn't been researched yet, `lookup` says so and
points at asking the agent to research it first; once it's logged, `lookup`
is instant from then on.

## Universe coverage (S&P 500)

```
python -m wealth_lab universe-status         # X/495 researched, overall and by sector
python -m wealth_lab universe-next --n 10    # next unresearched names, round-robin across sectors
```

"Every publicly tradeable stock" isn't buildable by hand at real research
depth - `wealth_lab/universe.py` treats the S&P 500 (`universe_sp500.csv`,
495 symbol/name/sector rows) as the honest, bounded stand-in for "every
stock that matters" for the lookup tool, and tracks how much of it has an
actual thesis logged. A symbol counts as covered once *any* thesis exists
for it (open or closed) - freshness of already-open theses is a separate
question, handled by `scan.py`'s staleness check.

`universe-next` doesn't just walk the CSV top to bottom - it round-robins
across GICS sectors so coverage grows breadth-first across the market
instead of exhausting one sector before touching the next (the CSV happens
to already be grouped by sector). This is also baked into `scan.py`'s daily
digest (see below) and exposed at `GET /universe` in the API, so both the
scheduled research Routine and a frontend showing buildout progress read
from the same coverage numbers.

## Risk metrics

```
python -m wealth_lab risk 1          # volatility, Sharpe, max drawdown, beta vs SPY for thesis #1
python -m wealth_lab lookup NVDA     # same section, folded into the full ticker view
```

`wealth_lab/risk.py` computes these from actual snapshot price history, not
assumptions - which means most calls currently come back "insufficient
data" rather than a number, honestly, since most positions have one
snapshot (inception) so far. That's correct behavior: a volatility estimate
from one data point isn't one. As the daily Routine logs more snapshots,
real numbers start appearing with no code changes needed.

Two things worth knowing about the math:
- Returns are simple period-over-period returns (not log returns), and
  Sharpe's annualized mean is `periods_per_year * mean(returns)`, not a
  compounded growth rate - standard shortcuts for a quick estimate, but
  they understate compounding over long horizons.
- Snapshots are irregular (logged whenever the research Routine runs), so
  `periods_per_year` is inferred from the average gap between the
  snapshots actually taken, not assumed to be 252 or 365.
- Beta is computed only over calendar dates where both series have a data
  point, so a beta value reflects genuinely paired, same-window returns
  rather than mismatched ones.

Beta vs SPY is deliberately **not** shown per individual stock: SPY is
itself a 30% core holding in this portfolio (see below), so "does CRWV
move more than SPY" would be circular in a way that's easy to gloss over.
Beta only appears at the whole-portfolio level, per `python -m wealth_lab
portfolio` - "does the whole account move more than the market" is the
question that's actually well-posed here.

## Portfolio-level risk

`python -m wealth_lab portfolio` also shows two volatility reads, on
purpose:

- **Real** (`portfolio.portfolio_risk_metrics`) - built from
  `portfolio.value_series()`, which reconstructs total portfolio value at
  every date any position has a snapshot, forward-filling every other
  position's price from its own most recent known point. This is
  correlation-aware (it's computed from the actual combined value history,
  not summed independently), but only as fresh as each position's last
  snapshot - a date where only one position updates still understates that
  day's true portfolio-wide movement.
- **Naive upper bound** (`portfolio.naive_volatility_upper_bound`) - the
  weighted average of each position's *own* volatility, ignoring how they
  move together. This overstates true risk whenever positions aren't
  perfectly correlated (the entire point of diversifying), so it's a quick
  sanity check, not the real number. Cash counts at exactly 0% by
  definition; any position without enough of its own history is excluded,
  and the reported coverage says how much of the portfolio the estimate
  actually rests on.

The gap between the two is itself informative once there's enough
history: it's the measured diversification benefit, not an assumption.

## Portfolio construction

`wealth_lab/portfolio.py` sizes funded positions into sleeves
(`core_equity` / `core_bond` / `cash` / `satellite`) with target weights,
and computes current allocation, concentration (Herfindahl-Hirschman
Index), and return since inception from live snapshots. `python -m
wealth_lab portfolio` shows current vs. target weights and risk metrics.
`wealth_lab/seed_portfolio.py` is a reviewable record of how the current
portfolio was actually built and sized.

## Confidence-driven position sizing (comparison only)

```
python -m wealth_lab sizing
```

What score x confidence would suggest for satellite weights, shown next to
the actual current weights - **not applied**. Weight within the satellite
sleeve is re-split proportional to `|score| x confidence` per position
(the core sleeve stays structural, untouched by this - see
`seed_portfolio.py`). On this tracker's real, current data it produces a
sharp result worth seeing exactly as computed: three of the four satellite
positions currently have a net score of 0.00 (their own bull and bear
signals cancel), giving them a conviction magnitude of exactly zero - the
formula would put the entire satellite sleeve into whichever name has the
clearest evidence and zero out the rest. That's the formula working
correctly on one day of signal history, not a bug, and exactly why it's a
comparison (`wealth_lab/sizing.py`, also in the console dashboard's
portfolio card) rather than something that actually moves capital yet.

## HTTP API (provider-ready, and can be made live)

```
pip install -r requirements.txt
uvicorn wealth_lab.api:app --reload
```

A thin FastAPI layer over the same engine the CLI uses - `GET /theses`,
`GET /theses/{symbol}`, `GET /compare`, `GET /portfolio`, `GET /universe`
(S&P 500 coverage, see above), `GET /snapshot` (everything at once), and
`POST /research/{symbol}`. This exists for a real frontend that needs to
serve more than one person at once, which a static Claude Artifact can't
do.

**By default this still isn't live** - every read endpoint reflects
whatever is already in the tracker's local database, and `POST
/research/{symbol}` returns `503`, because the default `MockProvider`
honestly returns nothing rather than fabricating data. But
`wealth_lab/providers/finnhub.py` is now a real implementation, not just
an interface: set `WEALTH_LAB_PROVIDER=finnhub` and a `FINNHUB_API_KEY`
and `/research/{symbol}` actually fetches a live price, fundamentals, and
recent news for a not-yet-researched ticker and logs a new thesis (see
`providers/README.md`). What it deliberately still doesn't do is decide
bullish/bearish for you - see that same doc's last section.

**Actually deploying this somewhere real** - a persistent database that
survives redeploys, CORS locked to your real frontend, and who's allowed
to trigger writes - is a separate checklist, **[DEPLOYMENT.md](DEPLOYMENT.md)**,
because every step there needs your own accounts and can't be done from a
coding session.

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

- A live `fetch_price()` implementation once run with real network access
  (separate from the Finnhub `DataProvider` below - this is `scan.py`'s own
  staleness-refresh path).
- Finish the S&P 500 universe buildout via the daily Routine
  (`universe.py`'s `next_batch()` - see `universe-status` for the current
  count).
- News-to-signal classification for `POST /research/{symbol}` (an LLM call
  per headline deciding bullish/bearish/category) - the Finnhub
  `DataProvider` itself is built and real; this is the deliberately-deferred
  piece on top of it. See `providers/README.md`'s last section.
