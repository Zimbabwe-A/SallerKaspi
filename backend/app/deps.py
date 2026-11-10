from datetime import date, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Query

from app import auth

from app.data import store
from app.data.models import Dataset


def get_dataset(
    shop: Annotated[str, Query(description="Магазин: demo или main")] = store.DEMO,
    sk_session: Annotated[str | None, Cookie()] = None,
) -> Dataset:
    # Демо открыто всем, настоящий магазин — только аккаунтам, которым он открыт.
    if shop != store.DEMO:
        user = auth.current_user(sk_session)
        if not user:
            raise HTTPException(status_code=401, detail="Войдите в аккаунт")
        if shop not in user["shops"]:
            raise HTTPException(status_code=403, detail="Этот магазин вам не открыт")
    try:
        return store.get_dataset(shop)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


DatasetDep = Annotated[Dataset, Depends(get_dataset)]


def period(
    ds: DatasetDep,
    start: Annotated[date | None, Query(alias="from", description="Начало периода, YYYY-MM-DD")] = None,
    end: Annotated[date | None, Query(alias="to", description="Конец периода, YYYY-MM-DD")] = None,
) -> tuple[date, date]:
    """Период запроса. По умолчанию — последние 7 дней; обрезается по границам данных."""
    end = min(end or ds.end, ds.end)
    start = max(start or end - timedelta(days=6), ds.start)
    if start > end:
        raise HTTPException(status_code=400, detail="Параметр from должен быть не позже to")
    return start, end


PeriodDep = Annotated[tuple[date, date], Depends(period)]


def product_id_checked(product_id: int, ds: DatasetDep) -> int:
    if product_id not in ds.products:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product_id


ProductIdDep = Annotated[int, Depends(product_id_checked)]
