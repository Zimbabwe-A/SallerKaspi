"""Настоящий магазин: заказы из кэша Kaspi -> данные сайта. Без сети, на примерах ответов Kaspi."""

import time

import pytest
from fastapi.testclient import TestClient

from app import config
from app.bot import storage
from app.kaspi import sync
from app.kaspi.sync import clean_entry, clean_order

NOW_MS = int(time.time() * 1000)


def raw_order(oid, status, state="ARCHIVE", total=10_000, delivery=699.14, town="Астана", days_ago=1):
    return {"id": oid, "type": "orders", "attributes": {
        "code": f"C{oid}", "creationDate": NOW_MS - days_ago * 86_400_000, "totalPrice": total,
        "deliveryCostForSeller": delivery, "isKaspiDelivery": True, "status": status, "state": state,
        "customer": {"firstName": "Иван", "cellPhone": "7001234567"},
        "deliveryAddress": {"town": town, "streetName": "Абая"},
        "kaspiDelivery": {"express": False}, "deliveryMode": "DELIVERY_LOCAL",
    }}


def raw_entry(sku, name, qty, price, category=("Master - Brushes", "Кисти")):
    return {"type": "orderentries", "attributes": {
        "quantity": qty, "basePrice": price, "totalPrice": price * qty, "weight": 0.1,
        "category": {"code": category[0], "title": category[1]},
        "offer": {"code": sku, "name": name}, "deliveryCost": 0,
    }, "relationships": {"product": {"data": {"id": f"m{sku}", "type": "masterproducts"}}}}


@pytest.fixture
def shop(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "SHOPS_DIR", tmp_path / "shops")
    monkeypatch.setattr(storage, "VAR_DIR", tmp_path)
    monkeypatch.setattr(storage, "STATE_FILE", tmp_path / "bot_state.json")
    monkeypatch.setattr(storage, "LOG_FILE", tmp_path / "bot_log.jsonl")
    monkeypatch.setattr(storage, "FEED_FILE", tmp_path / "price.xml")
    monkeypatch.setattr(config, "KASPI_API_TOKEN", "test-token")
    orders = {}
    for raw, entries in [
        (raw_order("1", "COMPLETED"), [raw_entry("207540642", "Кисточки", 1, 10_000)]),
        (raw_order("2", "COMPLETED", total=6_000), [raw_entry("207540642", "Кисточки", 1, 4_000),
                                                     raw_entry("JEW-1", "Серьги", 1, 2_000, ("Master - Earrings", "Ювелирные украшения"))]),
        (raw_order("3", "CANCELLED", delivery=0), [raw_entry("207540642", "Кисточки", 1, 10_000)]),
        (raw_order("4", "ACCEPTED_BY_MERCHANT", state="KASPI_DELIVERY"), [raw_entry("207540642", "Кисточки", 1, 10_000)]),
    ]:
        order = clean_order(raw)
        order["entries"] = [clean_entry(e) for e in entries]
        orders[order["id"]] = order
    products = {"m207540642": {"code": "178596339", "name": "Кисточки"}}
    sync.save_cache("main", {"synced_at": "2026-11-06T18:00:00", "days": 30, "orders": orders, "products": products})


def test_cache_has_no_customer_data(shop):
    text = sync.cache_file("main").read_text(encoding="utf-8")
    for secret in ("Иван", "7001234567", "Абая"):
        assert secret not in text


def test_totals_from_real_orders(shop):
    from app.kaspi.dataset import build
    from app.services.internal import orders_between, totals
    ds = build("main", "Тест")
    t = totals(orders_between(ds, ds.start, ds.end))
    assert t.revenue == 16_000  # только выкупленные: 10 000 + 4 000 + 2 000
    assert t.cancelled == 1
    assert t.commission == round(10_000 * 0.125) + round(4_000 * 0.125) + round(2_000 * 0.155)
    # Доставка: 699 за заказ 1 + 699 заказа 2 (поделена между товарами). Заказ в пути и отмена — 0.
    assert t.delivery == 699 + 699
    assert len(ds.products) == 2
    # Заказы считаем целиком: заказ 2 с двумя товарами — один заказ.
    assert t.orders == 4 and t.cancelled == 1
    assert t.avg_check == 16_000 // 2


def test_api_for_real_shop_and_bot_is_blocked(shop):
    from app.main import app
    with TestClient(app) as c:
        shops = c.get("/api/shops").json()
        assert [s["id"] for s in shops] == ["demo", "main"] and shops[1]["ready"]
        assert c.get("/api/summary?shop=main").json()["current"]["revenue"] == 16_000
        assert c.get("/api/stock?shop=main").json()[0]["status"] == "unknown"
        assert c.get("/api/market/categories?shop=main").status_code == 200
        assert c.get("/api/market/alerts?shop=main").status_code == 200
        assert c.get("/api/bot?shop=main").status_code == 409
        headers = {"Content-Type": "application/json", "Origin": "http://localhost:5173"}
        rule = {"enabled": True, "min_price": 1, "max_price": 99_999, "step": 1, "strategy": "first"}
        assert c.put("/api/bot/products/1?shop=main", json=rule, headers=headers).status_code == 409
        assert "test-token" not in c.get("/api/shops").text
        items = {p["sku"]: p for p in c.get("/api/products?shop=main").json()["items"]}
        assert items["207540642"]["kaspi_url"] == "https://kaspi.kz/shop/p/-178596339/"
        assert items["JEW-1"]["kaspi_url"] is None
        # Остаток вручную: сохраняется у нас и виден в товарах; чужой сайт не может его менять.
        pid = items["207540642"]["id"]
        assert c.put(f"/api/bot/products/{pid}/stock?shop=main", json={"quantity": 12}, headers=headers).status_code == 200
        items = {p["sku"]: p for p in c.get("/api/products?shop=main").json()["items"]}
        assert items["207540642"]["stock_entered"] == 12
        bad = {"Content-Type": "application/json", "Origin": "https://evil.example"}
        assert c.put(f"/api/bot/products/{pid}/stock?shop=main", json={"quantity": 1}, headers=bad).status_code == 403


