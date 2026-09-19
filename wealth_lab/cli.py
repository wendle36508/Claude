"""Command-line interface for the research tracker.

    python -m wealth_lab add AAPL stock "thesis text" --conviction 4 --entry-price 230 --sector "Consumer Hardware"
    python -m wealth_lab signal 1 insider_buying bullish --category growth --rationale "CEO bought $2M"
    python -m wealth_lab snapshot 1 245.10 --note "post-earnings pop"
    python -m wealth_lab close 1 closed_win
    python -m wealth_lab show 1
    python -m wealth_lab list --status open
    python -m wealth_lab report
    python -m wealth_lab score 1
    python -m wealth_lab lookup AAPL     # everything known about a ticker in one view
"""

from __future__ import annotations

import argparse
import sys

from wealth_lab import compare, db, ipo, portfolio, report, risk, scoring, sizing

BENCHMARK_SYMBOL = "SPY"


def cmd_add(conn, args) -> None:
    thesis_id = db.add_thesis(
        conn,
        symbol=args.symbol,
        asset_type=args.asset_type,
        thesis=args.thesis,
        conviction=args.conviction,
        name=args.name,
        sector=args.sector,
        entry_price=args.entry_price,
        entry_date=args.entry_date,
        target_price=args.target_price,
        horizon_days=args.horizon_days,
    )
    print(f"added thesis #{thesis_id}: {args.symbol.upper()} ({args.asset_type})")


def cmd_signal(conn, args) -> None:
    if db.get_thesis(conn, args.thesis_id) is None:
        sys.exit(f"no thesis #{args.thesis_id}")
    sig_id = db.add_signal(
        conn,
        thesis_id=args.thesis_id,
        name=args.name,
        direction=args.direction,
        category=args.category,
        rationale=args.rationale,
        weight=args.weight,
        source=args.source,
    )
    print(f"added signal #{sig_id} ({args.name}: {args.direction}, {args.category}) to thesis #{args.thesis_id}")


def cmd_snapshot(conn, args) -> None:
    if db.get_thesis(conn, args.thesis_id) is None:
        sys.exit(f"no thesis #{args.thesis_id}")
    snap_id = db.add_snapshot(conn, args.thesis_id, args.price, note=args.note)
    print(f"added snapshot #{snap_id}: thesis #{args.thesis_id} @ {args.price}")


def cmd_close(conn, args) -> None:
    if db.get_thesis(conn, args.thesis_id) is None:
        sys.exit(f"no thesis #{args.thesis_id}")
    db.set_status(conn, args.thesis_id, args.status)
    print(f"thesis #{args.thesis_id} -> {args.status}")


def cmd_show(conn, args) -> None:
    t = db.get_thesis(conn, args.thesis_id)
    if t is None:
        sys.exit(f"no thesis #{args.thesis_id}")
    print(f"#{t['id']} {t['symbol']} ({t['asset_type']}) - {t['status']} - conviction {t['conviction']}/5")
    if t["name"]:
        print(f"  {t['name']}" + (f" · {t['sector']}" if t["sector"] else ""))
    print(f"  thesis: {t['thesis']}")
    if t["entry_price"] is not None:
        print(f"  entry: {t['entry_price']} on {t['entry_date'] or '?'}"
              + (f", target {t['target_price']}" if t["target_price"] else ""))
    signals = db.list_signals(conn, args.thesis_id)
    if signals:
        print("  signals:")
        for s in signals:
            print(f"    - [{s['category']}] {s['name']}: {s['direction']} (w={s['weight']}) {s['rationale'] or ''}")
    snaps = db.list_snapshots(conn, args.thesis_id)
    if snaps:
        print("  snapshots:")
        for s in snaps:
            print(f"    - {s['recorded_at']}: {s['price']}" + (f" ({s['note']})" if s["note"] else ""))


