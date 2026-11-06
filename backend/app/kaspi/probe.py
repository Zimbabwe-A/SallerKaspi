"""Разведка формата ответов Kaspi: python -m app.kaspi.probe

Берёт ОДИН недавний заказ и печатает только СТРУКТУРУ ответа: названия полей и типы значений.
Настоящие значения показываются только для безопасных служебных полей (статусы, способ доставки,
категория, название и артикул товара). Покупатель, получатель и адрес (кроме города) скрыты целиком.
Только чтение. Вывод можно смело прислать разработчику.
"""

from datetime import date, timedelta

from app.kaspi.client import BASE_URL, KaspiClient, KaspiError, _ms

# Поля, значения которых не персональные и нужны, чтобы понять формат.
SHOW = {
    "type", "state", "status", "deliveryMode", "paymentMode", "unitType", "express", "isKaspiDelivery",
    "signatureRequired", "preOrder", "isImeiRequired", "returnedToWarehouse", "title", "name", "code",
    "town", "manufacturer", "brand", "pageCount", "totalCount", "categoryName", "productName",
}
# Ветки, которые прячем целиком: здесь данные покупателя.
HIDE = {"customer", "recipient", "user", "phone", "cellPhone", "firstName", "lastName", "streetName",
        "streetNumber", "apartment", "address", "formattedAddress", "latitude", "longitude"}


def shape(value, key: str = "", depth: int = 0, parent: str = ""):
    if key in HIDE:
        return "<скрыто>"
    if isinstance(value, dict):
        if depth > 6:
            return "{…}"
        # В deliveryAddress оставляем только город.
        items = value.items()
        if parent == "deliveryAddress" or key == "deliveryAddress":
            items = [(k, v) for k, v in value.items() if k == "town"]
        return {k: shape(v, k, depth + 1, key) for k, v in items}
    if isinstance(value, list):
        return [shape(value[0], key, depth + 1, parent), f"… всего {len(value)}"] if value else []
    if key in SHOW and isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bool):
        return "<да/нет>"
    if isinstance(value, (int, float)):
        return "<число>"
    if isinstance(value, str):
        if value.startswith(BASE_URL):
            return "<ссылка kaspi api>"
        return f"<текст {len(value)} симв.>"
    return "<пусто>" if value is None else f"<{type(value).__name__}>"


def show(title: str, value) -> None:
    import json
    print(f"\n===== {title} =====")
    print(json.dumps(shape(value), ensure_ascii=False, indent=2))


def main() -> None:
    client = KaspiClient()
    end = date.today()
    start = end - timedelta(days=13)
    try:
        for state in ("ARCHIVE", "KASPI_DELIVERY", "DELIVERY", "PICKUP", "NEW"):
            body = client.get("orders", {
                "page[number]": 0, "page[size]": 1, "filter[orders][state]": state,
                "filter[orders][creationDate][$ge]": _ms(start),
                "filter[orders][creationDate][$le]": _ms(end + timedelta(days=1)) - 1,
            })
            if body.get("data"):
                break
        else:
            print("За 14 дней заказов не нашлось.")
            return
        show(f"Заказ (состояние {state})", body)

        order_id = body["data"][0]["id"]
        entries = client.get(f"orders/{order_id}/entries")
        show("Товары в заказе (entries)", entries)

        # Пробуем получить карточку товара по ссылке из заказа.
        first = (entries.get("data") or [{}])[0]
        product = (first.get("relationships") or {}).get("product") or {}
        link = (product.get("links") or {}).get("related") or (product.get("links") or {}).get("self")
        if isinstance(link, str) and link.startswith(BASE_URL):
            show("Товар (по ссылке из заказа)", client.get(link[len(BASE_URL):]))
        else:
            print("\nСсылки на товар в заказе нет.")
    except KaspiError as error:
        print(f"Не получилось: {error}")


if __name__ == "__main__":
    main()
