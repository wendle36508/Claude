import pytest
from fastapi.testclient import TestClient

from wealth_lab import db, portfolio


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api_test.db")
    from wealth_lab.api import app  # import after DB_PATH is patched
    return TestClient(app)


def seed_thesis(symbol="AAA", with_signal=True, with_position=False):
    with db.connect() as conn:
        tid = db.add_thesis(
            conn, symbol=symbol, asset_type="stock", thesis="test thesis",
            conviction=3, entry_price=100.0, entry_date="2026-01-01", sector="Test Sector",
        )
        if with_signal:
            db.add_signal(conn, tid, "growth", "bullish", category="growth", weight=1.0, source="http://x.test")
        if with_position:
            portfolio.allocate(conn, 1000.0, [{"thesis_id": tid, "sleeve": "satellite", "target_weight": 1.0}])
        return tid


def test_root_reports_mock_provider(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["live_data"] is False
    assert body["provider"] == "MockProvider"


def test_list_theses_empty(client):
    r = client.get("/theses")
    assert r.status_code == 200
    assert r.json() == []


def test_list_theses_returns_seeded_thesis(client):
    seed_thesis("AAA")

    r = client.get("/theses")

    assert r.status_code == 200
    assert [t["symbol"] for t in r.json()] == ["AAA"]


def test_list_theses_filters_by_status(client):
    tid = seed_thesis("AAA")
    seed_thesis("BBB")
    with db.connect() as conn:
        db.set_status(conn, tid, "closed_win")

    r = client.get("/theses", params={"status": "closed_win"})

    assert [t["symbol"] for t in r.json()] == ["AAA"]


def test_get_thesis_by_symbol(client):
    seed_thesis("AAA")

    r = client.get("/theses/AAA")

    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "AAA"
    assert body["score"]["value"] == 1.0
    assert body["sector"] == "Test Sector"


def test_get_thesis_is_case_insensitive(client):
    seed_thesis("AAA")

    r = client.get("/theses/aaa")

    assert r.status_code == 200
    assert r.json()["symbol"] == "AAA"


def test_get_thesis_404_when_unresearched(client):
    r = client.get("/theses/NOPE")

    assert r.status_code == 404
    assert "hasn't been researched" in r.json()["detail"]


def test_compare_endpoint_sorts_by_score(client):
    with db.connect() as conn:
        tid_a = db.add_thesis(conn, symbol="A", asset_type="stock", thesis="t", conviction=3)
        tid_b = db.add_thesis(conn, symbol="B", asset_type="stock", thesis="t", conviction=3)
        db.add_signal(conn, tid_a, "growth", "bearish", weight=1.0)
        db.add_signal(conn, tid_b, "growth", "bullish", weight=1.0)

    r = client.get("/compare", params={"sort": "score"})

    assert r.status_code == 200
    symbols = [row["symbol"] for row in r.json()]
    assert symbols == ["B", "A"]


def test_compare_endpoint_rejects_unknown_sort_column(client):
    r = client.get("/compare", params={"sort": "not_a_column"})

    assert r.status_code == 400


def test_portfolio_endpoint_404_when_unfunded(client):
    r = client.get("/portfolio")

    assert r.status_code == 404


def test_portfolio_endpoint_returns_totals(client):
    seed_thesis("AAA", with_position=True)

    r = client.get("/portfolio")

    assert r.status_code == 200
    assert r.json()["total_value"] == 1000.0


def test_snapshot_endpoint_matches_export_shape(client):
    seed_thesis("AAA", with_position=True)

    r = client.get("/snapshot")

    assert r.status_code == 200
    body = r.json()
    assert "generated_at" in body
    assert "portfolio" in body
    assert "theses" in body


def test_research_endpoint_503_without_live_provider(client):
    r = client.post("/research/AAPL")

    assert r.status_code == 503
    assert "MockProvider" in r.json()["detail"]
