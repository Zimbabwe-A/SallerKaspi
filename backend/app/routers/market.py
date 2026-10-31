from typing import Literal

from fastapi import APIRouter

from app import schemas
from app.deps import DatasetDep, PeriodDep, ProductIdDep
from app.services import alerts, market

router = APIRouter(prefix="/market", tags=["Внешняя аналитика"])


@router.get("/products/{product_id}/offers", response_model=schemas.Offers,
            summary="Продавцы на карточке товара сейчас")
def get_offers(ds: DatasetDep, product_id: ProductIdDep):
    return market.offers(ds, product_id)


@router.get("/products/{product_id}/history", response_model=schemas.PriceHistory,
            summary="История цен, рейтинга и отзывов")
def get_history(ds: DatasetDep, product_id: ProductIdDep, period: PeriodDep):
    return market.price_history(ds, product_id, *period)


@router.get("/categories", response_model=list[schemas.CategoryMarket], summary="Сводка рынка по категориям")
def get_categories(ds: DatasetDep):
    return market.categories(ds)


@router.get("/alerts", response_model=list[schemas.Alert], summary="Сигналы по ценам, рейтингу и остаткам")
def get_alerts(ds: DatasetDep, severity: Literal["high", "medium", "low"] | None = None):
    items = alerts.alerts(ds)
    return [a for a in items if a.severity == severity] if severity else items
