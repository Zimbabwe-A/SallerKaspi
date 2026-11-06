"""Строим данные сайта (Dataset) из кэша заказов Kaspi.

Что есть у Kaspi: заказы, товары в заказе, цены продажи, доставка для продавца, город.
Чего нет: комиссии (считаем по тарифу категории), остатков, цен конкурентов, себестоимости.
Себестоимость можно задать в backend/var/shops/<магазин>/costs.json: {"артикул": цена закупки}.
"""

import json
from datetime import date, datetime, timedelta

from app import config
from app.data.models import Category, Dataset, MarketDay, Order, Product, StockState
from app.kaspi.sync import load_cache, shop_dir

# Статусы Kaspi -> статусы сайта.
STATUS = {
    "COMPLETED": "delivered",
    "CANCELLED": "cancelled",
    "CANCELLING": "cancelled",
    "RETURNED": "returned",
    "KASPI_DELIVERY_RETURN_REQUESTED": "returned",
    "RETURN_ACCEPTED_BY_MERCHANT": "returned",
}
# Остальные (APPROVED_BY_BANK, ACCEPTED_BY_MERCHANT…) — заказ ещё в пути: в выручку не идёт.
IN_PROGRESS = "active"


def commission_rate(category_code: str, category_title: str) -> float:
    """Комиссия Kaspi с НДС по категории. Точная ставка задаётся в config.COMMISSION_OVERRIDES."""
    if category_code in config.COMMISSION_OVERRIDES:
        return config.COMMISSION_OVERRIDES[category_code]
    title = category_title.lower()
    if any(word in title for word in ("ювелир", "украшени", "золот", "серебр")):
        return 0.155
    return config.DEFAULT_COMMISSION


def load_costs(shop_id: str) -> dict[str, int]:
    path = shop_dir(shop_id) / "costs.json"
    if not path.exists():
        return {}
    return {str(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


def build(shop_id: str, name: str) -> Dataset:
    cache = load_cache(shop_id)
    orders_raw = [o for o in cache["orders"].values() if o.get("entries")]
    if not orders_raw:
        raise LookupError("Нет загруженных заказов. Запустите загрузку: python -m app.kaspi.sync")

    costs = load_costs(shop_id)
    end = date.today()
    days = int(cache.get("days") or 90)
    start = min(min(_day(o["created"]) for o in orders_raw), end - timedelta(days=days - 1))

    categories: dict[str, Category] = {}
    products: dict[int, Product] = {}
    pid_by_sku: dict[str, int] = {}
    sales: dict[int, list[tuple[date, int]]] = {}  # product_id -> (день, цена) для истории цен
    orders: list[Order] = []

    for raw in sorted(orders_raw, key=lambda o: o["created"]):
        day = _day(raw["created"])
        status = STATUS.get(raw.get("status") or "", IN_PROGRESS)
        entries = raw["entries"]
        order_total = sum(e["total_price"] for e in entries) or 1
        delivery_total = raw.get("delivery_seller") or 0

        for n, e in enumerate(entries):
            cid = e["category_code"]
            if cid not in categories:
                categories[cid] = Category(cid, e["category_title"], commission_rate(cid, e["category_title"]))
            sku = e["sku"] or f"{cid}:{e['name']}"
            if sku not in pid_by_sku:
                pid = len(products) + 1
                pid_by_sku[sku] = pid
                products[pid] = Product(
                    id=pid, sku=sku, name=e["name"], category_id=cid,
                    cost_price=costs.get(sku, 0), base_price=e["base_price"],
                    weight_kg=e["weight"], base_daily=0,
                    kaspi_code=(cache["products"].get(e["master_id"] or "") or {}).get("code") or None,
                )
            pid = pid_by_sku[sku]
            sales.setdefault(pid, []).append((day, e["base_price"]))

            delivered = status == "delivered"
            share = e["total_price"] / order_total
            orders.append(Order(
                id=len(orders) + 1,
                day=day,
                product_id=pid,
                qty=e["qty"],
                price=e["base_price"],
                status=status,
                city=raw.get("town") or "—",
                commission=round(e["total_price"] * categories[cid].commission) if delivered else 0,
                # Доставку Kaspi сообщает на весь заказ (уже с НДС) — делим между товарами пропорционально цене.
                # Считаем только выкупленные и возвращённые: заказ в пути — ещё не расход, отмена — не платим.
                delivery=round(delivery_total * share) if status in ("delivered", "returned") else 0,
                penalty=0,
                cost=products[pid].cost_price * e["qty"] if delivered else 0,
                order_key=raw["id"],
            ))

    # «История цен» — только наша цена продажи по дням (конкурентов Kaspi API не даёт).
    market: dict[int, list[MarketDay]] = {}
    for pid, points in sales.items():
        by_day = dict(points)
        price = points[0][1]
        history = []
        day = start
        while day <= end:
            price = by_day.get(day, price)
            history.append(MarketDay(day=day, my_price=price, competitor_prices={}, rating=0.0, reviews=0))
            day += timedelta(days=1)
        market[pid] = history

    # Остатки, текущие цены и фото — из кабинета продавца (python -m app.kaspi.cabinet), если загружены.
    from dataclasses import replace

    from app.kaspi.cabinet import load_offers
    cabinet = load_offers(shop_id)
    stock = {pid: StockState(pid, 0) for pid in products}
    stock_known = False
    if cabinet:
        by_sku = {o["sku"]: o for o in cabinet["offers"]}
        stock_known = True
        for pid, product in list(products.items()):
            offer = by_sku.get(product.sku)
            if not offer:
                continue  # товар снят с продажи — остаток 0
            stock[pid] = StockState(pid, offer["stock"] or 0)
            products[pid] = replace(product, image_url=offer.get("image"),
                                    kaspi_code=product.kaspi_code or offer.get("master_sku") or None)
            if offer.get("price") and market.get(pid):
                last = market[pid][-1]
                market[pid][-1] = MarketDay(last.day, int(offer["price"]), last.competitor_prices, last.rating, last.reviews)

    # Конкуренты — с открытых страниц товаров kaspi.kz (python -m app.kaspi.market), если загружены.
    from app.data.models import Competitor
    from app.kaspi.market import load_market
    competitors: dict[str, Competitor] = {}
    market_known = False
    snapshot = load_market(shop_id)
    if snapshot:
        market_known = True
        days = {"TODAY": 0, "TOMORROW": 1, "TILL_2_DAYS": 2, "TILL_5_DAYS": 5, "TILL_7_DAYS": 7}
        for pid, product in products.items():
            sellers = snapshot["products"].get(product.kaspi_code or "", [])
            if not sellers or not market.get(pid):
                continue
            rivals: dict[str, int] = {}
            mine = None
            for seller in sellers:
                if seller["merchant_id"] == config.KASPI_MERCHANT_ID:
                    mine = seller
                    continue
                cid = f"k{seller['merchant_id']}"
                rivals[cid] = seller["price"]
                competitors.setdefault(cid, Competitor(cid, seller["name"] or "Продавец Kaspi", seller["rating"],
                                                       days.get(seller.get("delivery") or "", 3)))
            last = market[pid][-1]
            market[pid][-1] = MarketDay(last.day, mine["price"] if mine else last.my_price, rivals,
                                        mine["rating"] if mine else last.rating, mine["reviews"] if mine else last.reviews)

    return Dataset(
        start=start, end=end, categories=categories, products=products, competitors=competitors,
        orders=orders, market=market, stock=stock,
        source="kaspi", shop_id=shop_id, name=name, stock_known=stock_known, market_known=market_known,
        synced_at=cache.get("synced_at"),
    )


def _day(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000).date()
