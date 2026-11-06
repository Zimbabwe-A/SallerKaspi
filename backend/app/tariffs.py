"""Тарифы Магазина на Kaspi.kz для калькулятора и подбора ниш.

Источники (проверено 06.11.2026, перед важными решениями сверяйте заново):
- комиссия: «Тарифы Магазина на Kaspi.kz 2026», guide.kaspi.kz, таблица по категориям;
- доставка: guide.kaspi.kz/partner/ru/shop/delivery/shipping/q2288, тарифы с 1 января 2026 года без НДС.
Не связаны с заглушками в config.py: те нужны только для генератора тестовых данных.
"""

COMMISSION_SOURCE = "https://guide.kaspi.kz/cdn/content/pay/product/documents/Magazin/Tarify_Magazina_na_Kaspi_kz_2026.pdf"
DELIVERY_SOURCE = "https://guide.kaspi.kz/partner/ru/shop/delivery/shipping/q2288"
CHECKED_AT = "2026-11-06"

# Kaspi списывает доставку с учётом НДС; комиссия в пресетах уже указана с НДС.
VAT_RATE = 0.16

# Налог с выручки по умолчанию, %. Укажите ставку своего режима.
DEFAULT_TAX_PCT = 4.0
DEFAULT_TARGET_MARGIN_PCT = 15.0

COMMISSION_PRESETS = [
    {"id": "standard", "label": "Большинство товаров", "pct": 12.5},
    {"id": "accessories", "label": "Аксессуары, украшения, чехлы и аксессуары для телефонов", "pct": 15.5},
    {"id": "food_medicine", "label": "Продукты питания, лекарства", "pct": 7.3},
]

DELIVERY_TYPES = {"city": "По городу", "kazakhstan": "По Казахстану", "express": "Express"}

# Заказ до 10 000 ₸: тариф зависит только от суммы. (сумма до, тариф по типам доставки)
SMALL_ORDER_TIERS = [
    (1_000, {"city": 49, "kazakhstan": 49, "express": 49}),
    (3_000, {"city": 149, "kazakhstan": 149, "express": 149}),
    (5_000, {"city": 199, "kazakhstan": 199, "express": 199}),
    (10_000, {"city": 699, "kazakhstan": 799, "express": 799}),
]

# Заказ от 10 000 ₸: тариф зависит от веса.
WEIGHT_TIERS = {
    "to_5": {"label": "до 5 кг", "fees": {"city": 1_099, "kazakhstan": 1_299, "express": 1_699}},
    "to_15": {"label": "5–15 кг", "fees": {"city": 1_349, "kazakhstan": 1_699, "express": 1_849}},
    "to_30": {"label": "15–30 кг", "fees": {"city": 2_299, "kazakhstan": 3_599, "express": 3_149}},
    "to_60": {"label": "30–60 кг", "fees": {"city": 2_899, "kazakhstan": 5_649, "express": 3_599}},
    "to_100": {"label": "60–100 кг", "fees": {"city": 4_149, "kazakhstan": 8_549, "express": 5_599}},
    "over_100": {"label": "свыше 100 кг", "fees": {"city": 6_449, "kazakhstan": 11_999, "express": 8_449}},
}


def delivery_fee(price: float, delivery_type: str, weight: str) -> int:
    """Стоимость доставки заказа для продавца, ₸ с НДС."""
    for limit, fees in SMALL_ORDER_TIERS:
        if price < limit:
            return round(fees[delivery_type] * (1 + VAT_RATE))
    return round(WEIGHT_TIERS[weight]["fees"][delivery_type] * (1 + VAT_RATE))
