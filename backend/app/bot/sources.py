"""Откуда бот берёт цены конкурентов.

Сейчас — из тестовых данных. Источник с kaspi.kz подключается здесь же, когда
проверим его на настоящем магазине: остальной код бота от источника не зависит.
"""

from typing import Protocol

from app.data.models import Dataset
from app.services.market import market_day


class CompetitorSource(Protocol):
    name: str

    def prices(self, product_id: int) -> list[int]:
        """Цены других продавцов на карточке товара, ₸ (без нашей цены)."""
        ...


class TestCompetitorSource:
    name = "Тестовые данные"

    def __init__(self, ds: Dataset):
        self.ds = ds

    def prices(self, product_id: int) -> list[int]:
        return list(market_day(self.ds, product_id).competitor_prices.values())
