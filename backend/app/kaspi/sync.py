"""Загрузка заказов из Kaspi в локальный кэш: python -m app.kaspi.sync [дней]

Только чтение. В кэш попадает только то, что нужно для аналитики: суммы, статусы, доставка,
город и товары заказа. ФИО, телефоны и адреса покупателей не сохраняются.

Кэш: backend/var/shops/<магазин>/orders.json (папка не попадает в git, права только у владельца).
Повторный запуск докачивает только новое: заказы в архиве второй раз не запрашиваются.
"""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from app.bot.storage import VAR_DIR, _write_private
from app.kaspi.client import BASE_URL, ORDER_STATES, KaspiClient, KaspiError, _int

SHOPS_DIR = VAR_DIR / "shops"
FINAL_STATES = {"ARCHIVE"}


def shop_dir(shop_id: str) -> Path:
    if not shop_id.isidentifier():
        raise ValueError("Неверный id магазина")
    return SHOPS_DIR / shop_id


def cache_file(shop_id: str) -> Path:
    return shop_dir(shop_id) / "orders.json"


def load_cache(shop_id: str) -> dict:
    path = cache_file(shop_id)
    if not path.exists():
        return {"synced_at": None, "orders": {}, "products": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(shop_id: str, cache: dict) -> None:
    """Сохранить кэш, не затирая то, что параллельно дописала другая загрузка (история + автообновление)."""
    from app.bot.storage import lock
    with lock:
        shop_dir(shop_id).mkdir(mode=0o700, parents=True, exist_ok=True)
        current = load_cache(shop_id)
        for oid, order in current.get("orders", {}).items():
            mine = cache["orders"].get(oid)
            if mine is None or (mine.get("entries") is None and order.get("entries") is not None):
                cache["orders"][oid] = order
        for mid, product in current.get("products", {}).items():
            cache["products"].setdefault(mid, product)
        cache["days"] = max(int(cache.get("days") or 0), int(current.get("days") or 0))
        cache.setdefault("since", current.get("since"))
        _write_private(cache_file(shop_id), json.dumps(cache, ensure_ascii=False))


def clean_order(item: dict) -> dict:
    """Заказ без персональных данных."""
    a = item.get("attributes", {})
    town = (a.get("deliveryAddress") or {}).get("town")
    return {
        "id": str(item["id"]),
        "code": str(a.get("code", "")),
        "created": int(a.get("creationDate") or 0),
        "state": a.get("state"),
        "status": a.get("status"),
        "total": _int(a.get("totalPrice")) or 0,
        "delivery_seller": _int(a.get("deliveryCostForSeller")),
        "delivery_mode": a.get("deliveryMode"),
        "kaspi_delivery": bool(a.get("isKaspiDelivery")),
        "express": bool((a.get("kaspiDelivery") or {}).get("express")),
        "town": town if isinstance(town, str) else None,
        "origin_city": ((a.get("originAddress") or {}).get("city") or {}).get("name"),
        # Для «Заказов к отправке»: собран ли заказ, когда передать курьеру, передан ли, есть ли накладная.
        "assembled": bool(a.get("assembled")),
        "transmission_planned": _int((a.get("kaspiDelivery") or {}).get("courierTransmissionPlanningDate")),
        "transmitted": _int((a.get("kaspiDelivery") or {}).get("courierTransmissionDate")),
        "has_waybill": bool((a.get("kaspiDelivery") or {}).get("waybillNumber") or (a.get("kaspiDelivery") or {}).get("waybill")),
        "entries": None,  # заполняется отдельным запросом
    }


def clean_entry(item: dict) -> dict:
    a = item.get("attributes", {})
    offer = a.get("offer") or {}
    category = a.get("category") or {}
    product = ((item.get("relationships") or {}).get("product") or {}).get("data") or {}
    return {
        "sku": str(offer.get("code") or ""),
        "name": str(offer.get("name") or "Без названия"),
        "master_id": product.get("id"),
        "category_code": str(category.get("code") or "other"),
        "category_title": str(category.get("title") or "Без категории"),
        "qty": int(a.get("quantity") or 0),
        "base_price": _int(a.get("basePrice")) or 0,
        "total_price": _int(a.get("totalPrice")) or 0,
        "weight": float(a.get("weight") or 0),
        "delivery_cost": _int(a.get("deliveryCost")),
    }


def sync(shop_id: str, days: int, client: KaspiClient | None = None, log=print) -> dict:
    client = client or KaspiClient()
    cache = load_cache(shop_id)
    end = date.today()
    start = end - timedelta(days=days - 1)
    log(f"Загружаю заказы за {start:%d.%m.%Y} — {end:%d.%m.%Y}…")

    fetched = 0
    for state in ORDER_STATES:
        for raw in _raw_orders(client, start, end, state):
            order = clean_order(raw)
            old = cache["orders"].get(order["id"])
            # Архивный заказ уже не меняется — товары повторно не запрашиваем.
            if old and old.get("entries") is not None and old.get("state") in FINAL_STATES:
                continue
            order["entries"] = old.get("entries") if old else None
            cache["orders"][order["id"]] = order
            fetched += 1
        log(f"  {state}: готово")

    need_entries = [o for o in cache["orders"].values() if o["entries"] is None or o["state"] not in FINAL_STATES]
    log(f"Загружаю товары по {len(need_entries)} заказам…")
    for n, order in enumerate(need_entries, start=1):
        body = client.get(f"orders/{order['id']}/entries")
        order["entries"] = [clean_entry(e) for e in body.get("data", [])]
        if n % 50 == 0:
            log(f"  {n} из {len(need_entries)}")
            save_cache(shop_id, cache)  # чтобы при обрыве не начинать заново

    # Код карточки Kaspi для каждого товара (нужен для поиска конкурентов).
    masters = {e["master_id"] for o in cache["orders"].values() for e in (o["entries"] or []) if e["master_id"]}
    missing = [m for m in masters if m not in cache["products"]]
    if missing:
        log(f"Загружаю карточки {len(missing)} товаров…")
    for master_id in missing:
        try:
            body = client.get(f"masterproducts/{master_id}")
            attrs = (body.get("data") or {}).get("attributes") or {}
            cache["products"][master_id] = {"code": str(attrs.get("code") or ""), "name": attrs.get("name")}
        except KaspiError:
            cache["products"][master_id] = {"code": "", "name": None}

    cache["synced_at"] = datetime.now().isoformat(timespec="seconds")
    cache["days"] = days
    save_cache(shop_id, cache)
    log(f"Готово: заказов в кэше {len(cache['orders'])}, обновлено {fetched}.")
    return cache


def _raw_orders(client: KaspiClient, start: date, end: date, state: str):
    """Сырые заказы (только чтобы взять нужные поля). Логику страниц берём у клиента."""
    from app.kaspi.client import CHUNK_DAYS, PAGE_SIZE, _ms
    chunk = start
    while chunk <= end:
        chunk_end = min(chunk + timedelta(days=CHUNK_DAYS - 1), end)
        page = 0
        while True:
            body = client.get("orders", {
                "page[number]": page, "page[size]": PAGE_SIZE, "filter[orders][state]": state,
                "filter[orders][creationDate][$ge]": _ms(chunk),
                "filter[orders][creationDate][$le]": _ms(chunk_end + timedelta(days=1)) - 1,
            })
            yield from body.get("data", [])
            page += 1
            if page >= int((body.get("meta") or {}).get("pageCount") or 0):
                break
        chunk = chunk_end + timedelta(days=1)


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    try:
        sync("main", days)
        print("Обновите страницу сайта и выберите ваш магазин слева.")
    except KaspiError as error:
        print(f"Не получилось: {error}")


if __name__ == "__main__":
    main()
