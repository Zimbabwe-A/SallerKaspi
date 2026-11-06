"""Проверка: есть ли у текущих заказов Kaspi Доставки ссылка на накладную. python -m app.kaspi.waybill_probe

Печатает только «есть / нет», адрес сайта ссылки и тип файла — без самой ссылки и данных покупателя.
Только чтение.
"""

import urllib.parse
import urllib.request
from datetime import date, timedelta

from app.kaspi.client import SSL_CONTEXT, KaspiClient, KaspiError, _ms


def main() -> None:
    client = KaspiClient()
    end = date.today()
    start = end - timedelta(days=13)
    try:
        body = client.get("orders", {
            "page[number]": 0, "page[size]": 20, "filter[orders][state]": "KASPI_DELIVERY",
            "filter[orders][creationDate][$ge]": _ms(start),
            "filter[orders][creationDate][$le]": _ms(end + timedelta(days=1)) - 1,
        })
    except KaspiError as error:
        print(f"Не получилось: {error}")
        return
    orders = body.get("data", [])
    print(f"Заказов в Kaspi Доставке: {len(orders)}")
    for o in orders[:20]:
        a = o.get("attributes", {})
        kd = a.get("kaspiDelivery") or {}
        url = kd.get("waybill")
        info = "нет ссылки"
        if isinstance(url, str) and url:
            host = urllib.parse.urlparse(url).hostname
            kind = "?"
            try:
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "SallerKaspi-analytics/0.1"})
                with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as r:
                    kind = f"{r.status} {r.headers.get('Content-Type')}"
            except Exception as error:
                kind = f"не открылась без входа ({type(error).__name__})"
            info = f"есть ссылка на {host}, файл: {kind}"
        print(f"  статус {a.get('status')}, собран: {a.get('assembled')}, номер накладной: {'есть' if kd.get('waybillNumber') else 'нет'} — {info}")


if __name__ == "__main__":
    main()
