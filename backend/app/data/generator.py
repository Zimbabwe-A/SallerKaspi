"""Генератор правдоподобных тестовых данных магазина на Kaspi.

Один и тот же SEED даёт одни и те же данные (даты сдвигаются к сегодняшнему дню).
"""

import math
import random
from datetime import date, timedelta

from app import config
from app.data.catalog import CATALOG, SKU_PREFIX
from app.data.models import (
    Category,
    Competitor,
    Dataset,
    MarketDay,
    Order,
    Product,
    StockState,
)


def round_price(value: float) -> int:
    return max(10, int(round(value / 10)) * 10)


def delivery_fee(price: int) -> int:
    for limit, fee in config.DELIVERY_TIERS:
        if limit is None or price <= limit:
            return fee
    raise ValueError("DELIVERY_TIERS must end with a tier without limit")


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    threshold, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= threshold:
            return k
        k += 1


def demand_factor(day: date, index: int, my_price: int, min_competitor: int) -> float:
    weekday = {4: 1.1, 5: 1.25, 6: 1.2}.get(day.weekday(), 1.0)
    season = 1 + 0.2 * math.sin(2 * math.pi * index / 60) + 0.002 * index
    ratio = my_price / min_competitor
    price = 1.3 if ratio <= 1 else max(0.15, 1 - (ratio - 1) * 4)
    return weekday * season * price


def build_categories() -> dict[str, Category]:
    return {
        cid: Category(id=cid, name=c["name"], commission=c["commission"])
        for cid, c in config.CATEGORIES.items()
    }


def build_products(rng: random.Random) -> dict[int, Product]:
    products: dict[int, Product] = {}
    for category_id, items in CATALOG.items():
        for n, (name, low, high) in enumerate(items, start=1):
            pid = len(products) + 1
            base_price = round_price(rng.uniform(low, high))
            products[pid] = Product(
                id=pid,
                sku=f"{SKU_PREFIX[category_id]}-{n:03d}",
                name=name,
                category_id=category_id,
                cost_price=round_price(base_price * rng.uniform(0.5, 0.72)),
                base_price=base_price,
                base_daily=min(8.0, max(0.2, rng.lognormvariate(0, 0.8))),
            )
    return products


def build_competitors(rng: random.Random) -> dict[str, Competitor]:
    return {
        f"c{i}": Competitor(
            id=f"c{i}",
            name=name,
            rating=round(rng.uniform(4.0, 5.0), 1),
            delivery_days=rng.randint(1, 4),
        )
        for i, name in enumerate(config.COMPETITOR_NAMES, start=1)
    }


def generate(seed: int = config.SEED, days: int = config.HISTORY_DAYS, end: date | None = None) -> Dataset:
    rng = random.Random(seed)
    end = end or date.today()
    start = end - timedelta(days=days - 1)

    categories = build_categories()
    products = build_products(rng)
    competitors = build_competitors(rng)
    competitor_ids = list(competitors)

    raw_orders: list[tuple] = []
    market: dict[int, list[MarketDay]] = {}
    stock: dict[int, StockState] = {}

    for product in products.values():
        commission_rate = categories[product.category_id].commission
        sellers = rng.sample(competitor_ids, rng.randint(3, 8))
        prices = {s: round_price(product.base_price * rng.uniform(0.92, 1.12)) for s in sellers}
        my_price = product.base_price
        rating = rng.uniform(4.2, 4.9)
        reviews = rng.randint(5, 300)
        quantity = int(product.base_daily * rng.uniform(25, 50)) + 5
        incoming: tuple[date, int] | None = None
        # Часть товаров перестаёт пополняться в конце периода — чтобы в остатках были «горящие» позиции.
        stops_restock = rng.random() < 0.15
        history: list[MarketDay] = []

        for i in range(days):
            day = start + timedelta(days=i)

            for s in sellers:
                if rng.random() < 0.12:
                    moved = prices[s] * rng.uniform(0.94, 1.05)
                    prices[s] = round_price(min(max(moved, product.base_price * 0.75), product.base_price * 1.3))
            if rng.random() < 0.04:
                moved = my_price * rng.uniform(0.95, 1.05)
                my_price = round_price(min(max(moved, product.base_price * 0.85), product.base_price * 1.2))

            if incoming and day >= incoming[0]:
                quantity += incoming[1]
                incoming = None

            lam = product.base_daily * demand_factor(day, i, my_price, min(prices.values()))
            for _ in range(poisson(rng, lam)):
                if quantity <= 0:
                    break
                qty = 2 if rng.random() < 0.1 and quantity >= 2 else 1
                roll = rng.random()
                if roll < config.CANCEL_RATE:
                    status = "cancelled"
                elif roll < config.CANCEL_RATE + config.RETURN_RATE:
                    status = "returned"
                else:
                    status = "delivered"
                    quantity -= qty
                    if rng.random() < 0.08:
                        score = rng.choices([5, 4, 3, 2, 1], weights=[70, 18, 6, 3, 3])[0]
                        rating = (rating * reviews + score) / (reviews + 1)
                        reviews += 1
                raw_orders.append((day, product, qty, my_price, status, rng.choice(config.CITIES),
                                   commission_rate, rng.random()))

            reorder_point = product.base_daily * 12
            if incoming is None and quantity < reorder_point and not (stops_restock and i > days - 40):
                incoming = (day + timedelta(days=rng.randint(5, 12)),
                            int(product.base_daily * rng.uniform(30, 60)) + 5)

            history.append(MarketDay(day=day, my_price=my_price, competitor_prices=dict(prices),
                                     rating=round(rating, 2), reviews=reviews))

        market[product.id] = history
        stock[product.id] = StockState(
            product_id=product.id,
            quantity=quantity,
            incoming_quantity=incoming[1] if incoming else 0,
            incoming_date=incoming[0] if incoming else None,
        )

    raw_orders.sort(key=lambda o: (o[0], o[1].id))
    orders: list[Order] = []
    for oid, (day, product, qty, price, status, city, commission_rate, penalty_roll) in enumerate(raw_orders, start=1):
        delivered = status == "delivered"
        penalty = 0
        if status != "cancelled" and penalty_roll < config.PENALTY_PROBABILITY:
            penalty = config.PENALTY_AMOUNTS[oid % len(config.PENALTY_AMOUNTS)]
        orders.append(Order(
            id=oid,
            day=day,
            product_id=product.id,
            qty=qty,
            price=price,
            status=status,
            city=city,
            commission=round(price * qty * commission_rate) if delivered else 0,
            # Доставку платим и за выкупленный, и за возвращённый заказ.
            delivery=delivery_fee(price) if status != "cancelled" else 0,
            penalty=penalty,
            cost=product.cost_price * qty if delivered else 0,
        ))

    return Dataset(
        start=start,
        end=end,
        categories=categories,
        products=products,
        competitors=competitors,
        orders=orders,
        market=market,
        stock=stock,
    )
