"""Настройки mock-сервера.

Ставки комиссий, доставки и налога — заглушки для тестовых данных.
Перед подключением реального магазина сверьте их с актуальными тарифами Kaspi
и вашим налоговым режимом.
"""

SEED = 42
HISTORY_DAYS = 180
CURRENCY = "KZT"

# Откуда React-приложению разрешено ходить в API (Vite по умолчанию — 5173).
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# id категории -> название и комиссия Kaspi (доля от цены продажи).
CATEGORIES = {
    "electronics": {"name": "Электроника и аксессуары", "commission": 0.12},
    "home": {"name": "Дом и кухня", "commission": 0.10},
    "beauty": {"name": "Красота и здоровье", "commission": 0.11},
    "kids": {"name": "Детские товары", "commission": 0.09},
    "sport": {"name": "Спорт и отдых", "commission": 0.10},
}

# Стоимость доставки за заказ по цене товара: (цена до, ₸ за доставку). None — без верхней границы.
DELIVERY_TIERS = [
    (5_000, 600),
    (15_000, 900),
    (50_000, 1_500),
    (None, 2_500),
]

# Налог от выручки (упрощённая декларация). Укажите ставку своего режима.
TAX_RATE = 0.04

# Доля заказов со штрафом и возможные суммы штрафа, ₸.
PENALTY_PROBABILITY = 0.004
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
