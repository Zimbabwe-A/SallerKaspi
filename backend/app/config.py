"""Настройки mock-сервера.

Комиссии и доставка — по тарифам Kaspi на 2026 год (источники указаны ниже).
Налог — заглушка: укажите ставку своего режима.
"""

import os
from pathlib import Path


def _load_env(path: Path) -> None:
    """Читает backend/.env (KEY=value) в переменные окружения, не перезаписывая уже заданные."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env(Path(__file__).resolve().parent.parent / ".env")

# Токен API Kaspi. Хранится только в backend/.env, в коде его нет.
KASPI_API_TOKEN = os.environ.get("KASPI_API_TOKEN", "")
KASPI_API_URL = "https://kaspi.kz/shop/api/v2"

# Данные для XML-прайс-листа. Берутся из кабинета продавца Kaspi, задаются в backend/.env:
#   KASPI_COMPANY — название магазина, KASPI_MERCHANT_ID — ID продавца,
#   KASPI_STORE_ID — код склада («Склады и магазины» в кабинете).
KASPI_COMPANY = os.environ.get("KASPI_COMPANY", "").strip() or "Мой магазин"
KASPI_MERCHANT_ID = os.environ.get("KASPI_MERCHANT_ID", "")
KASPI_STORE_ID = os.environ.get("KASPI_STORE_ID", "").strip() or "PP1"
KASPI_DEFAULT_BRAND = os.environ.get("KASPI_DEFAULT_BRAND", "").strip() or "NoName"

# Бот цен: как часто пересчитывать цены. Kaspi забирает прайс-лист раз в 60 минут,
# поэтому чаще, чем раз в несколько минут, пересчитывать нет смысла.
BOT_INTERVAL_SECONDS = int(os.environ.get("BOT_INTERVAL_SECONDS", "300"))

SEED = 42
HISTORY_DAYS = 180
CURRENCY = "KZT"

# Откуда React-приложению разрешено ходить в API (Vite по умолчанию — 5173).
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# id категории -> название и комиссия Kaspi с НДС (доля от цены продажи).
# Источник: guide.kaspi.kz/partner/ru/shop/conditions/q4467
#   большинство категорий (дом, одежда, спорт, авто и др.) — 12,5% с НДС (10,9% без НДС);
#   аксессуары, телефоны, гаджеты, ТВ/аудио — 12,5–15,5% с НДС, взята нижняя граница;
#   ювелирка — 15,5%; продукты, зоотовары, аптека — от 7,3%.
CATEGORIES = {
    "electronics": {"name": "Электроника и аксессуары", "commission": 0.125},
    "home": {"name": "Дом и кухня", "commission": 0.125},
    "beauty": {"name": "Красота и здоровье", "commission": 0.125},
    "kids": {"name": "Детские товары", "commission": 0.125},
    "sport": {"name": "Спорт и отдых", "commission": 0.125},
}

# Для настоящего магазина: комиссия по коду категории Kaspi (как в заказе, например
# "Master - Brushes and applicators"). Если категории нет в списке — DEFAULT_COMMISSION,
# для ювелирки — 15,5%.
DEFAULT_COMMISSION = 0.125
COMMISSION_OVERRIDES: dict[str, float] = {}

# Kaspi Доставка, тарифы с 01.01.2026, ₸ за заказ без НДС.
# Источник: guide.kaspi.kz/cdn/content/pay/product/documents/Magazin/stoimost-servisa-kaspi-dostavka-s-1-1-2026.pdf
# Город продавца: заказы из этого города идут по тарифу «по городу», остальные — «по Казахстану».
SELLER_CITY = "Алматы"

# Заказы до 10 000 ₸ — по сумме заказа: (сумма меньше, тариф по городу, тариф по Казахстану).
DELIVERY_SMALL_ORDER_LIMIT = 10_000
DELIVERY_SMALL_TIERS = [
    (1_000, 49.14, 49.14),
    (3_000, 149.14, 149.14),
    (5_000, 199.14, 199.14),
    (10_000, 699.14, 799.14),
]

# Заказы от 10 000 ₸ — по весу заказа: (вес до, кг; по городу; по Казахстану; Express). None — без верхней границы.
DELIVERY_WEIGHT_TIERS = [
    (5, 1_099.14, 1_299.14, 1_699.14),
    (15, 1_349.14, 1_699.14, 1_849.14),
    (30, 2_299.14, 3_599.14, 3_149.14),
    (60, 2_899.14, 5_649.14, 3_599.14),
    (100, 4_149.14, 8_549.14, 5_599.14),
    (None, 6_449.14, 11_999.14, 8_449.14),
]

# Налог от выручки (упрощённая декларация). Укажите ставку своего режима.
TAX_RATE = 0.04

# Штрафы: продавец работает аккуратно, штрафов нет. Поставьте > 0, чтобы смоделировать их.
PENALTY_PROBABILITY = 0.0
PENALTY_AMOUNTS = [1_000, 2_000, 3_000]

# Исходы заказов.
CANCEL_RATE = 0.05
RETURN_RATE = 0.03

CITIES = ["Алматы", "Астана", "Шымкент", "Караганда", "Актобе", "Павлодар", "Усть-Каменогорск", "Атырау"]

# Вымышленные продавцы-конкуренты.
COMPETITOR_NAMES = [
    "TechnoPoint KZ", "DalaShop", "NurTrade", "Astana Gadget", "Alem Store",
    "Bazar Online", "Qazaq Retail", "Smart Price", "Zhuldyz Shop", "Shymkent Market",
    "Steppe Goods", "Arman Trade",
]

# Окно для расчёта средней скорости продаж (остатки, «дней до нуля»).
SALES_VELOCITY_DAYS = 14