def cmd_list(conn, args) -> None:
    theses = db.list_theses(conn, status=args.status)
    if not theses:
        print("no theses recorded yet")
        return
    for t in theses:
        snap = db.latest_snapshot(conn, t["id"])
        ret = ""
        if snap and t["entry_price"]:
            pct = (snap["price"] - t["entry_price"]) / t["entry_price"] * 100
            ret = f" | {pct:+.1f}%"
        print(f"#{t['id']:<3} {t['symbol']:<6} {t['asset_type']:<5} conv={t['conviction']} {t['status']:<12}{ret}")


def cmd_report(conn, args) -> None:
    returns = report.thesis_returns(conn)
    if not returns:
        print("no theses have both an entry price and a snapshot yet - nothing to calibrate")
        return

    print("== return by conviction level ==")
    for level, stats in report.conviction_calibration(returns).items():
        print(f"  conviction {level}: n={stats['n']:<3} avg return={stats['avg_return'] * 100:+.1f}%")

    print("\n== return by signal ==")
    for key, stats in report.signal_calibration(conn, returns).items():
        print(f"  {key:<35} n={stats['n']:<3} avg return={stats['avg_return'] * 100:+.1f}%")

    print("\n== return by composite signal score (manual weights) ==")
    for bucket, stats in scoring.score_calibration(conn).items():
        print(f"  {bucket:<15} n={stats['n']:<3} avg return={stats['avg_return'] * 100:+.1f}%")
    print("  (this is the check that matters: does the mechanical score beat gut conviction "
          "at predicting return? not enough data yet to say - keep tracking)")

    hr = report.hit_rate(conn)
    print("\n== hit rate (closed theses) ==")
    if hr:
        print(f"  {hr['wins']}/{hr['n_closed']} = {hr['hit_rate'] * 100:.0f}%")
    else:
        print("  no closed theses yet")


def cmd_portfolio(conn, args) -> None:
    values = portfolio.current_values(conn)
    if not values:
        print("no funded positions yet - run `python -m wealth_lab.seed_portfolio`")
        return

    total = portfolio.total_value(values)
    weights = portfolio.current_weights(values)

    print(f"== positions (total market value ${total:,.2f}) ==")
    for v in sorted(values, key=lambda v: v.market_value, reverse=True):
        print(
            f"  {v.symbol:<8} {v.sleeve:<12} target={v.target_weight * 100:5.1f}%  "
            f"actual={weights[v.symbol] * 100:5.1f}%  value=${v.market_value:>10,.2f}  "
            f"return={v.pct_return * 100:+.1f}%"
        )

    print("\n== sleeve breakdown ==")
    for sleeve, w in sorted(portfolio.sleeve_weights(values).items(), key=lambda kv: -kv[1]):
        print(f"  {sleeve:<12} {w * 100:5.1f}%")

    hhi = portfolio.herfindahl_index(values)
    print(f"\nconcentration (HHI): {hhi:.3f}  (1/n for n equal-weight positions; lower = more diversified)")

    ret = portfolio.portfolio_return(values, args.starting_capital)
    print(f"portfolio return since inception: {ret * 100:+.2f}%  (vs starting capital ${args.starting_capital:,.0f})")

    print("\n== portfolio risk (whole account) ==")
    benchmark = db.get_thesis_by_symbol(conn, BENCHMARK_SYMBOL)
    benchmark_id = benchmark["id"] if benchmark else None
    m = portfolio.portfolio_risk_metrics(conn, benchmark_thesis_id=benchmark_id)
    _print_risk_metrics(m)

    naive = portfolio.naive_volatility_upper_bound(conn)
    if naive:
        print(f"  naive volatility upper-bound: {naive.weighted_volatility * 100:.1f}%  "
              f"(weighted avg of each position's own vol, ignoring correlation - "
              f"coverage {naive.covered_weight * 100:.0f}% of portfolio, {naive.n_positions_included} positions)")
        if m.volatility is not None:
            gap = naive.weighted_volatility - m.volatility
            print(f"  -> real portfolio vol is {gap * 100:.1f}pp below the naive estimate; "
                  "that gap is the measured diversification benefit")
    else:
        print("  naive volatility upper-bound: not enough per-position history yet")


