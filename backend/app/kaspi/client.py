"""Клиент Kaspi Shop API — ТОЛЬКО ЧТЕНИЕ.

Правила безопасности, зашитые в код:
- только GET-запросы: метода, который что-то меняет в магазине, здесь нет;
- только на https://kaspi.kz/shop/api/v2/ — токен не уйдёт ни на какой другой адрес;
- токен не попадает в логи, ошибки и ответы (repr и сообщения ошибок его не содержат);
- данные покупателей (ФИО, телефон, адрес) отбрасываются сразу после получения.

Документация: guide.kaspi.kz/partner/ru/shop/api/orders/q3201
"""

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import certifi

from app import config

BASE_URL = "https://kaspi.kz/shop/api/v2/"
PAGE_SIZE = 100  # максимум у Kaspi
CHUNK_DAYS = 14  # период запроса заказов дробим на куски по 14 дней
TIMEOUT = 30
# Свои сертификаты: Python с python.org на macOS не видит системные, и HTTPS без этого не работает.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

ORDER_STATES = ["NEW", "SIGN_REQUIRED", "PICKUP", "DELIVERY", "KASPI_DELIVERY", "ARCHIVE"]


class KaspiError(Exception):
    """Ошибка запроса к Kaspi. Сообщение никогда не содержит токен."""


@dataclass(frozen=True)
class Order:
    """Заказ без персональных данных покупателя."""
    id: str
    code: str
    created: datetime
    state: str
    status: str
    total_price: int
    delivery_cost_for_seller: int | None
    delivery_mode: str | None
    express: bool
    town: str | None


class KaspiClient:
    def __init__(self, token: str | None = None):
        token = (token if token is not None else config.KASPI_API_TOKEN).strip()
        if not token:
            raise KaspiError("Токен Kaspi не задан: впишите KASPI_API_TOKEN в backend/.env")
        self.__token = token  # двойное подчёркивание: не светится в repr и автодополнении

    def __repr__(self) -> str:
        return "KaspiClient(token=***)"

    def get(self, path: str, params: dict[str, str | int] | None = None) -> dict:
        url = urllib.parse.urljoin(BASE_URL, path.lstrip("/"))
        if not url.startswith(BASE_URL):
            raise KaspiError("Запрос разрешён только к kaspi.kz/shop/api/v2")
        if params:
            url += "?" + urllib.parse.urlencode(params, safe="[]$")
        request = urllib.request.Request(url, method="GET", headers={
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
            "X-Auth-Token": self.__token,
            "User-Agent": "SallerKaspi-analytics/0.1",
        })
        last = ""
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT, context=SSL_CONTEXT) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                if error.code == 401 or error.code == 403:
                    raise KaspiError("Kaspi не принял токен (проверьте KASPI_API_TOKEN в backend/.env)") from None
                if error.code == 429 or error.code >= 500:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise KaspiError(f"Kaspi ответил ошибкой {error.code} на {path}") from None
            except (urllib.error.URLError, TimeoutError) as error:
                last = type(getattr(error, "reason", error)).__name__
                time.sleep(2 * (attempt + 1))
        raise KaspiError(f"Kaspi не отвечает ({path}, {last}). Проверьте, открывается ли kaspi.kz в браузере.")

    def orders(self, start: date, end: date, state: str) -> list[Order]:
        """Заказы в состоянии state, созданные с start по end включительно."""
        result: list[Order] = []
        chunk_start = start
        while chunk_start <= end:
            chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), end)
            page = 0
            while True:
                body = self.get("orders", {
                    "page[number]": page,
                    "page[size]": PAGE_SIZE,
                    "filter[orders][state]": state,
                    "filter[orders][creationDate][$ge]": _ms(chunk_start),
                    "filter[orders][creationDate][$le]": _ms(chunk_end + timedelta(days=1)) - 1,
                })
                result += [parse_order(item) for item in body.get("data", [])]
                page += 1
                if page >= int(body.get("meta", {}).get("pageCount", 0) or 0):
                    break
            chunk_start = chunk_end + timedelta(days=1)
        return result


def _ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day).timestamp() * 1000)


def _int(value) -> int | None:
    return None if value is None else int(round(float(value)))


def parse_order(item: dict) -> Order:
    """Берём только нужное для аналитики. customer, recipient и улица адреса не сохраняются."""
    a = item.get("attributes", {})
    address = a.get("deliveryAddress") or {}
    return Order(
        id=str(item.get("id")),
        code=str(a.get("code", "")),
        created=datetime.fromtimestamp(int(a.get("creationDate", 0)) / 1000),
        state=str(a.get("state", "")),
        status=str(a.get("status", "")),
        total_price=_int(a.get("totalPrice")) or 0,
        delivery_cost_for_seller=_int(a.get("deliveryCostForSeller")),
        delivery_mode=a.get("deliveryMode"),
        express=bool(a.get("express")),
        town=address.get("town") if isinstance(address, dict) else None,
    )
