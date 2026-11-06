"""Кабинет продавца Kaspi — ТОЛЬКО ЧТЕНИЕ товаров (остатки, цены, фото, наличие).

Как устроено (см. CABINET_NOTES.md):
- вход: POST https://idmc.shop.kaspi.kz/api/p/login с почтой и паролем пользователя «Аналитика Бот»;
- товары: POST https://mc.shop.kaspi.kz/bff/offer-view/v2/list (это запрос-ПОИСК, он ничего не меняет).

Правила безопасности, зашитые в код:
- разрешены ровно два адреса (вход и список товаров) — любой другой запрос отклоняется;
  запросов, которые меняют цену, остаток или заказы, здесь нет;
- почта и пароль берутся только из backend/.env и не попадают в логи, ошибки и repr;
- сессия (cookie) хранится в backend/var/shops/<магазин>/cabinet_cookies.txt, права только у владельца.
"""

import http.cookiejar
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import certifi

from app import config
from app.kaspi.sync import shop_dir

LOGIN_URL = "https://idmc.shop.kaspi.kz/api/p/login"
OFFERS_URL = "https://mc.shop.kaspi.kz/bff/offer-view/v2/list"
# Только эти адреса можно вызывать методом POST. Оба ничего не меняют в магазине.
ALLOWED_POST = {LOGIN_URL, OFFERS_URL}
ALLOWED_HOSTS = {"idmc.shop.kaspi.kz", "mc.shop.kaspi.kz", "kaspi.kz"}

PAGE_SIZE = 100
TIMEOUT = 30
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
USER_AGENT = "SallerKaspi-analytics/0.1"


class CabinetError(Exception):
    """Ошибка работы с кабинетом. Сообщение никогда не содержит почту, пароль и cookie."""


@dataclass(frozen=True)
class Offer:
    sku: str  # ваш артикул
    master_sku: str  # код карточки на kaspi.kz
    title: str
    brand: str | None
    price: int
    available: bool
    stock: int | None  # сумма по складам; None — остаток не указан в кабинете
    stores: tuple[str, ...]
    preorder_days: int
    image: str | None


class CabinetClient:
    def __init__(self, shop_id: str = "main", email: str | None = None, password: str | None = None):
        self.shop_id = shop_id
        self.__email = (email if email is not None else config.KASPI_CABINET_EMAIL).strip()
        self.__password = password if password is not None else config.KASPI_CABINET_PASSWORD
        self.merchant_id = config.KASPI_MERCHANT_ID
        self.cookie_file = shop_dir(shop_id) / "cabinet_cookies.txt"
        self.jar = http.cookiejar.MozillaCookieJar(str(self.cookie_file))
        if self.cookie_file.exists():
            try:
                self.jar.load(ignore_discard=True, ignore_expires=True)
            except (OSError, http.cookiejar.LoadError):
                pass
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.HTTPSHandler(context=SSL_CONTEXT),
        )

    def __repr__(self) -> str:
        return f"CabinetClient(shop={self.shop_id!r}, email=***, password=***)"

    # --- низкий уровень ---

    def _request(self, method: str, url: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict | None]:
        base = url.split("?", 1)[0]
        host = urllib.parse.urlparse(url).hostname or ""
        if host not in ALLOWED_HOSTS:
            raise CabinetError("Запрос разрешён только к кабинету Kaspi")
        if method != "GET" and base not in ALLOWED_POST:
            raise CabinetError("Этот запрос мог бы изменить магазин — он запрещён")
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            **(headers or {}),
        })
        try:
            with self.opener.open(request, timeout=TIMEOUT) as response:
                text = response.read().decode("utf-8", errors="replace")
                status = response.status
        except urllib.error.HTTPError as error:
            return error.code, None
        except (urllib.error.URLError, TimeoutError):
            raise CabinetError("Кабинет Kaspi не отвечает. Проверьте, открывается ли kaspi.kz.") from None
        try:
            return status, json.loads(text) if text.strip() else None
        except json.JSONDecodeError:
            return status, None

    def _save_cookies(self) -> None:
        self.cookie_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.jar.save(ignore_discard=True, ignore_expires=True)
        os.chmod(self.cookie_file, 0o600)

    # --- вход ---

    def login(self) -> None:
        if not self.__email or not self.__password:
            raise CabinetError("Впишите KASPI_CABINET_EMAIL и KASPI_CABINET_PASSWORD в backend/.env")
        # Сначала открываем страницу входа: она ставит служебные cookie, без них вход не проходит.
        self._request("GET", "https://idmc.shop.kaspi.kz/login", headers={"Accept": "text/html"})
        status, body = self._request("POST", LOGIN_URL, {"_u": self.__email, "_p": self.__password, "_r_d": True}, {
            "Origin": "https://idmc.shop.kaspi.kz",
            "Referer": "https://idmc.shop.kaspi.kz/login",
        })
        if status in (400, 401):
            raise CabinetError(f"Kaspi не принял почту или пароль пользователя кабинета (ответ {status})")
        if status == 403:
            raise CabinetError("Kaspi закрыл вход для программы (ответ 403) — похоже, защита от ботов. Обходить её не будем.")
        if status != 200 or not isinstance(body, dict) or "redirectUrl" not in body:
            # Показываем только названия полей ответа — без значений.
            keys = sorted(body.keys()) if isinstance(body, dict) else type(body).__name__
            raise CabinetError(f"Вход в кабинет не удался (ответ {status}, поля: {keys}). "
                               "Возможно, Kaspi просит код — войдите вручную.")
        redirect = str(body["redirectUrl"])
        if not redirect.startswith("http"):
            redirect = urllib.parse.urljoin("https://idmc.shop.kaspi.kz/", redirect)
        self._request("GET", redirect)  # открывает кабинет и ставит cookie сессии
        self._save_cookies()

    # --- товары ---

    def _offers_page(self, start: int) -> tuple[int, dict | None]:
        query = urllib.parse.urlencode({"m": self.merchant_id, "l": PAGE_SIZE, "start": start, "sortBy": "DATE_DESC"})
        return self._request("POST", f"{OFFERS_URL}?{query}", {"available": True}, {
            "Origin": "https://kaspi.kz",
            "Referer": "https://kaspi.kz/mc/",
        })

    def offers(self) -> list[Offer]:
        """Все товары в продаже. Если сессия истекла — один раз входит заново."""
        if not self.merchant_id:
            raise CabinetError("Впишите KASPI_MERCHANT_ID в backend/.env (виден в шапке кабинета: «ID - …»)")
        result: list[Offer] = []
        start, relogged = 0, False
        while True:
            status, body = self._offers_page(start)
            if status in (401, 403) or (status == 200 and not isinstance(body, dict)):
                if relogged:
                    raise CabinetError("Кабинет не пускает даже после входа. Попробуйте войти вручную.")
                self.login()
                relogged = True
                continue
            if status != 200 or not isinstance(body, dict):
                raise CabinetError(f"Кабинет ответил ошибкой {status} на список товаров")
            data = body.get("data") or []
            result += [parse_offer(item) for item in data]
            start += len(data)
            if not data or start >= int(body.get("total") or 0):
                break
            time.sleep(0.5)  # не нагружаем кабинет
        self._save_cookies()
        return result


