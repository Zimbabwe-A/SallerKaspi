from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.data.store import get_dataset
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["products"] > 40
    assert body["orders"] > 1000


def test_summary_adds_up(client):
    t = client.get("/api/summary").json()["current"]
    assert t["kaspi_total"] == t["commission"] + t["delivery"] + t["penalties"]
    assert t["payout"] == t["revenue"] - t["kaspi_total"]
    assert t["profit"] == t["payout"] - t["cost"]
    assert t["profit_after_tax"] == t["profit"] - t["tax"]


def test_breakdown_sums_to_revenue(client):
    body = client.get("/api/breakdown").json()
    assert sum(i["amount"] for i in body["items"]) == body["revenue"]


def test_daily_matches_summary(client):
    ds = get_dataset()
    params = {"from": str(ds.end - timedelta(days=29)), "to": str(ds.end)}
    days = client.get("/api/sales/daily", params=params).json()
    summary = client.get("/api/summary", params=params).json()["current"]
    assert len(days) == 30
    assert sum(d["revenue"] for d in days) == summary["revenue"]
    assert sum(d["profit"] for d in days) == summary["profit"]


def test_products_match_summary(client):
    summary = client.get("/api/summary").json()["current"]
    products = client.get("/api/products").json()
    assert products["total"] == len(get_dataset().products)
    assert sum(p["revenue"] for p in products["items"]) == summary["revenue"]
    revenues = [p["revenue"] for p in products["items"]]
    assert revenues == sorted(revenues, reverse=True)


def test_products_filters(client):
    items = client.get("/api/products", params={"category": "sport", "sort": "name", "order": "asc"}).json()["items"]
    assert items and all(p["category_id"] == "sport" for p in items)
    assert [p["name"] for p in items] == sorted(p["name"] for p in items)


def test_product_detail_and_404(client):
    body = client.get("/api/products/1").json()
    assert body["product"]["id"] == 1
    assert len(body["daily"]) == 7
    assert client.get("/api/products/9999").status_code == 404


def test_bad_period(client):
    assert client.get("/api/summary", params={"from": "2026-10-10", "to": "2026-10-01"}).status_code == 400


def test_offers(client):
    body = client.get("/api/market/products/1/offers").json()
    me = [o for o in body["offers"] if o["is_me"]]
    assert len(me) == 1 and me[0]["position"] == body["my_position"]
    prices = [o["price"] for o in body["offers"]]
    assert prices == sorted(prices) and body["min_price"] == prices[0]


def test_history_and_market(client):
    history = client.get("/api/market/products/1/history").json()
    assert all(p["min_price"] <= p["my_price"] <= p["max_price"] for p in history["points"])
    categories = client.get("/api/market/categories").json()
    assert len(categories) == len(get_dataset().categories)


def test_alerts_and_stock(client):
    assert isinstance(client.get("/api/market/alerts").json(), list)
    stock = client.get("/api/stock").json()
    assert len(stock) == len(get_dataset().products)
    assert any(s["status"] != "ok" for s in stock)
