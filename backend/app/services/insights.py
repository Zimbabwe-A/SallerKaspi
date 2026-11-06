"""Аналитика для закупа: умный заказ, упущенная выручка, ABC/XYZ, риски (монополия, демпинг).

Всё считается по вашим данным: заказы Kaspi, остатки из кабинета, цены продавцов на карточках.
"""

import math
from datetime import timedelta
from statistics import mean, pstdev

from pydantic import BaseModel

from app import config, economics
from app.data.models import Dataset
from app.kaspi.market import load_history, load_market
from app.services import market

LEAD_DAYS = 7  # сколько дней обычно идёт поставка
COVER_DAYS = 30  # на сколько дней продаж закупать
BIG_SELLER_REVIEWS = 5_000  # продавец с таким числом отзывов — «крупный», ценой его не перебить
CROWDED_SELLERS = 10  # столько продавцов на карточке — тесно


class ReorderRow(BaseModel):
    product_id: int
    name: str
    sku: str
    stock: int | None
    per_day: float  # продаётся штук в день (за 14 дней)
    days_left: float | None  # на сколько дней хватит
    order_qty: int  # сколько заказать
    status: str  # out | urgent | soon | ok | no_sales
    message: str


class LostRow(BaseModel):
    product_id: int
    name: str
    per_day: float
    price: int
    lost_per_day: int  # теряете ₸ в день


class AbcRow(BaseModel):
    product_id: int
    name: str
    abc: str | None  # A / B / C по прибыли (или выручке, если закупка не указана)
    xyz: str | None  # X стабильно / Y колеблется / Z случайно
    amount: int  # прибыль или выручка за 90 дней
    advice: str


class RiskRow(BaseModel):
    product_id: int
    name: str
    sellers: int
    big_sellers: list[str]
    monopoly: bool
    price_drop_pct: float | None  # на сколько % упала самая низкая цена конкурента за период истории
    history_days: int
    advice: str


class Insights(BaseModel):
    based_on: str  # по прибыли или по выручке
    reorder: list[ReorderRow]
    lost_total_per_day: int
    lost: list[LostRow]
    abc: list[AbcRow]
    risks: list[RiskRow]


def _units_by_day(ds: Dataset, start, end) -> dict[int, dict]:
    result: dict[int, dict] = {}
    day = start
    while day <= end:
        for o in ds.orders_by_day.get(day, ()):
            if o.status == "delivered":
                result.setdefault(o.product_id, {})
                result[o.product_id][day] = result[o.product_id].get(day, 0) + o.qty
        day += timedelta(days=1)
    return result


