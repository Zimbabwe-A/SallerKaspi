"""Внутренняя аналитика: продажи, удержания Kaspi, прибыль, товары, остатки."""

import math
from collections import defaultdict
from datetime import date, timedelta

from app import config, schemas
from app.data.generator import delivery_fee
from app.data.models import Dataset, Order, Product
from app import economics
from app.services import market


def orders_between(ds: Dataset, start: date, end: date) -> list[Order]:
    result: list[Order] = []
    day = start
    while day <= end:
        result.extend(ds.orders_by_day.get(day, ()))
        day += timedelta(days=1)
    return result


def _order_count(orders: list[Order], status: str | None = None) -> int:
    """Число заказов (а не позиций): товары одного заказа Kaspi считаем одним заказом."""
    return len({o.order_key or o.id for o in orders if status is None or o.status == status})


def totals(orders: list[Order]) -> schemas.Totals:
    delivered = [o for o in orders if o.status == "delivered"]
    delivered_orders = _order_count(delivered)
    revenue = sum(o.revenue for o in delivered)
    commission = sum(o.commission for o in orders)
    delivery = sum(o.delivery for o in orders)
    penalties = sum(o.penalty for o in orders)
    kaspi_total = commission + delivery + penalties
    cost = sum(o.cost for o in orders)
    profit = revenue - kaspi_total - cost
    tax = round(revenue * config.TAX_RATE)
    return schemas.Totals(
        orders=_order_count(orders),
        units=sum(o.qty for o in delivered),
        cancelled=_order_count(orders, "cancelled"),
        returned=_order_count(orders, "returned"),
        revenue=revenue,
        commission=commission,
        delivery=delivery,
        penalties=penalties,
        kaspi_total=kaspi_total,
        payout=revenue - kaspi_total,
        cost=cost,
        profit=profit,
        tax=tax,
        profit_after_tax=profit - tax,
        avg_check=round(revenue / delivered_orders) if delivered_orders else 0,
        # Заказы ещё в пути: Kaspi засчитает их в выручку после выдачи покупателю.
        pending_orders=_order_count(orders, "active"),
        pending_amount=sum(o.price * o.qty for o in orders if o.status == "active"),
    )


def pct_change(current: int, previous: int) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def summary(ds: Dataset, start: date, end: date) -> schemas.Summary:
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    current = totals(orders_between(ds, start, end))
    previous = totals(orders_between(ds, prev_start, prev_end))
    keys = ["revenue", "orders", "units", "payout", "profit", "avg_check"]
    return schemas.Summary(
        period=schemas.Period(start=start, end=end),
        previous_period=schemas.Period(start=prev_start, end=prev_end),
        current=current,
        previous=previous,
        change_pct={k: pct_change(getattr(current, k), getattr(previous, k)) for k in keys},
    )


def breakdown(ds: Dataset, start: date, end: date) -> schemas.Breakdown:
    t = totals(orders_between(ds, start, end))
    parts = [
        ("commission", "Комиссия Kaspi", t.commission),
        ("delivery", "Доставка", t.delivery),
        *([("penalties", "Штрафы", t.penalties)] if t.penalties else []),
        ("cost", "Себестоимость", t.cost),
        ("tax", "Налог", t.tax),
        ("profit", "Прибыль", t.profit_after_tax),
    ]
    share = lambda amount: round(amount / t.revenue * 100, 1) if t.revenue else 0.0
    return schemas.Breakdown(
        period=schemas.Period(start=start, end=end),
        revenue=t.revenue,
        items=[schemas.BreakdownItem(key=k, label=label, amount=a, share=share(a)) for k, label, a in parts],
    )


def daily(ds: Dataset, start: date, end: date, product_id: int | None = None) -> list[schemas.DailyPoint]:
    points: list[schemas.DailyPoint] = []
    day = start
    while day <= end:
        orders = ds.orders_by_day.get(day, [])
        if product_id is not None:
            orders = [o for o in orders if o.product_id == product_id]
        t = totals(orders)
        points.append(schemas.DailyPoint(date=day, orders=t.orders, units=t.units,
                                         revenue=t.revenue, payout=t.payout, profit=t.profit))
        day += timedelta(days=1)
    return points


def sales_velocity(ds: Dataset, product_id: int) -> float:
    start = ds.end - timedelta(days=config.SALES_VELOCITY_DAYS - 1)
    units = sum(o.qty for o in orders_between(ds, start, ds.end)
                if o.product_id == product_id and o.status == "delivered")
    return round(units / config.SALES_VELOCITY_DAYS, 2)


def stock_status(quantity: int, days_of_cover: float | None) -> str:
    if quantity <= 0:
        return "out"
    if days_of_cover is None:
        return "ok"
    if days_of_cover < 7:
        return "critical"
    if days_of_cover < 14:
        return "low"
    return "ok"


IDLE_DAYS = 30  # столько дней без продаж — товар «лежит»
REORDER_DAYS = 30  # дозаказ — чтобы хватило на месяц


def last_sale_days(ds: Dataset) -> dict[int, int]:
    """Сколько дней назад была последняя продажа каждого товара."""
    last: dict[int, date] = {}
    for o in ds.orders:
        if o.status in ("delivered", "active") and o.day > last.get(o.product_id, date.min):
            last[o.product_id] = o.day
    return {pid: (ds.end - day).days for pid, day in last.items()}


