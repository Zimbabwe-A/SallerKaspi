"""Один проход бота и фоновый цикл."""

import asyncio
import logging

from app import config
from app.bot import storage
from app.bot.feed import FeedOffer, build_xml
from app.bot.sources import CompetitorSource, TestCompetitorSource
from app.bot.strategy import Rule, decide
from app import economics
from app.data.models import Dataset
from app.data.store import get_dataset
from app.services.market import market_day

log = logging.getLogger("bot")


def current_price(ds: Dataset, state: storage.BotState, product_id: int) -> int:
    return state.prices.get(str(product_id), market_day(ds, product_id).my_price)


def effective_rule(ds: Dataset, pid: int, rule: storage.ProductRule) -> tuple[Rule, int | None]:
    """Правило с учётом защиты от убытка: минимум не ниже цены без убытка. Возвращает и эту цену."""
    base = rule.to_rule()
    product = ds.products[pid]
    cost = economics.cost_of(ds, product)
    if cost is None:
        return base, None
    floor = economics.break_even(ds, product, cost)
    if rule.protect and floor > base.min_price:
        return Rule(floor, max(base.max_price, floor), base.step, base.strategy), floor
    return base, floor


def run_once(ds: Dataset, source: CompetitorSource | None = None, force: bool = False) -> list[dict]:
    """Пересчитать цены всех включённых товаров и обновить XML.

    force=True — запустить, даже если общий выключатель выключен (кнопка «Проверить сейчас»).
    В режиме проверки (dry_run) цены не меняются, только пишутся в журнал.
    """
    if not ds.market_known:  # нет цен конкурентов — бот ничего не делает
        return []
    source = source or TestCompetitorSource(ds)
    shop = ds.shop_id
    # Настоящий магазин: только тестовый режим — бот считает, но ничего не меняет в Kaspi.
    real_shop = ds.source != "test"
    with storage.lock:
        state = storage.load_state(shop)
        if real_shop:
            state.dry_run = True
        if not state.enabled and not force:
            return []

        time = storage.now_iso()
        entries: list[dict] = []
        for pid_str, rule in state.rules.items():
            pid = int(pid_str)
            if not rule.enabled or pid not in ds.products:
                continue
            old = current_price(ds, state, pid)
            try:
                decision = decide(effective_rule(ds, pid, rule)[0], source.prices(pid))
            except Exception as error:  # один сломанный товар не должен останавливать остальные
                entries.append(_entry(time, ds, pid, old, old, f"Ошибка: {error}", state.dry_run))
                continue
            if decision.price == old:
                continue
            entries.append(_entry(time, ds, pid, old, decision.price, decision.reason, state.dry_run))
            if not state.dry_run:
                state.prices[pid_str] = decision.price

        state.last_run = time
        storage.save_state(state, shop)
        storage.append_log(entries, shop)
        if not real_shop:  # прайс-лист для Kaspi — только у демо-магазина
            storage.write_feed(render_feed(ds, state))
        return entries


def _entry(time: str, ds: Dataset, pid: int, old: int, new: int, reason: str, dry_run: bool) -> dict:
    p = ds.products[pid]
    return {"time": time, "product_id": pid, "sku": p.sku, "name": p.name,
            "old_price": old, "new_price": new, "reason": reason, "dry_run": dry_run}


def render_feed(ds: Dataset, state: storage.BotState) -> str:
    offers = [
        FeedOffer(
            sku=p.sku,
            model=p.name,
            brand=config.KASPI_DEFAULT_BRAND,
            price=current_price(ds, state, p.id),
            stock=ds.stock[p.id].quantity,
        )
        for p in ds.products.values()
    ]
    return build_xml(config.KASPI_COMPANY, config.KASPI_MERCHANT_ID, config.KASPI_STORE_ID, offers)


async def loop() -> None:
    """Фоновый цикл: раз в BOT_INTERVAL_SECONDS, только если бот включён."""
    while True:
        try:
            await asyncio.to_thread(run_once, get_dataset())
        except Exception:
            log.exception("Ошибка в проходе бота")
        await asyncio.sleep(config.BOT_INTERVAL_SECONDS)