def cmd_score(conn, args) -> None:
    thesis = db.get_thesis(conn, args.thesis_id)
    if thesis is None:
        sys.exit(f"no thesis #{args.thesis_id}")

    signal_weights = scoring.learned_signal_weights(conn) if args.learned else None
    half_life = None if args.no_decay else scoring.DECAY_HALF_LIFE_DAYS
    result = scoring.composite_score(conn, args.thesis_id, signal_weights=signal_weights, half_life_days=half_life)
    if result is None:
        print(f"#{args.thesis_id} {thesis['symbol']}: no signals logged yet - nothing to score")
        return

    print(f"#{args.thesis_id} {thesis['symbol']} - composite score ({result.weights_used} weights"
          f"{', no decay' if args.no_decay else ''})")
    for c in result.breakdown:
        age_note = f"age={c.age_days:.0f}d decay={c.decay:.2f}" if c.decay < 0.99 else "fresh"
        print(f"  {c.name:<30} {c.direction:<9} weight={c.base_weight:.2f}->{c.effective_weight:.2f} "
              f"({age_note})  contribution={c.contribution:+.2f}")
    print(f"\n  composite score: {result.score:+.2f}  (range -1 bearish .. +1 bullish, n={result.n_signals})")

    cmp = scoring.compare_to_conviction(conn, args.thesis_id, result)
    print(f"  manual conviction: {cmp['conviction']}/5  (normalized {cmp['conviction_normalized']:+.2f})")
    if cmp["agrees"]:
        print("  -> signal score and conviction broadly agree")
    else:
        print(f"  -> DIVERGES from conviction by {cmp['delta']:+.2f} - worth a second look")

    conf = scoring.confidence(result)
    print(f"\n  confidence: {conf.confidence:.2f} ({conf.band})  "
          f"[coverage={conf.coverage:.2f} agreement={conf.agreement:.2f} recency={conf.recency:.2f}]")

    rng = scoring.expected_return_range(conn, result, conf, entry_price=thesis["entry_price"])
    print(f"  expected return range ({rng.source} width): "
          f"floor {rng.floor_return * 100:+.1f}%  base {rng.base_return * 100:+.1f}%  ceiling {rng.ceiling_return * 100:+.1f}%")
    if rng.floor_price is not None:
        print(f"    -> price: floor ${rng.floor_price:,.2f}  base ${rng.base_price:,.2f}  ceiling ${rng.ceiling_price:,.2f}")
    print("  (heuristic band from the scoring engine's own inputs, not a valuation model - "
          "widens automatically when confidence is low)")

    if args.learned and not signal_weights:
        print("\n  note: no signal name has enough return history yet to learn a weight "
              f"(needs >= {scoring.MIN_OBSERVATIONS_TO_LEARN} observations with both bullish and bearish outcomes) "
              "- these are effectively manual weights until then")


def _print_risk_metrics(m: risk.RiskMetrics) -> None:
    if not m.sufficient:
        print(f"Risk metrics: not enough price history yet ({m.n_snapshots} snapshot(s), "
              f"need >= {risk.MIN_SNAPSHOTS_FOR_VOLATILITY}) - volatility/Sharpe/drawdown need a real return series")
        return

    print(f"Risk metrics ({m.n_returns} periods, ~{m.periods_per_year:.0f}/yr inferred from snapshot spacing):")
    print(f"  volatility (annualized): {m.volatility * 100:.1f}%" if m.volatility is not None else "  volatility: n/a")
    print(f"  sharpe ratio:            {m.sharpe:+.2f}" if m.sharpe is not None else "  sharpe ratio: n/a")
    print(f"  max drawdown:            {m.max_drawdown * 100:.1f}%" if m.max_drawdown is not None else "  max drawdown: n/a")
    if m.beta_vs_benchmark is not None:
        print(f"  beta vs {BENCHMARK_SYMBOL}:              {m.beta_vs_benchmark:+.2f}  (n={m.n_aligned_returns} aligned periods)")
    elif m.n_aligned_returns > 0:
        print(f"  beta vs {BENCHMARK_SYMBOL}: not enough aligned history yet ({m.n_aligned_returns} paired periods, "
              f"need >= {risk.MIN_ALIGNED_POINTS_FOR_BETA - 1})")


