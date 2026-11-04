"""The demo shop's HTTP API (demo_repo/tinyshop/api.py), including its planted bug."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(DEMO))
    for name in [m for m in sys.modules if m == "tinyshop" or m.startswith("tinyshop.")]:
        monkeypatch.delitem(sys.modules, name)
    from tinyshop.api import create_app

    return TestClient(create_app(tmp_path / "shop.db"))


def test_order_lowers_the_stock_and_shows_in_the_report(client):
    pid = client.post("/products", json={"name": "Tea", "price": 2.5, "stock": 5}).json()["id"]
    assert client.post("/orders", json={"product_id": pid, "qty": 2, "day": "2026-11-04"}).status_code == 201
    assert client.get("/products", params={"name": "Tea"}).json()[0]["stock"] == 3
    assert "Tea: 2 x 2.50" in client.get("/reports/2026-11-04").json()["report"]


def test_unknown_product_is_404(client):
    assert client.post("/orders", json={"product_id": 999, "qty": 1, "day": "2026-11-04"}).status_code == 404


def test_oversell_is_the_planted_bug(client):
    # bug-oversell in security/demo_repo_flaws.json: the docstring promises 409, the code accepts it
    pid = client.post("/products", json={"name": "Tea", "price": 2.5, "stock": 1}).json()["id"]
    assert client.post("/orders", json={"product_id": pid, "qty": 5, "day": "2026-11-04"}).status_code == 201
