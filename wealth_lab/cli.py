"""Command-line interface for the research tracker.

    python -m wealth_lab add AAPL stock "thesis text" --conviction 4 --entry-price 230
    python -m wealth_lab signal 1 insider_buying bullish --rationale "CEO bought $2M"
    python -m wealth_lab snapshot 1 245.10 --note "post-earnings pop"
    python -m wealth_lab close 1 closed_win
    python -m wealth_lab show 1
    python -m wealth_lab list --status open
    python -m wealth_lab report
"""

from __future__ import annotations

import argparse
import sys

from wealth_lab import db, portfolio, report


def cmd_add(conn, args) -> None:
    thesis_id = db.add_thesis(
        conn,
        symbol=args.symbol,
        asset_type=args.asset_type,
        thesis=args.thesis,
        conviction=args.conviction,
        name=args.name,
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
        rationale=args.rationale,
        weight=args.weight,
        source=args.source,
    )
    print(f"added signal #{sig_id} ({args.name}: {args.direction}) to thesis #{args.thesis_id}")


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
        print(f"  {t['name']}")
    print(f"  thesis: {t['thesis']}")
    if t["entry_price"] is not None:
        print(f"  entry: {t['entry_price']} on {t['entry_date'] or '?'}"
              + (f", target {t['target_price']}" if t["target_price"] else ""))
    signals = db.list_signals(conn, args.thesis_id)
    if signals:
        print("  signals:")
        for s in signals:
            print(f"    - {s['name']}: {s['direction']} (w={s['weight']}) {s['rationale'] or ''}")
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wealth_lab")
    sub = p.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="log a new thesis")
    add.add_argument("symbol")
    add.add_argument("asset_type", choices=["stock", "ipo"])
    add.add_argument("thesis")
    add.add_argument("--conviction", type=int, required=True, choices=range(1, 6))
    add.add_argument("--name")
    add.add_argument("--entry-price", type=float)
    add.add_argument("--entry-date")
    add.add_argument("--target-price", type=float)
    add.add_argument("--horizon-days", type=int)
    add.set_defaults(func=cmd_add)

    sig = sub.add_parser("signal", help="attach a signal to a thesis")
    sig.add_argument("thesis_id", type=int)
    sig.add_argument("name")
    sig.add_argument("direction", choices=["bullish", "bearish", "neutral"])
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

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    with db.connect() as conn:
        args.func(conn, args)


if __name__ == "__main__":
    main()
