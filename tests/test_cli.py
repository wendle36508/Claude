import pytest

from wealth_lab import cli, db


def _signal(conn, *extra):
    tid = db.add_thesis(conn, symbol="AAA", asset_type="stock", thesis="t", conviction=3)
    args = cli.build_parser().parse_args(["signal", str(tid), "eps_beat", "bullish", *extra])
    args.func(conn, args)
    return db.list_signals(conn, tid)[0]["weight"]


@pytest.mark.parametrize("tier,weight", [("hard", 1.5), ("standard", 1.0), ("soft", 0.5)])
def test_signal_strength_sets_tier_weight(conn, tier, weight):
    assert _signal(conn, "--strength", tier) == weight


def test_signal_defaults_to_standard_weight(conn):
    assert _signal(conn) == 1.0


def test_signal_explicit_weight_still_works(conn):
    assert _signal(conn, "--weight", "2.0") == 2.0


def test_signal_rejects_strength_and_weight_together():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["signal", "1", "x", "bullish", "--strength", "hard", "--weight", "2"])