def cmd_risk(conn, args) -> None:
    thesis = db.get_thesis(conn, args.thesis_id)
    if thesis is None:
        sys.exit(f"no thesis #{args.thesis_id}")

    # No per-stock beta vs SPY here on purpose: SPY is itself a holding in
    # this portfolio (see `portfolio`), so "the whole account vs SPY" is
    # the meaningful comparison - beta only appears at the portfolio level.
    print(f"#{args.thesis_id} {thesis['symbol']} - risk metrics")
    m = risk.compute_risk_metrics(conn, args.thesis_id)
    _print_risk_metrics(m)


def cmd_lookup(conn, args) -> None:
    """The 'search a ticker, see everything' view: thesis, sector, price/return,
    portfolio position, category sub-scores, and every signal with its source -
    all pulled from what's already in the tracker, nothing fetched live."""
    t = db.get_thesis_by_symbol(conn, args.symbol)
    if t is None:
        print(f"{args.symbol.upper()} hasn't been researched yet - nothing in the tracker for it.")
        print("This command only reads what's already logged; it can't fetch live news or prices itself.")
        print(f"Ask the agent to research {args.symbol.upper()} first (it'll WebSearch, log sourced")
        print("signals, and then this lookup will work instantly from then on.)")
        return

    print(f"=== {t['symbol']} lookup ===")
    header = f"{t['name'] or t['symbol']}"
    if t["sector"]:
        header += f"  ·  {t['sector']}"
    header += f"  ·  {t['asset_type']}  ·  {t['status']}"
    print(header)
    print(f"\n{t['thesis']}")

    snap = db.latest_snapshot(conn, t["id"])
    if t["entry_price"] is not None:
        price_line = f"\nEntry ${t['entry_price']:,.2f} on {t['entry_date'] or '?'}"
        if snap:
            ret = (snap["price"] - t["entry_price"]) / t["entry_price"]
            price_line += f"  ->  latest ${snap['price']:,.2f} ({snap['recorded_at'][:10]})  return {ret * 100:+.1f}%"
        print(price_line)

    pos = db.get_position_for_thesis(conn, t["id"])
    if pos:
        print(f"Portfolio: {pos['sleeve']} sleeve, target {pos['target_weight'] * 100:.1f}%, "
              f"{pos['shares']:.4f} shares @ cost ${pos['cost_basis']:,.2f}")
    else:
        print("Portfolio: not funded - watchlist only")

    result = scoring.composite_score(conn, t["id"])
    if result is None:
        print("\nNo signals logged yet - nothing to score.")
        return

    conf = scoring.confidence(result)
    rng = scoring.expected_return_range(conn, result, conf, entry_price=t["entry_price"])
    print(f"\nComposite score: {result.score:+.2f}   Confidence: {conf.confidence:.2f} ({conf.band})   "
          f"Conviction: {t['conviction']}/5")
    print(f"Expected range ({rng.source}): floor {rng.floor_return * 100:+.1f}%  "
          f"base {rng.base_return * 100:+.1f}%  ceiling {rng.ceiling_return * 100:+.1f}%"
          + (f"  ->  ${rng.floor_price:,.2f} / ${rng.base_price:,.2f} / ${rng.ceiling_price:,.2f}" if rng.floor_price else ""))

    print("\nBy category:")
    for category in db.SIGNAL_CATEGORIES:
        cat_result = scoring.category_score(conn, t["id"], category)
        if cat_result is None:
            continue
        print(f"  {category:<10} {cat_result.score:+.2f}  (n={cat_result.n_signals})")

    print("\nSignals:")
    for s in db.list_signals(conn, t["id"]):
        source = f"  [{s['source']}]" if s["source"] else ""
        print(f"  [{s['category']:<9}] {s['direction']:<8} {s['name']:<28} {s['rationale'] or ''}{source}")

    # No per-stock beta vs SPY here on purpose - see cmd_risk's comment.
    print()
    _print_risk_metrics(risk.compute_risk_metrics(conn, t["id"]))