# --- Кабинет продавца: только чтение, без утечки пароля ---

OFFER = {
    "sku": "207540642", "masterSku": "178596339", "title": "Кисточки", "brandName": "NoName", "price": 299.0,
    "available": True, "images": ["p30/p78/76494464.jpeg"],
    "availabilities": [{"available": "yes", "storeId": "30465550_PP1", "stockCount": 37, "preOrder": 0, "stockSpecified": True}],
}


def test_cabinet_blocks_anything_but_reading(shop):
    from app.kaspi.cabinet import CabinetClient, CabinetError
    client = CabinetClient("main", email="bot@example.com", password="secret-pass")
    assert "secret-pass" not in repr(client) and "bot@example.com" not in repr(client)
    with pytest.raises(CabinetError):
        client._request("POST", "https://mc.shop.kaspi.kz/offers/api/v1/offer/price/update", {"price": 1})
    with pytest.raises(CabinetError):
        client._request("GET", "https://evil.example/steal")


def test_cabinet_logs_in_once_when_session_expired(shop, monkeypatch):
    from app import config
    from app.kaspi import cabinet
    monkeypatch.setattr(config, "KASPI_MERCHANT_ID", "30465550")
    client = cabinet.CabinetClient("main", email="bot@example.com", password="secret-pass")
    calls = []

    def fake(method, url, body=None, headers=None):
        calls.append((method, url.split("?")[0], body))
        if url.startswith(cabinet.LOGIN_URL):
            return 200, {"redirectUrl": "https://kaspi.kz/mc/"}
        if url.startswith(cabinet.OFFERS_URL):
            logged_in = any(c[1] == cabinet.LOGIN_URL for c in calls)
            return (200, {"total": 1, "data": [OFFER]}) if logged_in else (401, None)
        return 200, None

    monkeypatch.setattr(client, "_request", fake)
    offers = client.offers()
    assert [c[1] for c in calls].count(cabinet.LOGIN_URL) == 1
    assert offers[0].stock == 37 and offers[0].price == 299 and offers[0].available
    assert offers[0].image == "https://resources.cdn-kaspi.kz/img/m/p/p30/p78/76494464.jpeg"


def test_cabinet_stock_reaches_site(shop):
    from app.kaspi.cabinet import parse_offer, save_offers
    save_offers("main", [parse_offer(OFFER)])
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/source?shop=main").json()["stock_known"] is True
        items = {p["sku"]: p for p in c.get("/api/products?shop=main").json()["items"]}
        assert items["207540642"]["stock"] == 37
        assert items["207540642"]["price"] == 299
        assert items["207540642"]["image_url"].endswith("76494464.jpeg")
        assert items["JEW-1"]["stock"] == 0  # нет в кабинете — снят с продажи
    assert not any("secret" in p.name for p in sync.shop_dir("main").iterdir())


def test_real_shop_market_and_bot_test_mode_only(shop, monkeypatch):
    from app import config
    from app.bot import storage as st
    from app.kaspi.market import save_market
    monkeypatch.setattr(config, "KASPI_MERCHANT_ID", "30465550")
    save_market("main", "710000000", {"178596339": [
        {"merchant_id": "111", "name": "Конкурент", "price": 249, "rating": 4.6, "reviews": 10, "delivery": "TILL_2_DAYS"},
        {"merchant_id": "30465550", "name": "Мы", "price": 299, "rating": 4.9, "reviews": 39, "delivery": "TOMORROW"},
    ]})
    from app.main import app
    headers = {"Content-Type": "application/json", "Origin": "http://localhost:5173"}
    with TestClient(app) as c:
        assert c.get("/api/source?shop=main").json()["market_known"] is True
        items = {p["sku"]: p for p in c.get("/api/products?shop=main").json()["items"]}
        assert items["207540642"]["price"] == 299 and items["207540642"]["price_position"] == 2
        status = c.get("/api/bot?shop=main").json()
        assert status["dry_run"] is True
        pid = items["207540642"]["id"]
        rule = {"enabled": True, "min_price": 100, "max_price": 500, "step": 1, "strategy": "first", "protect": False}
        assert c.put(f"/api/bot/products/{pid}?shop=main", json=rule, headers=headers).status_code == 200
        # Включить смену цен на настоящем магазине нельзя.
        assert c.post("/api/bot/switch?shop=main", json={"enabled": True, "dry_run": False}, headers=headers).status_code == 409
        changes = c.post("/api/bot/run?shop=main", json={}, headers=headers).json()["changes"]
        assert changes and all(ch["dry_run"] for ch in changes) and changes[0]["new_price"] == 248
        # Настройки бота настоящего магазина — отдельно от демо, прайс-лист для Kaspi не создаётся.
        assert (sync.shop_dir("main") / "bot_state.json").exists()
        assert not st.FEED_FILE.exists() or "207540642" not in st.FEED_FILE.read_text()
