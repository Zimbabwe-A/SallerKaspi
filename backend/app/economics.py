"""Экономика одной продажи: закупка, прибыль, цена без убытка.

Закупочная цена хранится только у вас: backend/var/shops/<магазин>/costs.json ({"артикул": цена}).
В магазин Kaspi отсюда ничего не уходит.
"""

import json
from dataclasses import dataclass

from app import config
from app.bot.storage import _write_private, lock
from app.data.generator import delivery_fee
from app.data.models import Dataset, Product
from app.kaspi.sync import shop_dir

MAX_PRICE = 100_000_000


def costs_file(shop_id: str):
    return shop_dir(shop_id) / "costs.json"


def load_costs(shop_id: str) -> dict[str, int]:
    path = costs_file(shop_id)
    if not path.exists():
        return {}
    return {str(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


def set_cost(shop_id: str, sku: str, cost: int | None) -> None:
    """Сохранить закупочную цену товара. None — удалить (снова «не указана»)."""
    with lock:
        costs = load_costs(shop_id)
        if cost is None:
            costs.pop(sku, None)
        else:
            costs[sku] = int(cost)
        shop_dir(shop_id).mkdir(mode=0o700, parents=True, exist_ok=True)
        _write_private(costs_file(shop_id), json.dumps(costs, ensure_ascii=False, indent=2))


def cost_of(ds: Dataset, product: Product) -> int | None:
    """Закупка: что вы ввели, иначе из данных магазина. None — не указана (у настоящего магазина)."""
    saved = load_costs(ds.shop_id).get(product.sku)
    if saved is not None:
        return saved
    if ds.source == "test":
        return product.cost_price
    return product.cost_price or None


@dataclass(frozen=True)
class Sale:
    price: int
    commission: int
    delivery: int
    tax: int
    cost: int
    profit: int


def sale(ds: Dataset, product: Product, price: int, cost: int) -> Sale:
    """Что остаётся с одной продажи по цене price (доставка — по тарифу «по Казахстану»)."""
    commission = round(price * ds.categories[product.category_id].commission)
    delivery = delivery_fee(price, product.weight_kg)
    tax = round(price * config.TAX_RATE)
    return Sale(price, commission, delivery, tax, cost, price - commission - delivery - tax - cost)


def break_even(ds: Dataset, product: Product, cost: int) -> int:
    """Самая низкая цена, при которой продажа не в минус.

    Доставка меняется ступеньками (по сумме заказа), поэтому прибыль растёт с ценой не плавно:
    ищем приблизительно, потом уточняем шагом в 1 ₸.
    """
    low, high = 1, max(cost * 3 + 20_000, 1_000)
    while sale(ds, product, high, cost).profit < 0 and high < MAX_PRICE:
        high *= 2
    # Ищем самую низкую цену с прибылью >= 0, проверяя, что и следующие цены не уходят в минус
    # (на границе ступени доставки прибыль может провалиться).
    while low < high:
        mid = (low + high) // 2
        if sale(ds, product, mid, cost).profit >= 0:
            high = mid
        else:
            low = mid + 1
    price = low
    while price < MAX_PRICE and any(sale(ds, product, p, cost).profit < 0 for p in range(price, price + 50)):
        price += 1
    return price