def cmd_compare(conn, args) -> None:
    rows = compare.build_comparison(conn, status=args.status)
    if not rows:
        print("no theses recorded yet")
        return
    rows = compare.sort_rows(rows, by=args.sort, descending=not args.ascending)

    def fmt_pct(v):
        return f"{v * 100:+.1f}%" if v is not None else "  —  "

    def fmt(v, spec):
        return format(v, spec) if v is not None else "  —  "

    header = (f"{'SYMBOL':<10} {'SECTOR':<26} {'STATUS':<11} {'CONV':>4} {'SCORE':>6} "
              f"{'CONF':>5} {'FLOOR':>7} {'BASE':>7} {'CEIL':>7} {'VOL':>7}")
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r.symbol:<10} {(r.sector or '—')[:26]:<26} {r.status:<11} {r.conviction:>4} "
            f"{fmt(r.score, '+.2f'):>6} {fmt(r.confidence, '.2f'):>5} "
            f"{fmt_pct(r.floor_return):>7} {fmt_pct(r.base_return):>7} {fmt_pct(r.ceiling_return):>7} "
            f"{fmt_pct(r.volatility):>7}"
        )
    print(f"\nsorted by {args.sort} ({'descending' if not args.ascending else 'ascending'}); "
          "'—' means not enough data yet for that column, not zero")


def cmd_ipo_set(conn, args) -> None:
    if db.get_thesis(conn, args.thesis_id) is None:
        sys.exit(f"no thesis #{args.thesis_id}")
    db.set_ipo_details(
        conn, args.thesis_id,
        expected_list_date=args.expected_list_date, actual_list_date=args.actual_list_date,
        lockup_days=args.lockup_days, disclosed_valuation=args.valuation,
        disclosed_revenue=args.revenue, notes=args.notes,
    )
    print(f"set IPO details for thesis #{args.thesis_id}")


def cmd_ipo_comp(conn, args) -> None:
    if db.get_thesis(conn, args.thesis_id) is None:
        sys.exit(f"no thesis #{args.thesis_id}")
    comp_id = db.add_comparable(
        conn, args.thesis_id, args.peer_symbol, args.multiple,
        peer_name=args.peer_name, metric=args.metric, source=args.source,
    )
    print(f"added comparable #{comp_id}: {args.peer_symbol.upper()} {args.metric}={args.multiple} to thesis #{args.thesis_id}")