def _image(value) -> str | None:
    """Фото: Kaspi отдаёт список строк или объектов — берём первую ссылку."""
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, str):
            url = first
        elif isinstance(first, dict):
            url = next((v for k, v in first.items() if isinstance(v, str) and ("url" in k.lower() or v.startswith("http"))), None)
        else:
            url = None
        if url and url.startswith("//"):
            url = "https:" + url
        if url and not url.startswith("http"):
            url = "https://resources.cdn-kaspi.kz/img/m/p/" + url.lstrip("/")
        return url
    return None


def parse_offer(item: dict) -> Offer:
    availabilities = item.get("availabilities") or []
    counts = [a.get("stockCount") for a in availabilities if a.get("stockSpecified") and a.get("stockCount") is not None]
    return Offer(
        sku=str(item.get("sku") or ""),
        master_sku=str(item.get("masterSku") or ""),
        title=str(item.get("title") or item.get("model") or item.get("masterName") or ""),
        brand=item.get("brandName") or item.get("brand"),
        price=int(round(float(item.get("price") or 0))),
        available=bool(item.get("available")) and any(str(a.get("available")).lower() in ("yes", "true", "да") for a in availabilities),
        stock=int(sum(counts)) if counts else None,
        stores=tuple(str(a.get("storeId")) for a in availabilities if a.get("storeId")),
        preorder_days=max((int(a.get("preOrder") or 0) for a in availabilities), default=0),
        image=_image(item.get("imagesV2")) or _image(item.get("images")),
    )


def offers_file(shop_id: str):
    return shop_dir(shop_id) / "offers.json"


def save_offers(shop_id: str, offers: list[Offer]) -> None:
    from datetime import datetime

    from app.bot.storage import _write_private
    shop_dir(shop_id).mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = {"synced_at": datetime.now().isoformat(timespec="seconds"), "offers": [o.__dict__ | {"stores": list(o.stores)} for o in offers]}
    _write_private(offers_file(shop_id), json.dumps(payload, ensure_ascii=False))


def load_offers(shop_id: str) -> dict | None:
    path = offers_file(shop_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main() -> None:
    """python -m app.kaspi.cabinet — загрузить остатки, цены и фото из кабинета (только чтение)."""
    try:
        client = CabinetClient()
        offers = client.offers()
        save_offers("main", offers)
        with_stock = sum(o.stock is not None for o in offers)
        with_photo = sum(o.image is not None for o in offers)
        print(f"Готово: товаров в продаже {len(offers)}, с остатком {with_stock}, с фото {with_photo}.")
        print("Обновите страницу сайта.")
    except CabinetError as error:
        print(f"Не получилось: {error}")


if __name__ == "__main__":
    main()
