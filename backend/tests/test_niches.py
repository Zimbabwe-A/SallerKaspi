import pytest
from fastapi.testclient import TestClient

from app import config, schemas, tariffs
from app.main import app
from app.services import calculator

BASE = {"purchase_cost": 6000, "other_cost": 500, "price": 15000}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


def econ(**overrides):
    return schemas.EconomicsInput(**{**BASE, **overrides})


@pytest.mark.parametrize(
    ("price", "delivery_type", "weight", "base"),
    [
        (999, "city", "to_5", 49),
        (1000, "city", "to_5", 149),
        (4999, "express", "to_5", 199),
        (5000, "city", "to_5", 699),
        (9999, "kazakhstan", "over_100", 799),
        (10000, "city", "to_5", 1099),
        (10000, "kazakhstan", "to_30", 3599),
        (50000, "express", "over_100", 8449),
    ],
)
def test_delivery_fee_includes_vat(price, delivery_type, weight, base):
    assert tariffs.delivery_fee(price, delivery_type, weight) == round(base * 1.16)


def test_calculator_adds_up(client):
    r = client.post("/api/calculator", json=BASE).json()
    assert r["commission"] == 1875 and r["tax"] == 600 and r["delivery"] == 1275 and r["cost"] == 6500
    assert r["profit"] == 15000 - 1875 - 600 - 1275 - 6500
    assert r["margin_pct"] == 31.7
    assert r["roi_pct"] == 73.1


@pytest.mark.parametrize("purchase", [0, 300, 1500, 3800, 4200, 6500, 60000])
@pytest.mark.parametrize("margin", [0, 15])
def test_price_for_margin_is_minimal(purchase, margin):
    data = econ(purchase_cost=purchase, other_cost=0, target_margin_pct=margin)
    price = calculator.price_for_margin(data, margin)
    at = calculator.calculate(data.model_copy(update={"price": price}))
    # Округление комиссии и налога до тенге может сдвинуть результат на пару тенге.
    assert at.profit >= price * margin / 100 - 2
    if price > 1:
        below = calculator.calculate(data.model_copy(update={"price": price - 2}))
        assert below.profit < (price - 2) * margin / 100 + 2


def test_unreachable_margin():
    assert calculator.price_for_margin(econ(commission_pct=50, tax_pct=50), 15) is None


def test_validation(client):
    assert client.post("/api/calculator", json={**BASE, "price": 0}).status_code == 422
    assert client.post("/api/candidates", json={**BASE, "name": ""}).status_code == 422


def test_candidates_crud_and_ranking(client):
    good = {**BASE, "name": "Хороший", "sellers": 3, "reviews": 400, "min_price": 15000}
    bad = {**BASE, "name": "Убыточный", "purchase_cost": 14000, "sellers": 30}
    created = client.post("/api/candidates", json=bad)
    assert created.status_code == 201
    bad_id = created.json()["id"]
    good_id = client.post("/api/candidates", json=good).json()["id"]

    items = client.get("/api/candidates").json()
    assert [c["id"] for c in items] == [good_id, bad_id]
    assert items[0]["verdict"] == "good"
    assert items[1]["verdict"] == "reject"
    parts = items[0]["score_parts"]
    assert items[0]["score"] - sum(parts.values()) in (-1, 0, 1)

    updated = client.put(f"/api/candidates/{bad_id}", json={**bad, "purchase_cost": 5000}).json()
    assert updated["verdict"] != "reject"
    assert client.delete(f"/api/candidates/{bad_id}").status_code == 204
    assert client.delete(f"/api/candidates/{bad_id}").status_code == 404
    assert client.put(f"/api/candidates/{bad_id}", json=bad).status_code == 404


def test_min_price_warnings(client):
    body = {**BASE, "name": "Дорогой", "reviews": 100, "min_price": 8000}
    c = client.post("/api/candidates", json=body).json()
    assert c["profit_at_min_price"] < 0
    assert c["verdict"] != "good"
    assert any("убыточен" in w for w in c["warnings"])
    assert "Ваша цена выше минимальной на 87,5%" in c["warnings"]
    round_gap = client.post("/api/candidates", json={**body, "min_price": 12000}).json()
    assert "Ваша цена выше минимальной на 25%" in round_gap["warnings"]


def test_tariffs_endpoint(client):
    body = client.get("/api/tariffs").json()
    assert [p["pct"] for p in body["commission_presets"]] == [12.5, 15.5, 7.3]
    assert len(body["delivery_types"]) == 3 and len(body["weight_tiers"]) == 6
