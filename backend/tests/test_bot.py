import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.bot import storage
from app.bot.feed import FeedOffer, build_xml
from app.bot.strategy import Rule, decide


@pytest.fixture(autouse=True)
def tmp_var(tmp_path, monkeypatch):
    """Каждый тест пишет в свою временную папку, а не в настоящий backend/var."""
    monkeypatch.setattr(storage, "VAR_DIR", tmp_path)
    monkeypatch.setattr(storage, "STATE_FILE", tmp_path / "bot_state.json")
    monkeypatch.setattr(storage, "LOG_FILE", tmp_path / "bot_log.jsonl")
    monkeypatch.setattr(storage, "FEED_FILE", tmp_path / "price.xml")
    monkeypatch.setattr(storage, "SECRET_FILE", tmp_path / "feed_secret")
    monkeypatch.delenv("KASPI_FEED_SECRET", raising=False)
    from app.kaspi import sync
    monkeypatch.setattr(sync, "SHOPS_DIR", tmp_path / "shops")


# --- Логика цены ---

def test_undercuts_cheapest_by_step():
    assert decide(Rule(9_000, 12_000, 1), [10_500, 10_000, 11_000]).price == 9_999


def test_never_below_min():
    assert decide(Rule(9_000, 12_000, 1), [8_500]).price == 9_000


def test_raises_up_to_max_when_alone_or_everyone_dearer():
    assert decide(Rule(9_000, 12_000, 1), []).price == 12_000
    assert decide(Rule(9_000, 12_000, 1), [15_000]).price == 12_000


def test_raises_when_competitor_went_up():
    # Были самыми дешёвыми с запасом — поднимаемся до «конкурент минус шаг».
    assert decide(Rule(9_000, 12_000, 50), [11_000]).price == 10_950


def test_second_place():
    assert decide(Rule(9_000, 12_000, 1, "second"), [10_000, 10_400, 11_000]).price == 10_399


def test_bad_rule_rejected():
    with pytest.raises(ValueError):
        decide(Rule(10_000, 9_000, 1), [9_500])


# --- XML ---

def test_xml_is_valid_and_escaped():
    xml = build_xml("Shop & Co", "123", "PP1", [FeedOffer("EL-001", 'Кабель "USB" <2м>', "NoName", 1990, 0)])
    root = ET.fromstring(xml.encode())
    ns = {"k": "kaspiShopping"}
    offer = root.find("k:offers/k:offer", ns)
    assert offer.get("sku") == "EL-001"
    assert offer.find("k:model", ns).text == 'Кабель "USB" <2м>'
    assert offer.find("k:price", ns).text == "1990"
    assert offer.find("k:availabilities/k:availability", ns).get("available") == "no"


# --- API и защита ---

@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


JSON = {"Content-Type": "application/json", "Origin": "http://localhost:5173"}
RULE = {"enabled": True, "min_price": 1_000, "max_price": 100_000, "step": 1, "strategy": "first"}


def test_dry_run_does_not_change_prices(client):
    before = {r["product_id"]: r["price"] for r in client.get("/api/bot").json()["rows"]}
    assert client.put("/api/bot/products/1", json=RULE, headers=JSON).status_code == 200
    changes = client.post("/api/bot/run", json={}, headers=JSON).json()["changes"]
    assert changes and all(c["dry_run"] for c in changes)
    after = {r["product_id"]: r["price"] for r in client.get("/api/bot").json()["rows"]}
    assert after == before


def test_live_run_changes_price_and_feed(client):
    client.put("/api/bot/products/1", json=RULE, headers=JSON)
    client.post("/api/bot/switch", json={"enabled": False, "dry_run": False}, headers=JSON)
    change = client.post("/api/bot/run", json={}, headers=JSON).json()["changes"][0]
    row = next(r for r in client.get("/api/bot").json()["rows"] if r["product_id"] == 1)
    assert row["price"] == change["new_price"]
    assert f"<price>{change['new_price']}</price>" in storage.read_feed()


def test_foreign_site_cannot_change_anything(client):
    bad = {"Content-Type": "application/json", "Origin": "https://evil.example"}
    assert client.post("/api/bot/switch", json={"enabled": True, "dry_run": False}, headers=bad).status_code == 403
    assert client.put("/api/bot/products/1", json=RULE, headers=bad).status_code == 403
    # Простая форма (без JSON) тоже не проходит.
    form = {"Content-Type": "application/x-www-form-urlencoded"}
    assert client.post("/api/bot/switch", content="enabled=true", headers=form).status_code == 415
    assert client.get("/api/bot").json()["enabled"] is False


def test_step_is_always_one_tenge(client):
    assert client.put("/api/bot/products/1", json={**RULE, "step": 50}, headers=JSON).status_code == 422


def test_counts_and_positions(client):
    client.put("/api/bot/products/1", json=RULE, headers=JSON)
    body = client.get("/api/bot").json()
    assert body["counts"]["total"] == len(body["rows"])
    assert body["counts"]["in_bot"] == 1
    row = next(r for r in body["rows"] if r["product_id"] == 1)
    assert row["next_position"] == 1  # минимум 1000 ₸ — бот встаёт первым


