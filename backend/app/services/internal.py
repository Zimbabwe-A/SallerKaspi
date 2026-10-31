"""Внутренняя аналитика: продажи, удержания Kaspi, прибыль, товары, остатки."""

from collections import defaultdict
from datetime import date, timedelta

from app import config, schemas
from app.data.generator import delivery_fee
from app.data.models import Dataset, Order, Product
from app.services import market


def orders_between(ds: Dataset, start: date, end: date) -> list[Order]:
    result: list[Order] = []
    day = start
    while day <= end:
        result.extend(ds.orders_by_day.get(day, ()))
        day += timedelta(days=1)
    return result


def totals(orders: list[Order]) -> schemas.Totals:
    delivered = [o for o in orders if o.status == "delivered"]
    revenue = sum(o.revenue for o in delivered)
    commission = sum(o.commission for o in orders)
    delivery = sum(o.delivery for o in orders)
    penalties = sum(o.penalty for o in orders)
    kaspi_total = commission + delivery + penalties
    cost = sum(o.cost for o in orders)
    profit = revenue - kaspi_total - cost
    tax = round(revenue * config.TAX_RATE)
    return schemas.Totals(
        orders=len(orders),
        units=sum(o.qty for o in delivered),
        cancelled=sum(1 for o in orders if o.status == "cancelled"),
        returned=sum(1 for o in orders if o.status == "returned"),
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
        avg_check=round(revenue / len(delivered)) if delivered else 0,
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
        ("penalties", "Штрафы", t.penalties),
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


def stock_row(ds: Dataset, product: Product) -> schemas.StockRow:
    state = ds.stock[product.id]
    velocity = sales_velocity(ds, product.id)
    cover = round(state.quantity / velocity, 1) if velocity > 0 else None
    return schemas.StockRow(
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        category_id=product.category_id,
        quantity=state.quantity,
        avg_daily_sales=velocity,
        days_of_cover=cover,
        status=stock_status(state.quantity, cover),
        incoming_quantity=state.incoming_quantity,
        incoming_date=state.incoming_date,
    )


def stock(ds: Dataset) -> list[schemas.StockRow]:
    order = {"out": 0, "critical": 1, "low": 2, "ok": 3}
    rows = [stock_row(ds, p) for p in ds.products.values()]
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
    for product in ds.products.values():
        t = product_totals[product.id]
        offers = market.offers(ds, product.id)
        stock_info = stock_row(ds, product)
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
        ))
    return rows


def unit_economics(ds: Dataset, product: Product, price: int) -> schemas.UnitEconomics:
    commission = round(price * ds.categories[product.category_id].commission)
    delivery = delivery_fee(price)
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
