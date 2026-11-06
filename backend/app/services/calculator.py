"""Юнит-экономика товара на Kaspi: что останется продавцу с одной продажи."""

import math

from app import schemas, tariffs


def price_for_margin(data: schemas.EconomicsInput, margin_pct: float) -> int | None:
    """Минимальная цена, при которой маржа не ниже заданной. None — недостижимо при таких ставках.

    Доставка зависит от цены скачками, поэтому решаем уравнение отдельно в каждом ценовом диапазоне.
    """
    share_left = 1 - (data.commission_pct + data.tax_pct + margin_pct) / 100
    if share_left <= 0:
        return None
    fixed = data.purchase_cost + data.other_cost
    bounds = [0, *(limit for limit, _ in tariffs.SMALL_ORDER_TIERS)]
    for low, high in zip(bounds, [*bounds[1:], math.inf]):
        fee = tariffs.delivery_fee(low, data.delivery_type, data.weight)
        price = max(math.ceil((fixed + fee) / share_left), low, 1)
        if price < high:
            return price
    return None


def calculate(data: schemas.EconomicsInput) -> schemas.Economics:
    commission = round(data.price * data.commission_pct / 100)
    delivery = tariffs.delivery_fee(data.price, data.delivery_type, data.weight)
    tax = round(data.price * data.tax_pct / 100)
    cost = data.purchase_cost + data.other_cost
    profit = data.price - commission - delivery - tax - cost
    return schemas.Economics(
        price=data.price,
        commission=commission,
        delivery=delivery,
        tax=tax,
        cost=cost,
        profit=profit,
        margin_pct=round(profit / data.price * 100, 1),
        roi_pct=round(profit / cost * 100, 1) if cost else None,
        break_even_price=price_for_margin(data, 0),
        target_price=price_for_margin(data, data.target_margin_pct),
    )