def insights(ds: Dataset) -> Insights:
    end = ds.end
    window = config.SALES_VELOCITY_DAYS
    recent = _units_by_day(ds, end - timedelta(days=window - 1), end)
    year = _units_by_day(ds, max(ds.start, end - timedelta(days=89)), end)

    reorder, lost = [], []
    for p in ds.products.values():
        per_day = round(sum(recent.get(p.id, {}).values()) / window, 2)
        stock = economics.stock_of(ds, p)
        if per_day == 0:
            status, days_left, qty = "no_sales", None, 0
            msg = "Продаж за 2 недели нет — заказывать не нужно."
        elif stock is None:
            status, days_left, qty = "ok", None, 0
            msg = "Остаток неизвестен."
        else:
            days_left = round(stock / per_day, 1)
            qty = max(0, math.ceil(per_day * (COVER_DAYS + LEAD_DAYS) - stock))
            if stock == 0:
                status, msg = "out", f"Закончился. Заказать {qty} шт — хватит на {COVER_DAYS} дней."
            elif days_left <= LEAD_DAYS:
                status, msg = "urgent", f"Осталось на {days_left:g} дн. Пора заказать {qty} шт."
            elif days_left <= LEAD_DAYS + 7:
                status, msg = "soon", f"Осталось на {days_left:g} дн. Скоро заказать ≈{qty} шт."
            else:
                status, msg = "ok", f"Хватит на {days_left:g} дн."
        reorder.append(ReorderRow(product_id=p.id, name=p.name, sku=p.sku, stock=stock, per_day=per_day,
                                  days_left=days_left, order_qty=qty, status=status, message=msg))
        if stock == 0 and per_day > 0:
            price = market.market_day(ds, p.id).my_price
            lost.append(LostRow(product_id=p.id, name=p.name, per_day=per_day, price=price,
                                lost_per_day=round(per_day * price)))
    order = {"out": 0, "urgent": 1, "soon": 2, "ok": 3, "no_sales": 4}
    reorder.sort(key=lambda r: (order[r.status], r.days_left if r.days_left is not None else 1e9, -r.per_day))
    lost.sort(key=lambda r: -r.lost_per_day)

    # ABC по прибыли (если закупка указана хоть у одного товара), иначе по выручке. XYZ — по неделям.
    with_cost = any(economics.cost_of(ds, p) is not None for p in ds.products.values())
    amount: dict[int, int] = {}
    since = max(ds.start, end - timedelta(days=89))
    day = since
    while day <= end:
        for o in ds.orders_by_day.get(day, ()):
            if o.status == "delivered":
                value = o.price * o.qty - (o.commission + o.delivery + o.cost) if with_cost else o.price * o.qty
                amount[o.product_id] = amount.get(o.product_id, 0) + value
        day += timedelta(days=1)
    total = sum(v for v in amount.values() if v > 0) or 1
    abc_class, running = {}, 0
    for pid, value in sorted(amount.items(), key=lambda kv: -kv[1]):
        if value <= 0:
            abc_class[pid] = "C"
            continue
        running += value
        abc_class[pid] = "A" if running / total <= 0.8 or not abc_class else "B" if running / total <= 0.95 else "C"
    weeks = 12
    abc = []
    for p in ds.products.values():
        days = year.get(p.id, {})
        weekly = [sum(days.get(end - timedelta(days=w * 7 + d), 0) for d in range(7)) for w in range(weeks)]
        avg = mean(weekly)
        xyz = None
        if avg > 0:
            cv = pstdev(weekly) / avg
            xyz = "X" if cv <= 0.5 else "Y" if cv <= 1.0 else "Z"
        a = abc_class.get(p.id)
        advice = {
            "A": "Главный товар — держите всегда в наличии.",
            "B": "Средний — заказывайте по мере продаж.",
            "C": "Мало приносит — новые партии не закупать, распродать остаток.",
        }.get(a or "", "Продаж нет — больше не закупать.")
        if a == "A" and xyz == "Z":
            advice = "Приносит много, но продаётся рывками — держите небольшой запас."
        abc.append(AbcRow(product_id=p.id, name=p.name, abc=a, xyz=xyz, amount=amount.get(p.id, 0), advice=advice))
    abc.sort(key=lambda r: ("ABC".find(r.abc) if r.abc else 9, -r.amount))

    # Риски: тесно на карточке, крупные продавцы, падение цены конкурентов по истории.
    snapshot = (load_market(ds.shop_id) or {}) if ds.source != "test" else {}
    history = load_history(ds.shop_id) if ds.source != "test" else {}
    risks = []
    for p in ds.products.values():
        if ds.source == "test":
            md = market.market_day(ds, p.id)
            sellers = len(md.competitor_prices) + 1
            big: list[str] = []
            first = market.market_day(ds, p.id, max(ds.start, end - timedelta(days=89))).competitor_prices.values()
            first_min = min(first) if first else None
            now_min = min(md.competitor_prices.values()) if md.competitor_prices else None
            history_days = 90
        else:
            raw = snapshot.get("products", {}).get(p.kaspi_code or "", [])
            sellers = len(raw)
            big = [s["name"] for s in raw if s["merchant_id"] != config.KASPI_MERCHANT_ID
                   and (s["reviews"] >= BIG_SELLER_REVIEWS or "kaspi" in s["name"].lower())]
            points = [day[p.kaspi_code] for day in history.values() if p.kaspi_code in day and day[p.kaspi_code]["min"]]
            first_min = points[0]["min"] if points else None
            now_min = points[-1]["min"] if points else None
            history_days = len(points)
        if sellers == 0:
            continue
        drop = round((first_min - now_min) / first_min * 100, 1) if first_min and now_min and history_days >= 2 else None
        monopoly = bool(big)
        if monopoly:
            advice = f"Не закупать много: на карточке крупный продавец ({big[0]}) — выдавит ценой."
        elif drop is not None and drop >= 15:
            advice = f"Цена у конкурентов упала на {drop:g}% — товар обесценивают, осторожно с закупом."
        elif sellers >= CROWDED_SELLERS:
            advice = f"Тесно: {sellers} продавцов — сильная ценовая война."
        elif sellers == 1:
            advice = "Вы один на карточке — хорошая позиция."
        else:
            advice = f"Продавцов {sellers} — обычная конкуренция."
        risks.append(RiskRow(product_id=p.id, name=p.name, sellers=sellers, big_sellers=big, monopoly=monopoly,
                             price_drop_pct=drop, history_days=history_days, advice=advice))
    risks.sort(key=lambda r: (not r.monopoly, -(r.price_drop_pct or 0), -r.sellers))

    return Insights(based_on="прибыли" if with_cost else "выручке", reorder=reorder,
                    lost_total_per_day=sum(r.lost_per_day for r in lost), lost=lost, abc=abc, risks=risks)
