"""Проверка подключения к Kaspi: python -m app.kaspi.check

Печатает только количество заказов и суммы по состояниям — без номеров заказов и данных покупателей.
"""

from collections import Counter
from datetime import date, timedelta

from app.kaspi.client import ORDER_STATES, KaspiClient, KaspiError


def main(days: int = 14) -> None:
    end = date.today()
    start = end - timedelta(days=days - 1)
    print(f"Проверяю заказы Kaspi за {start:%d.%m} — {end:%d.%m} (только чтение)…")
    try:
        client = KaspiClient()
        total, with_delivery = 0, 0
        for state in ORDER_STATES:
            orders = client.orders(start, end, state)
            total += len(orders)
            with_delivery += sum(o.delivery_cost_for_seller is not None for o in orders)
            statuses = ", ".join(f"{s} {n}" for s, n in Counter(o.status for o in orders).most_common())
            amount = sum(o.total_price for o in orders)
            print(f"  {state:<15} заказов: {len(orders):>4}   сумма: {amount:>12,} ₸   {statuses}".replace(",", " "))
        print(f"Готово. Всего заказов: {total}. С полем доставки для продавца: {with_delivery}.")
    except KaspiError as error:
        print(f"Не получилось: {error}")


if __name__ == "__main__":
    main()