def stock_row(ds: Dataset, product: Product, idle: dict[int, int] | None = None) -> schemas.StockRow:
    state = ds.stock[product.id]
    velocity = sales_velocity(ds, product.id)
    quantity = economics.stock_of(ds, product)  # из кабинета Kaspi или вписанный вручную
    cost = economics.cost_of(ds, product)
    if quantity is None:
        return schemas.StockRow(
            product_id=product.id, sku=product.sku, name=product.name, category_id=product.category_id,
            quantity=0, avg_daily_sales=velocity, days_of_cover=None, status="unknown",
            incoming_quantity=0, incoming_date=None, cost=cost,
        )
    idle = last_sale_days(ds) if idle is None else idle
    cover = round(quantity / velocity, 1) if velocity > 0 else None
    incoming = state.incoming_quantity if ds.stock_known else 0
    return schemas.StockRow(
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        category_id=product.category_id,
        quantity=quantity,
        avg_daily_sales=velocity,
        days_of_cover=cover,
        status=stock_status(quantity, cover),
        incoming_quantity=incoming,
        incoming_date=state.incoming_date if ds.stock_known else None,
        idle_days=(idle.get(product.id, (ds.end - ds.start).days) if quantity > 0 else None),
        cost=cost,
        frozen=quantity * cost if cost is not None and quantity > 0 else None,
        reorder=max(0, math.ceil(velocity * REORDER_DAYS - quantity - incoming)) if velocity > 0 else 0,
    )


def stock(ds: Dataset) -> list[schemas.StockRow]:
    order = {"out": 0, "critical": 1, "low": 2, "ok": 3, "unknown": 4}
    idle = last_sale_days(ds)
    rows = [stock_row(ds, p, idle) for p in ds.products.values()]
    return sorted(rows, key=lambda r: (order[r.status], r.days_of_cover if r.days_of_cover is not None else 1e9))


def abc_classes(revenue_by_product: dict[int, int]) -> dict[int, str]:
    total = sum(revenue_by_product.values())
    classes: dict[int, str] = {}
    running = 0
    for pid, revenue in sorted(revenue_by_product.items(), key=lambda kv: kv[1], reverse=True):
        if revenue <= 0:
            continue
        running += revenue
        share = running / total
        classes[pid] = "A" if share <= 0.8 or not classes else "B" if share <= 0.95 else "C"
    return classes


def product_rows(ds: Dataset, start: date, end: date) -> list[schemas.ProductRow]:
    by_product: dict[int, list[Order]] = defaultdict(list)
    for o in orders_between(ds, start, end):
        by_product[o.product_id].append(o)
    product_totals = {pid: totals(by_product.get(pid, [])) for pid in ds.products}
    abc = abc_classes({pid: t.revenue for pid, t in product_totals.items()})

    rows: list[schemas.ProductRow] = []
    idle = last_sale_days(ds)
    for product in ds.products.values():
        t = product_totals[product.id]
        offers = market.offers(ds, product.id)
        stock_info = stock_row(ds, product, idle)
        last = ds.market[product.id][-1]
        rows.append(schemas.ProductRow(
            id=product.id,
            sku=product.sku,
            name=product.name,
            category_id=product.category_id,
            category_name=ds.categories[product.category_id].name,
            price=offers.my_price,
            min_market_price=offers.min_price,
            price_position=offers.my_position,
            sellers=offers.sellers,
            units=t.units,
            revenue=t.revenue,
            kaspi_fees=t.kaspi_total,
            cost=t.cost,
            profit=t.profit,
            margin_pct=round(t.profit / t.revenue * 100, 1) if t.revenue else None,
            abc=abc.get(product.id),
            stock=stock_info.quantity,
            days_of_cover=stock_info.days_of_cover,
            stock_status=stock_info.status,
            rating=last.rating,
            reviews=last.reviews,
            kaspi_url=f"https://kaspi.kz/shop/p/-{product.kaspi_code}/" if product.kaspi_code else None,
            cost_price=economics.cost_of(ds, product),
            image_url=product.image_url,
            stock_entered=None if ds.stock_known else economics.load_stock(ds.shop_id).get(product.sku),
        ))
    return rows


def unit_economics(ds: Dataset, product: Product, price: int) -> schemas.UnitEconomics:
    commission = round(price * ds.categories[product.category_id].commission)
    # Одна штука, направление «по Казахстану» (большинство заказов не из города продавца).
    delivery = delivery_fee(price, product.weight_kg)
    tax = round(price * config.TAX_RATE)
    profit = price - commission - delivery - product.cost_price - tax
    return schemas.UnitEconomics(
        price=price,
        commission=commission,
        delivery=delivery,
        cost=product.cost_price,
        tax=tax,
        profit=profit,
        margin_pct=round(profit / price * 100, 1),
    )


def product_detail(ds: Dataset, product_id: int, start: date, end: date) -> schemas.ProductDetail:
    product = ds.products[product_id]
    row = next(r for r in product_rows(ds, start, end) if r.id == product_id)
    return schemas.ProductDetail(
        period=schemas.Period(start=start, end=end),
        product=row,
        cost_price=product.cost_price,
        commission_rate=ds.categories[product.category_id].commission,
        unit_economics=unit_economics(ds, product, row.price),
        daily=daily(ds, start, end, product_id),
    )
