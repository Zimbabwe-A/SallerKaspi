from datetime import date, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Query

from app.data.models import Dataset
from app.data.store import get_dataset

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
