"""Автообновление настоящего магазина: python -m app.kaspi.autoupdate

Каждые AUTO_UPDATE_MINUTES минут (по умолчанию 5):
1. новые заказы из Kaspi API (только чтение);
2. цены конкурентов с открытых страниц kaspi.kz (только чтение);
3. пересчёт бота цен — ТОЛЬКО тестовый режим: бот пишет в журнал, что сделал бы, цены в Kaspi не меняет.

Запускать в Терминале на своём Mac (оттуда открывается Kaspi). Остановить — Ctrl+C.
"""

import json
import time
from datetime import datetime

from app import config
from app.bot import runner, storage
from app.bot.storage import _write_private
from app.data import store
from app.kaspi import market, sync
from app.kaspi.client import KaspiError

SHOP = "main"


def status_file():
    return sync.shop_dir(SHOP) / "autoupdate.json"


def write_status(**fields) -> None:
    sync.shop_dir(SHOP).mkdir(mode=0o700, parents=True, exist_ok=True)
    fields.pop("interval_minutes", None)  # интервал всегда текущий, из настроек
    _write_private(status_file(), json.dumps({"interval_minutes": config.AUTO_UPDATE_MINUTES, **fields}, ensure_ascii=False))


def load_status() -> dict | None:
    path = status_file()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def now() -> str:
    return datetime.now().strftime("%H:%M")


def run_cycle() -> dict:
    result: dict = {"started_at": datetime.now().isoformat(timespec="seconds")}
    try:
        sync.sync(SHOP, days=14, log=lambda *_: None)  # последние 2 недели: новые и изменившиеся заказы
        result["orders"] = "ok"
    except KaspiError as error:
        result["orders"] = f"ошибка: {error}"

    codes = market.product_codes(SHOP)
    products: dict[str, list[dict]] = (market.load_market(SHOP) or {}).get("products", {})
    try:
        for code in codes:
            products[code] = market.fetch_sellers(code, config.KASPI_CITY_ID)
            time.sleep(market.PAUSE_SECONDS)
        result["market"] = f"ok, товаров {len(codes)}"
    except market.MarketError as error:
        result["market"] = f"остановились: {error}"
    if products:
        market.save_market(SHOP, config.KASPI_CITY_ID, products)

    state = storage.load_state(SHOP)
    if state.enabled:
        ds = store.get_dataset(SHOP)
        changes = runner.run_once(ds)  # на настоящем магазине — всегда тестовый режим
        result["bot"] = f"посчитал, изменений {len(changes)} (тестовый режим)"
    else:
        result["bot"] = "бот остановлен — не считал"
    result["finished_at"] = datetime.now().isoformat(timespec="seconds")
    return result


def main() -> None:
    minutes = config.AUTO_UPDATE_MINUTES
    print(f"Автообновление каждые {minutes} мин. Только чтение, цены в Kaspi не меняются. Остановить — Ctrl+C.")
    while True:
        print(f"[{now()}] обновляю…", flush=True)
        # Сразу сообщаем сайту, что автообновление работает (зелёный огонёк), не дожидаясь конца прохода.
        previous = load_status() or {}
        write_status(**{**previous, "running": True, "heartbeat": datetime.now().isoformat(timespec="seconds")})
        try:
            result = run_cycle()
        except Exception as error:  # один сбой не должен останавливать обновление
            result = {"error": str(error), "finished_at": datetime.now().isoformat(timespec="seconds")}
        write_status(**result, running=False, heartbeat=datetime.now().isoformat(timespec="seconds"))
        print(f"[{now()}] заказы: {result.get('orders')} · конкуренты: {result.get('market')} · бот: {result.get('bot')}", flush=True)
        time.sleep(minutes * 60)


if __name__ == "__main__":
    main()