def test_at_min_is_not_first():
    from app.bot.strategy import position
    d = decide(Rule(9_000, 12_000), [8_500, 9_500])
    assert d.kind == "min" and position(d.price, [8_500, 9_500]) == 2


def test_min_above_max_rejected(client):
    bad = {**RULE, "min_price": 5_000, "max_price": 4_000}
    assert client.put("/api/bot/products/1", json=bad, headers=JSON).status_code == 422


def test_status_does_not_leak_feed_secret(client):
    assert storage.feed_secret() not in client.get("/api/bot").text


def test_feed_server_needs_secret():
    from app.feed_app import app as feed
    storage.write_feed("<kaspi_catalog/>")
    with TestClient(feed) as c:
        assert c.get(f"/kaspi/{storage.feed_secret()}/price.xml").status_code == 200
        assert c.get("/kaspi/wrong/price.xml").status_code == 404
        assert c.get("/api/bot").status_code == 404
        assert c.get("/docs").status_code == 404


# --- Клиент Kaspi: безопасность ---

def test_kaspi_client_hides_token_and_stays_on_kaspi():
    from app.kaspi.client import KaspiClient, KaspiError
    client = KaspiClient(token="secret-token-123")
    assert "secret-token-123" not in repr(client)
    with pytest.raises(KaspiError) as error:
        client.get("https://evil.example/steal")
    assert "secret-token-123" not in str(error.value)


def test_kaspi_client_has_no_write_methods():
    from app.kaspi.client import KaspiClient
    assert not any(hasattr(KaspiClient, m) for m in ("post", "put", "patch", "delete"))


def test_parse_order_drops_customer_data():
    from app.kaspi.client import parse_order
    order = parse_order({"id": "1", "attributes": {
        "code": "123", "creationDate": 1_700_000_000_000, "state": "ARCHIVE", "status": "COMPLETED",
        "totalPrice": 9999.0, "deliveryCostForSeller": 699.14,
        "customer": {"firstName": "Иван", "cellPhone": "7001234567"},
        "deliveryAddress": {"town": "Алматы", "streetName": "Абая"},
    }})
    text = repr(order)
    assert "Иван" not in text and "7001234567" not in text and "Абая" not in text
    assert order.town == "Алматы" and order.total_price == 9999 and order.delivery_cost_for_seller == 699


def test_probe_hides_customer_data():
    import json
    from app.kaspi.probe import shape
    sample = {"data": [{"type": "orders", "id": "XYZ", "attributes": {
        "code": "777", "state": "ARCHIVE", "totalPrice": 5000.0,
        "customer": {"firstName": "Иван", "lastName": "Петров", "cellPhone": "7001234567"},
        "recipient": {"firstName": "Мария"},
        "deliveryAddress": {"town": "Алматы", "streetName": "Абая", "apartment": "5"},
        "comment": "позвонить Ивану 7001234567",
    }}]}
    text = json.dumps(shape(sample), ensure_ascii=False)
    for secret in ("Иван", "Петров", "7001234567", "Мария", "Абая", "XYZ"):
        assert secret not in text
    assert "Алматы" in text and "ARCHIVE" in text


# --- Закупка, цена без убытка, защита от убытка ---

def test_break_even_is_lowest_safe_price():
    from app import economics
    from app.data.store import get_dataset
    ds = get_dataset()
    p = ds.products[1]
    be = economics.break_even(ds, p, 5_000)
    assert economics.sale(ds, p, be, 5_000).profit >= 0
    assert economics.sale(ds, p, be - 1, 5_000).profit < 0


def test_bot_never_goes_below_break_even(client, monkeypatch):
    from app import economics
    pid = 1
    client.put(f"/api/bot/products/{pid}/cost", json={"cost": 9_000}, headers=JSON)
    client.put(f"/api/bot/products/{pid}", json={**RULE, "min_price": 1_000}, headers=JSON)
    row = next(r for r in client.get("/api/bot").json()["rows"] if r["product_id"] == pid)
    assert row["cost"] == 9_000
    assert row["next_price"] >= row["break_even"] > 1_000
    assert row["next_profit"] >= 0
    assert "без убытка" in row["next_reason"] or row["next_kind"] != "min"


def test_protection_can_be_turned_off(client):
    client.put("/api/bot/products/1/cost", json={"cost": 9_000}, headers=JSON)
    client.put("/api/bot/products/1", json={**RULE, "min_price": 1_000, "protect": False}, headers=JSON)
    row = next(r for r in client.get("/api/bot").json()["rows"] if r["product_id"] == 1)
    assert row["next_price"] < row["break_even"]  # без защиты бот идёт за конкурентом


def test_cost_endpoint_rejects_foreign_site(client):
    bad = {"Content-Type": "application/json", "Origin": "https://evil.example"}
    assert client.put("/api/bot/products/1/cost", json={"cost": 1}, headers=bad).status_code == 403
