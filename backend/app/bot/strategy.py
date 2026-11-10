"""Как бот выбирает цену. Чистая функция: без сети, файлов и времени — её легко проверить тестами."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Literal

Strategy = Literal["first", "second", "top3", "top5"]
# Какое место по цене держим: first — 1-е, second — 2-е, top3/top5 — не ниже 3-го/5-го (меньше уступаем в цене).
PLACE_INDEX = {"first": 0, "second": 1, "top3": 2, "top5": 4}
Kind = Literal["target", "min", "max", "alone", "hold"]


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
    kind: Kind  # target — встали куда хотели; min/max — упёрлись в границу; alone — конкурентов нет; hold — тормоза


def tg(value: int) -> str:
    """10510 -> «10 510 ₸» (неразрывные пробелы)."""
    return f"{value:,}".replace(",", "\u00a0") + "\u00a0₸"


def decide(rule: Rule, competitor_prices: list[int]) -> Decision:
    """Новая цена товара.

    first  — встать на 1 шаг дешевле самого дешёвого конкурента;
    second — встать на 1 шаг дешевле второго по цене конкурента (держимся вторыми, бережём маржу);
    top3 / top5 — на шаг дешевле 3-го / 5-го конкурента: место в тройке / пятёрке, цена выше.
    Цены-выбросы (опечатки, «товар за 1 ₸») не считаются. Цена всегда остаётся в пределах [min_price, max_price].
    """
    if rule.min_price <= 0 or rule.max_price < rule.min_price or rule.step <= 0:
        raise ValueError("Нужно: минимум > 0, максимум ≥ минимума, шаг > 0")

    prices = clean_prices(competitor_prices)
    index = PLACE_INDEX.get(rule.strategy, 0)
    if len(prices) <= index:
        if index and prices:
            return Decision(rule.max_price, f"Конкурентов меньше, чем {index + 1} — место и так ваше, держим максимум", "alone")
        return Decision(rule.max_price, "Других продавцов нет — держим максимум", "alone")

    target = prices[index] - rule.step
    place = {0: "самого дешёвого", 1: "второго по цене"}.get(index, f"{index + 1}-го по цене")
    if target < rule.min_price:
        return Decision(rule.min_price,
                        f"Конкурент продаёт за {tg(prices[index])} — это ниже вашего минимума, стоим на минимуме", "min")
    if target > rule.max_price:
        return Decision(rule.max_price, "Все конкуренты дороже максимума — стоим на максимуме", "max")
    return Decision(target, f"На {tg(rule.step)} дешевле {place} конкурента ({tg(prices[index])})", "target")


def clean_prices(competitor_prices: list[int]) -> list[int]:
    """Цены конкурентов без выбросов: дороже 4 медиан или дешевле половины медианы — не рынок, а ошибка."""
    prices = sorted(p for p in competitor_prices if p > 0)
    if len(prices) < 3:
        return prices
    mid = median(prices)
    return [p for p in prices if mid / 2 <= p <= mid * 4]


# ---------- тормоза: чтобы бот не сжёг маржу за вечер ----------
MAX_STEP_SHARE = 0.05  # за один проход цена меняется не больше чем на 5 %
MAX_MOVES_PER_DAY = 6  # не больше 6 снижений и 6 подъёмов в сутки
PAUSE = timedelta(minutes=60)  # между ходами в одну сторону — не меньше часа
NIGHT = (23, 7)  # с 23:00 до 07:00 цену не снижаем: ночью покупателей мало, гонка ничего не решает


@dataclass(frozen=True)
class Move:
    time: datetime
    up: bool


def is_night(now: datetime) -> bool:
    start, end = NIGHT
    return now.hour >= start or now.hour < end


def brake(old: int, decision: Decision, moves: list[Move], now: datetime,
          floor: int | None = None, night_pause: bool = True) -> Decision:
    """Ограничить ход бота: глубина, частота, пауза, ночь. Чистая функция.

    moves — ходы этого товара (для подсчёта за сутки). floor — цена без убытка:
    подъём до неё тормозами не ограничен — это исправление убытка, а не гонка.
    """
    new = decision.price
    if new == old:
        return decision
    up = new > old
    if up and floor is not None and old < floor:
        return Decision(new, f"Цена была ниже безубыточной ({tg(floor)}) — поднимаем сразу. {decision.reason}", decision.kind)
    if not up and night_pause and is_night(now):
        return Decision(old, "Ночь — снижать цену начнём с 7:00, ночью гонка ничего не решает", "hold")
    day_ago = now - timedelta(days=1)
    same = sorted(m.time for m in moves if m.up == up and m.time > day_ago)
    word = "подъём" if up else "снижение"
    if len(same) >= MAX_MOVES_PER_DAY:
        return Decision(old, f"За сутки уже {len(same)} ходов в эту сторону — следующий {word} завтра", "hold")
    if same and now - same[-1] < PAUSE:
        wait = math.ceil((PAUSE - (now - same[-1])).total_seconds() / 60)
        return Decision(old, f"Пауза после прошлого хода: следующий {word} через {wait} мин — ждём ответа рынка", "hold")
    limit = max(1, math.floor(old * MAX_STEP_SHARE))
    if abs(new - old) > limit:
        step_price = old + limit if up else old - limit
        if up:
            step_price = min(step_price, old * 2)
        return Decision(step_price, f"{decision.reason}. Двигаемся постепенно: не больше 5 % за проход", decision.kind)
    return decision


def position(price: int, competitor_prices: list[int]) -> int:
    """Место по цене на карточке (1 — самый дешёвый). При равной цене считаем, что мы ниже конкурента."""
    return 1 + sum(1 for p in competitor_prices if 0 < p <= price)