def cmd_ipo_show(conn, args) -> None:
    t = db.get_thesis(conn, args.thesis_id)
    if t is None:
        sys.exit(f"no thesis #{args.thesis_id}")
    details = db.get_ipo_details(conn, args.thesis_id)

    print(f"#{args.thesis_id} {t['symbol']} - IPO details")
    if details is None:
        print("  no IPO details set yet - use `ipo set` to add expected list date / valuation / revenue")
        return

    if details["disclosed_valuation"] and details["disclosed_revenue"]:
        print(f"  disclosed: ${details['disclosed_valuation']:,.0f} valuation on "
              f"${details['disclosed_revenue']:,.0f} revenue")
    if details["notes"]:
        print(f"  notes: {details['notes']}")

    lockup = ipo.lockup_status(conn, args.thesis_id)
    if lockup.expiry_date:
        est = " (estimate, based on expected list date)" if lockup.is_estimate else ""
        print(f"  lockup expiry: {lockup.expiry_date}{est} - {lockup.days_until_expiry:+d} days from today")
    else:
        print("  lockup expiry: unknown (no expected/actual list date set)")

    gap = ipo.valuation_gap(conn, args.thesis_id)
    if gap is None:
        print("  valuation comp: n/a (need both disclosed valuation and revenue set)")
    else:
        print(f"  implied multiple ({gap.metric}): {gap.ipo_multiple:.1f}x")
        if gap.n_comps == 0:
            print("  no comparables logged yet - use `ipo comp` to add public peers")
        else:
            print(f"  peer median ({gap.n_comps} comps): {gap.peer_median:.1f}x  "
                  f"-> {'premium' if gap.premium_to_peers >= 0 else 'discount'} of {abs(gap.premium_to_peers) * 100:.0f}% to peers")
            for c in db.list_comparables(conn, args.thesis_id, metric=gap.metric):
                print(f"    {c['peer_symbol']:<6} {c['peer_multiple']:.1f}x" + (f"  [{c['source']}]" if c["source"] else ""))


