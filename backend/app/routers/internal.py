from typing import Literal

from fastapi import APIRouter

from app import config, schemas
from app.deps import DatasetDep, PeriodDep, ProductIdDep
from app.services import internal

router = APIRouter(tags=["Внутренняя аналитика"])

SortField = Literal["revenue", "profit", "units", "margin_pct", "stock", "days_of_cover", "name"]


@router.get("/summary", response_model=schemas.Summary, summary="KPI за период и сравнение с прошлым")
def get_summary(ds: DatasetDep, period: PeriodDep):
    return internal.summary(ds, *period)


@router.get("/breakdown", response_model=schemas.Breakdown, summary="Куда уходит цена")
def get_breakdown(ds: DatasetDep, period: PeriodDep):
    return internal.breakdown(ds, *period)


@router.get("/sales/daily", response_model=list[schemas.DailyPoint], summary="Продажи по дням")
def get_sales_daily(ds: DatasetDep, period: PeriodDep):
    return internal.daily(ds, *period)


@router.get("/products", response_model=schemas.ProductList, summary="Товары с юнит-экономикой и ABC")
def get_products(
    ds: DatasetDep,
    period: PeriodDep,
    category: str | None = None,
    search: str | None = None,
    abc: Literal["A", "B", "C"] | None = None,
    sort: SortField = "revenue",
    order: Literal["asc", "desc"] = "desc",
):
    rows = internal.product_rows(ds, *period)
    if category:
        rows = [r for r in rows if r.category_id == category]
    if search:
        needle = search.lower()
        rows = [r for r in rows if needle in r.name.lower() or needle in r.sku.lower()]
    if abc:
        rows = [r for r in rows if r.abc == abc]
    # Пустые значения (None) всегда в конце списка.
    present = [r for r in rows if getattr(r, sort) is not None]
    missing = [r for r in rows if getattr(r, sort) is None]
    present.sort(key=lambda r: getattr(r, sort), reverse=order == "desc")
    return schemas.ProductList(period=schemas.Period(start=period[0], end=period[1]),
                               total=len(rows), items=present + missing)


@router.get("/products/{product_id}", response_model=schemas.ProductDetail, summary="Карточка товара")
def get_product(ds: DatasetDep, product_id: ProductIdDep, period: PeriodDep):
    return internal.product_detail(ds, product_id, *period)


@router.get("/stock", response_model=list[schemas.StockRow], summary="Остатки и дней до нуля")
def get_stock(ds: DatasetDep):
    return internal.stock(ds)


@router.get("/categories", response_model=list[schemas.Category], summary="Категории")
def get_categories(ds: DatasetDep):
    return [schemas.Category(id=c.id, name=c.name, commission=c.commission) for c in ds.categories.values()]


@router.get("/settings", response_model=schemas.Settings, summary="Ставки и параметры расчёта")
def get_settings(ds: DatasetDep):
    return schemas.Settings(
        currency=config.CURRENCY,
        tax_rate=config.TAX_RATE,
        categories=get_categories(ds),
        delivery_tiers=[schemas.DeliveryTier(up_to=limit, fee=fee) for limit, fee in config.DELIVERY_TIERS],
        data_period=schemas.Period(start=ds.start, end=ds.end),
    )
