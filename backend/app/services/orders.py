"""Заказы к отправке: что собрать и передать курьеру Kaspi.

Настоящий магазин — из кэша заказов Kaspi API (var/shops/<магазин>/orders.json, без данных покупателей).
Демо — из тестовых заказов «в пути».
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

from app.data.models import Dataset

RECENT_DAYS = 14  # старше — скорее всего уже ушёл в архив, просто кэш не обновился
# Kaspi Доставка: заказ принят продавцом и ещё не передан курьеру — его нужно собрать и отдать.
TO_SHIP = {("KASPI_DELIVERY", "ACCEPTED_BY_MERCHANT")}
CANCELLING = {"CANCELLING"}


def _day(ms: int | None) -> str | None:
    return datetime.fromtimestamp(ms / 1000).date().isoformat() if ms else None


def _real(ds: Dataset) -> list[dict]:
    from app.kaspi.sync import load_cache  # только для настоящего магазина

    since = datetime.now() - timedelta(days=RECENT_DAYS)
    result = []
    for o in load_cache(ds.shop_id).get("orders", {}).values():
        created = datetime.fromtimestamp((o.get("created") or 0) / 1000)
        if created < since or o.get("state") != "KASPI_DELIVERY":
            continue
        cancelling = o.get("status") in CANCELLING
        if (o.get("state"), o.get("status")) not in TO_SHIP and not cancelling:
            continue
        if o.get("transmitted"):
            continue  # уже у курьера
        result.append({
            "code": o.get("code", ""),
            "created": created.isoformat(timespec="minutes"),
            "town": o.get("town"),
            "express": bool(o.get("express")),
            "assembled": bool(o.get("assembled")),
            "ship_by": _day(o.get("transmission_planned")),
            "has_waybill": bool(o.get("has_waybill")),
            "cancelling": cancelling,
            "total": o.get("total") or 0,
            "items": [{"sku": e.get("sku", ""), "name": e.get("name", ""), "qty": e.get("qty", 0)}
                      for e in (o.get("entries") or [])],
        })
    return result


def _demo(ds: Dataset) -> list[dict]:
    groups: dict[str, list] = defaultdict(list)
    # В тестовых данных нет заказов «в пути» — для примера берём сегодняшние заказы, кроме отменённых.
    for o in ds.orders:
        if o.status != "cancelled" and o.day == ds.end:
            groups[o.order_key or str(o.id)].append(o)
    result = []
    for key, items in groups.items():
        first = items[0]
        result.append({
            "code": key,
            "created": datetime.combine(first.day, datetime.min.time()).isoformat(timespec="minutes"),
            "town": first.city,
            "express": False,
            "ship_by": first.day.isoformat() if len(result) % 3 else (first.day + timedelta(days=1)).isoformat(),
            "assembled": len(result) % 4 == 1,
            "has_waybill": True,
            "cancelling": False,
            "total": sum(o.price * o.qty for o in items),
            "items": [{"sku": ds.products[o.product_id].sku, "name": ds.products[o.product_id].name, "qty": o.qty}
                      for o in items],
        })
    return result


def to_ship(ds: Dataset) -> dict:
    orders = _demo(ds) if ds.source == "test" else _real(ds)
    orders.sort(key=lambda o: (o["cancelling"], o["ship_by"] or "9999", o["created"]))
    active = [o for o in orders if not o["cancelling"]]
    pick: dict[str, dict] = {}
    for o in active:
        for item in o["items"]:
            row = pick.setdefault(item["sku"], {"sku": item["sku"], "name": item["name"], "qty": 0, "orders": 0})
            row["qty"] += item["qty"]
            row["orders"] += 1
    today = date.today().isoformat()
    return {
        "orders": orders,
        "pick_list": sorted(pick.values(), key=lambda r: (-r["qty"], r["name"])),
        "count": len(active),
        "due_today": sum(1 for o in active if o["ship_by"] and o["ship_by"] <= today),
        "not_assembled": sum(1 for o in active if not o["assembled"]),
        "cancelling": len(orders) - len(active),
        "dates_known": any(o["ship_by"] for o in active),
    }