def cmd_sizing(conn, args) -> None:
    suggestions = sizing.satellite_sizing(conn)
    if not suggestions:
        print("no funded satellite positions yet")
        return

    print("== confidence-driven sizing vs. current satellite weights ==")
    print("(comparison only - not applied. see wealth_lab/sizing.py for why.)\n")
    header = f"{'SYMBOL':<8} {'CONVICTION':>11} {'CURRENT':>9} {'SUGGESTED':>10} {'DELTA':>8}"
    print(header)
    print("-" * len(header))
    for s in sorted(suggestions, key=lambda s: s.suggested_weight, reverse=True):
        print(
            f"{s.symbol:<8} {s.conviction_magnitude:>11.3f} {s.current_weight * 100:>8.1f}% "
            f"{s.suggested_weight * 100:>9.1f}% {s.delta * 100:>+7.1f}%"
        )

    zero_mag = [s.symbol for s in suggestions if s.conviction_magnitude == 0]
    if zero_mag:
        print(f"\n{', '.join(zero_mag)} scored 0 conviction magnitude (net-zero score, or bull/bear signals "
              "canceling) - the formula would zero these out in favor of whatever currently has the clearest "
              "evidence, which is a real reflection of thin day-one signal history, not something to act on yet.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wealth_lab")
    sub = p.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="log a new thesis")
    add.add_argument("symbol")
    add.add_argument("asset_type", choices=["stock", "ipo", "etf", "cash"])
    add.add_argument("thesis")
    add.add_argument("--conviction", type=int, required=True, choices=range(1, 6))
    add.add_argument("--name")
    add.add_argument("--sector", help="e.g. 'AI Cloud Infrastructure' - the market/category this competes in")
    add.add_argument("--entry-price", type=float)
    add.add_argument("--entry-date")
    add.add_argument("--target-price", type=float)
    add.add_argument("--horizon-days", type=int)
    add.set_defaults(func=cmd_add)

    sig = sub.add_parser("signal", help="attach a signal to a thesis")
    sig.add_argument("thesis_id", type=int)
    sig.add_argument("name")
    sig.add_argument("direction", choices=["bullish", "bearish", "neutral"])
    sig.add_argument("--category", choices=db.SIGNAL_CATEGORIES, default="other",
                      help="growth / valuation / risk / catalyst / macro / other")
    sig.add_argument("--rationale")
    sig.add_argument("--weight", type=float, default=1.0)
    sig.add_argument("--source")
    sig.set_defaults(func=cmd_signal)

    snap = sub.add_parser("snapshot", help="record a price check-in")
    snap.add_argument("thesis_id", type=int)
    snap.add_argument("price", type=float)
    snap.add_argument("--note")
    snap.set_defaults(func=cmd_snapshot)

    close = sub.add_parser("close", help="close out a thesis")
    close.add_argument("thesis_id", type=int)
    close.add_argument("status", choices=["closed_win", "closed_loss", "closed_flat"])
    close.set_defaults(func=cmd_close)

    show = sub.add_parser("show", help="show one thesis in full")
    show.add_argument("thesis_id", type=int)
    show.set_defaults(func=cmd_show)

    ls = sub.add_parser("list", help="list theses")
    ls.add_argument("--status", choices=["open", "closed_win", "closed_loss", "closed_flat"])
    ls.set_defaults(func=cmd_list)

    rep = sub.add_parser("report", help="calibration report: conviction/signals vs realized return")
    rep.set_defaults(func=cmd_report)

    pf = sub.add_parser("portfolio", help="show current portfolio allocation and risk metrics")
    pf.add_argument("--starting-capital", type=float, default=100_000.0)
    pf.set_defaults(func=cmd_portfolio)

    sc = sub.add_parser("score", help="computed composite score from a thesis's signals, vs. its manual conviction")
    sc.add_argument("thesis_id", type=int)
    sc.add_argument("--learned", action="store_true", help="use historically-learned per-signal weights instead of manual weights")
    sc.add_argument("--no-decay", action="store_true", help="don't discount older signals - score every signal at full weight regardless of age")
    sc.set_defaults(func=cmd_score)

    lu = sub.add_parser("lookup", help="everything known about a ticker: thesis, scores, signals, portfolio position")
    lu.add_argument("symbol")
    lu.set_defaults(func=cmd_lookup)

    rk = sub.add_parser("risk", help="volatility, Sharpe, max drawdown, beta vs SPY - from real snapshot history")
    rk.add_argument("thesis_id", type=int)
    rk.set_defaults(func=cmd_risk)

    cmp = sub.add_parser("compare", help="every thesis side by side - one row each, every metric its own column")
    cmp.add_argument("--status", choices=["open", "closed_win", "closed_loss", "closed_flat"])
    cmp.add_argument("--sort", choices=compare.SORTABLE_COLUMNS, default="score")
    cmp.add_argument("--ascending", action="store_true", help="sort ascending instead of descending")
    cmp.set_defaults(func=cmd_compare)

    ipo_set = sub.add_parser("ipo-set", help="set/update a pre-IPO thesis's list date, lockup, and disclosed valuation")
    ipo_set.add_argument("thesis_id", type=int)
    ipo_set.add_argument("--expected-list-date", help="YYYY-MM-DD, forecast")
    ipo_set.add_argument("--actual-list-date", help="YYYY-MM-DD, once it actually lists")
    ipo_set.add_argument("--lockup-days", type=int, default=180)
    ipo_set.add_argument("--valuation", type=float, help="disclosed/rumored valuation in dollars")
    ipo_set.add_argument("--revenue", type=float, help="disclosed revenue in dollars, same period basis as valuation")
    ipo_set.add_argument("--notes")
    ipo_set.set_defaults(func=cmd_ipo_set)

    ipo_comp = sub.add_parser("ipo-comp", help="log a public comparable-company multiple for an IPO thesis")
    ipo_comp.add_argument("thesis_id", type=int)
    ipo_comp.add_argument("peer_symbol")
    ipo_comp.add_argument("multiple", type=float)
    ipo_comp.add_argument("--peer-name")
    ipo_comp.add_argument("--metric", default="ev_revenue")
    ipo_comp.add_argument("--source")
    ipo_comp.set_defaults(func=cmd_ipo_comp)

    ipo_show = sub.add_parser("ipo-show", help="lockup countdown and valuation-vs-comps for an IPO thesis")
    ipo_show.add_argument("thesis_id", type=int)
    ipo_show.set_defaults(func=cmd_ipo_show)

    sz = sub.add_parser("sizing", help="confidence-driven satellite weight suggestions vs. current weights (comparison only)")
    sz.set_defaults(func=cmd_sizing)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    with db.connect() as conn:
        args.func(conn, args)


if __name__ == "__main__":
    main()
