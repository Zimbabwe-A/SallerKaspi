"""Цены конкурентов с открытых страниц товаров kaspi.kz: python -m app.kaspi.market

Это те же данные, что видит любой покупатель в блоке «Продавцы» на карточке товара.
Только чтение. Запросы редкие (пауза между товарами), без обхода каких-либо защит:
если Kaspi отвечает отказом, программа останавливается.

Результат: backend/var/shops/<магазин>/market.json
"""

import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime

import certifi

from app import config
from app.bot.storage import _write_private
from app.kaspi.sync import shop_dir

OFFERS_URL = "https://kaspi.kz/yml/offer-view/offers/{code}"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
PAUSE_SECONDS = 1.0


class MarketError(Exception):
    pass


def fetch_sellers(code: str, city_id: str) -> list[dict]:
    """Продавцы товара в городе: [{merchant_id, name, price, rating, reviews, delivery}]."""
    body = json.dumps({"cityId": city_id, "id": code, "limit": 64, "page": 0, "sortOption": "PRICE"}).encode()
    request = urllib.request.Request(OFFERS_URL.format(code=code), data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/*",
        "User-Agent": "SallerKaspi-analytics/0.1",
        "Referer": f"https://kaspi.kz/shop/p/-{code}/",
    })
    try:
        with urllib.request.urlopen(request, timeout=30, context=SSL_CONTEXT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code in (403, 429):
            raise MarketError(f"Kaspi ограничил запросы (ответ {error.code}). Остановились, попробуйте позже.") from None
        return []
    except (urllib.error.URLError, TimeoutError):
        raise MarketError("kaspi.kz не отвечает") from None
    return [parse_seller(o) for o in data.get("offers") or []]


def parse_seller(o: dict) -> dict:
    return {
        "merchant_id": str(o.get("merchantId") or ""),
        "name": str(o.get("merchantName") or ""),
        "price": int(round(float(o.get("price") or 0))),
        "rating": float(o.get("merchantRating") or 0),
        "reviews": int(o.get("merchantReviewsQuantity") or 0),
        "delivery": o.get("deliveryDuration"),
    }


def market_file(shop_id: str):
    return shop_dir(shop_id) / "market.json"


def save_market(shop_id: str, city_id: str, products: dict[str, list[dict]]) -> None:
    shop_dir(shop_id).mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {"synced_at": datetime.now().isoformat(timespec="seconds"), "city_id": city_id, "products": products}
    _write_private(market_file(shop_id), json.dumps(payload, ensure_ascii=False))
    save_daily(shop_id, products)


def history_dir(shop_id: str):
    return shop_dir(shop_id) / "market_history"


def save_daily(shop_id: str, products: dict[str, list[dict]]) -> None:
    """Снимок дня: самая низкая цена конкурента и число продавцов по товару (для индекса демпинга)."""
    from app import config
    day = datetime.now().date().isoformat()
    snapshot = {}
    for code, sellers in products.items():
        rivals = [s["price"] for s in sellers if s["merchant_id"] != config.KASPI_MERCHANT_ID and s["price"] > 0]
        snapshot[code] = {"min": min(rivals) if rivals else None, "sellers": len(sellers)}
    path = history_dir(shop_id)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    _write_private(path / f"{day}.json", json.dumps(snapshot, ensure_ascii=False))


def load_history(shop_id: str, days: int = 90) -> dict[str, dict]:
    """{дата: {код: {min, sellers}}} за последние days дней, по возрастанию даты."""
    path = history_dir(shop_id)
    if not path.exists():
        return {}
    files = sorted(path.glob("*.json"))[-days:]
    return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in files}


def load_market(shop_id: str) -> dict | None:
    path = market_file(shop_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def product_codes(shop_id: str) -> list[str]:
    """Коды карточек: из кабинета (offers.json) и из заказов."""
    from app.kaspi.cabinet import load_offers
    from app.kaspi.sync import load_cache
    codes: list[str] = []
    offers = load_offers(shop_id)
    for o in (offers or {}).get("offers", []):
        if o.get("master_sku"):
            codes.append(str(o["master_sku"]))
    for p in load_cache(shop_id).get("products", {}).values():
        if p.get("code"):
            codes.append(str(p["code"]))
    return list(dict.fromkeys(codes))


def main() -> None:
    city = config.KASPI_CITY_ID
    codes = product_codes("main")
    print(f"Смотрю продавцов по {len(codes)} товарам (город {city}), только чтение…")
    products: dict[str, list[dict]] = {}
    try:
        for n, code in enumerate(codes, start=1):
            products[code] = fetch_sellers(code, city)
            if n % 10 == 0:
                print(f"  {n} из {len(codes)}")
            time.sleep(PAUSE_SECONDS)
    except MarketError as error:
        print(f"Остановились: {error}")
    if products:
        save_market("main", city, products)
        with_rivals = sum(1 for sellers in products.values() if any(s["merchant_id"] != config.KASPI_MERCHANT_ID for s in sellers))
        print(f"Готово: {len(products)} товаров, с конкурентами {with_rivals}. Обновите страницу сайта.")


if __name__ == "__main__":
    main()
