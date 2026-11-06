"""Загрузка всей истории заказов: python -m app.kaspi.backfill [с какой даты, по умолчанию 2015-01-01]

Только чтение. Идёт от сегодняшнего дня назад кусками по 14 дней, сохраняется по ходу —
если прервать (Ctrl+C), повторный запуск продолжит и не скачает уже загруженное заново.
Если Kaspi не отдаёт какой-то старый период, программа пропускает его и идёт дальше.
"""

import sys
import time
from datetime import date, timedelta

from app.kaspi.client import CHUNK_DAYS, ORDER_STATES, PAGE_SIZE, KaspiClient, KaspiError, _ms
from app.kaspi.sync import FINAL_STATES, clean_entry, clean_order, load_cache, save_cache

SHOP = "main"


def main() -> None:
    since = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2015, 1, 1)
    client = KaspiClient()
    cache = load_cache(SHOP)
    cache["days"] = max(int(cache.get("days") or 0), (date.today() - since).days + 1)
    print(f"Загружаю историю заказов с {since:%d.%m.%Y} (только чтение). Можно прервать Ctrl+C и продолжить потом.")

    end = date.today()
    added, skipped_chunks, empty_streak = 0, 0, 0
    while end >= since:
        start = max(since, end - timedelta(days=CHUNK_DAYS - 1))
        found = 0
        for state in ORDER_STATES:
            page = 0
            while True:
                try:
                    body = client.get("orders", {
                        "page[number]": page, "page[size]": PAGE_SIZE, "filter[orders][state]": state,
                        "filter[orders][creationDate][$ge]": _ms(start),
                        "filter[orders][creationDate][$le]": _ms(end + timedelta(days=1)) - 1,
                    })
                except KaspiError:
                    skipped_chunks += 1
                    break
                for raw in body.get("data", []):
                    found += 1
                    order = clean_order(raw)
                    old = cache["orders"].get(order["id"])
                    if old and old.get("entries") is not None and old.get("state") in FINAL_STATES:
                        continue
                    order["entries"] = old.get("entries") if old else None
                    if order["entries"] is None:
                        try:
                            entries = client.get(f"orders/{order['id']}/entries")
                            order["entries"] = [clean_entry(e) for e in entries.get("data", [])]
                        except KaspiError:
                            pass
                    cache["orders"][order["id"]] = order
                    added += 1
                page += 1
                if page >= int((body.get("meta") or {}).get("pageCount") or 0):
                    break
        save_cache(SHOP, cache)
        cache = load_cache(SHOP)
        cache["days"] = max(int(cache.get("days") or 0), (date.today() - since).days + 1)
        print(f"  {start:%d.%m.%Y}–{end:%d.%m.%Y}: заказов {found} · всего в истории {len(cache['orders'])}", flush=True)
        # Год подряд без единого заказа — дальше в прошлое, скорее всего, магазина ещё не было.
        empty_streak = empty_streak + 1 if found == 0 else 0
        if empty_streak >= 26:
            print("Год без заказов — дальше истории нет, останавливаюсь.")
            break
        end = start - timedelta(days=1)
        time.sleep(0.3)
    print(f"Готово: в истории {len(cache['orders'])} заказов (добавлено/обновлено {added}). "
          f"Пропущено периодов: {skipped_chunks}. Обновите страницу сайта.")


if __name__ == "__main__":
    main()
