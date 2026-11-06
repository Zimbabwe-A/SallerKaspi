"""Как бот выбирает цену. Чистая функция: без сети, файлов и времени — её легко проверить тестами."""

from dataclasses import dataclass
from typing import Literal

Strategy = Literal["first", "second"]
Kind = Literal["target", "min", "max", "alone"]


@dataclass(frozen=True)
class Rule:
    min_price: int
    max_price: int
    step: int = 1
    strategy: Strategy = "first"


@dataclass(frozen=True)
class Decision:
    price: int
    reason: str
    kind: Kind  # target — встали куда хотели; min/max — упёрлись в границу; alone — конкурентов нет


def tg(value: int) -> str:
    """10510 -> «10 510 ₸» (неразрывные пробелы)."""
    return f"{value:,}".replace(",", "\u00a0") + "\u00a0₸"


def decide(rule: Rule, competitor_prices: list[int]) -> Decision:
    """Новая цена товара.

    first  — встать на 1 шаг дешевле самого дешёвого конкурента;
    second — встать на 1 шаг дешевле второго по цене конкурента (держимся вторыми, бережём маржу).
    Цена всегда остаётся в пределах [min_price, max_price].
    """
    if rule.min_price <= 0 or rule.max_price < rule.min_price or rule.step <= 0:
        raise ValueError("Нужно: минимум > 0, максимум ≥ минимума, шаг > 0")

    prices = sorted(p for p in competitor_prices if p > 0)
    index = 0 if rule.strategy == "first" else 1
    if len(prices) <= index:
        return Decision(rule.max_price, "Других продавцов нет — держим максимум", "alone")

    target = prices[index] - rule.step
    place = "самого дешёвого" if index == 0 else "второго по цене"
    if target < rule.min_price:
        return Decision(rule.min_price,
                        f"Конкурент продаёт за {tg(prices[index])} — это ниже вашего минимума, стоим на минимуме", "min")
    if target > rule.max_price:
        return Decision(rule.max_price, "Все конкуренты дороже максимума — стоим на максимуме", "max")
    return Decision(target, f"На {tg(rule.step)} дешевле {place} конкурента ({tg(prices[index])})", "target")


def position(price: int, competitor_prices: list[int]) -> int:
    """Место по цене на карточке (1 — самый дешёвый). При равной цене считаем, что мы ниже конкурента."""
    return 1 + sum(1 for p in competitor_prices if 0 < p <= price)
