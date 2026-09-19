import pytest

from wealth_lab import db, universe


def fake_universe():
    return [
        universe.UniverseEntry("AAA", "Alpha Co", "Tech"),
        universe.UniverseEntry("BBB", "Beta Co", "Tech"),
        universe.UniverseEntry("CCC", "Gamma Co", "Health"),
        universe.UniverseEntry("DDD", "Delta Co", "Health"),
        universe.UniverseEntry("EEE", "Epsilon Co", "Energy"),
    ]


def add_thesis(conn, symbol, status="open"):
    tid = db.add_thesis(conn, symbol=symbol, asset_type="stock", thesis="t", conviction=3)
    if status != "open":
        db.set_status(conn, tid, status)
    return tid


def test_load_universe_reads_the_real_csv():
    rows = universe.load_universe()
    assert len(rows) > 400
    symbols = [r.symbol for r in rows]
    assert len(symbols) == len(set(symbols))
    assert all(r.symbol and r.name and r.sector for r in rows)


def test_coverage_with_nothing_researched(conn):
    report = universe.coverage(conn, universe=fake_universe())
    assert report.total == 5
    assert report.researched == 0
    assert report.remaining == 5
    assert report.pct == 0.0
    assert report.by_sector["Tech"] == (0, 2)


def test_coverage_counts_researched_symbols(conn):
    add_thesis(conn, "AAA")
    add_thesis(conn, "CCC")

    report = universe.coverage(conn, universe=fake_universe())

    assert report.researched == 2
    assert report.remaining == 3
    assert report.pct == pytest.approx(40.0)
    assert report.by_sector["Tech"] == (1, 2)
    assert report.by_sector["Health"] == (1, 2)
    assert report.by_sector["Energy"] == (0, 1)


def test_coverage_counts_closed_theses_too(conn):
    # a symbol that's been researched and closed out still counts as covered -
    # scan.py's staleness check handles freshness separately
    add_thesis(conn, "AAA", status="closed_win")

    report = universe.coverage(conn, universe=fake_universe())

    assert report.researched == 1


def test_coverage_ignores_symbols_outside_the_universe(conn):
    add_thesis(conn, "ZZZ")  # not in fake_universe()

    report = universe.coverage(conn, universe=fake_universe())

    assert report.researched == 0


def test_next_batch_skips_already_researched(conn):
    add_thesis(conn, "AAA")

    batch = universe.next_batch(conn, n=5, universe=fake_universe())

    assert "AAA" not in [e.symbol for e in batch]
    assert len(batch) == 4


def test_next_batch_round_robins_across_sectors(conn):
    batch = universe.next_batch(conn, n=3, universe=fake_universe())

    sectors = [e.symbol for e in batch]
    # first pick should come from each of the first 3 sectors in sorted order
    # (Energy, Health, Tech alphabetically), one each, not two from the same
    # sector before touching a third
    assert len(set(e.sector for e in batch)) == 3
    assert sectors == ["EEE", "CCC", "AAA"]


def test_next_batch_respects_n(conn):
    batch = universe.next_batch(conn, n=2, universe=fake_universe())
    assert len(batch) == 2


def test_next_batch_empty_when_fully_covered(conn):
    for e in fake_universe():
        add_thesis(conn, e.symbol)

    batch = universe.next_batch(conn, n=5, universe=fake_universe())

    assert batch == []
