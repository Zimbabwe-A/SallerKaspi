"""Закупочные цены таблицей: выгрузить в Excel, заполнить, загрузить обратно.

Хранится только у вас (var/shops/<магазин>/costs.json). В Kaspi ничего не отправляется.
"""

import math
import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from app import economics
from app.deps import DatasetDep
from app.routers.waybills import same_site_only
from app.xlsx import TableError, read_table, write_xlsx

router = APIRouter(prefix="/costs", tags=["Закупочные цены"])
write = APIRouter(prefix="/costs", tags=["Закупочные цены"], dependencies=[Depends(same_site_only)])

HEADER = ["Артикул", "Название", "Закупка, ₸", "Цена на Kaspi, ₸", "Остаток, шт"]
SKU_WORDS = ("артикул", "sku", "код товара")
COST_WORDS = ("закуп", "себестоим", "cost")


@router.get("/export.xlsx", summary="Скачать закупочные цены в Excel")
def export_costs(ds: DatasetDep):
    from app.services.market import market_day

    rows: list[list] = [HEADER]
    for p in sorted(ds.products.values(), key=lambda p: p.name):
        rows.append([p.sku, p.name, economics.cost_of(ds, p), market_day(ds, p.id).my_price, economics.stock_of(ds, p)])
    data = write_xlsx(rows, "Закупка", widths=[22, 60, 14, 16, 12])
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="zakupka_{date.today():%Y-%m-%d}.xlsx"', "Cache-Control": "no-store"},
    )


def parse_money(text: str) -> int | None:
    """«6 000», «6000,50», «6 000 ₸» → 6000 / 6001. Пусто → None."""
    raw = (text or "").strip()
    if raw in ("", "-", "—"):
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", raw).replace(",", ".")
    if not re.search(r"\d", cleaned):
        raise ValueError(f"не число: «{text}»")
    if cleaned.count(".") > 1:  # 6.000.50 → тысячи через точку
        head, _, tail = cleaned.rpartition(".")
        cleaned = head.replace(".", "") + "." + tail
    try:
        value = math.floor(float(cleaned) + 0.5)  # 1234,5 → 1235, как считают в магазине
    except ValueError:
        raise ValueError(f"не число: «{text}»") from None
    if value < 0 or value > 100_000_000:
        raise ValueError(f"странная сумма: «{text}»")
    return value


def _columns(rows: list[list[str]]) -> tuple[int, int, int]:
    """Номер строки заголовка, колонки артикула и закупки. Без заголовка — A и C, как в нашей выгрузке."""
    for n, row in enumerate(rows[:10]):
        low = [c.lower() for c in row]
        sku = next((i for i, c in enumerate(low) if any(w in c for w in SKU_WORDS)), None)
        cost = next((i for i, c in enumerate(low) if any(w in c for w in COST_WORDS)), None)
        if sku is not None and cost is not None:
            return n + 1, sku, cost
    return 0, 0, 2


@write.post("/import", summary="Загрузить закупочные цены из Excel или CSV")
async def import_costs(ds: DatasetDep, file: Annotated[UploadFile, File(description=".xlsx или .csv")]):
    try:
        rows = read_table(await file.read(), file.filename or "")
    except TableError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    if not rows:
        raise HTTPException(status_code=400, detail="Файл пустой")
    start, sku_col, cost_col = _columns(rows)
    by_sku = {p.sku: p for p in ds.products.values()}
    saved = economics.load_costs(ds.shop_id)
    changes: dict[str, int] = {}
    unchanged, empty, unknown, errors = 0, 0, [], []
    for n, row in enumerate(rows[start:], start=start + 1):
        sku = row[sku_col].strip() if sku_col < len(row) else ""
        if not sku:
            continue
        if sku.endswith(".0") and sku[:-2].isdigit():  # Excel хранит числовой артикул как 123.0
            sku = sku[:-2]
        product = by_sku.get(sku)
        if product is None:
            unknown.append(sku)
            continue
        try:
            cost = parse_money(row[cost_col] if cost_col < len(row) else "")
        except ValueError as error:
            errors.append(f"строка {n}: {error}")
            continue
        if cost is None:
            empty += 1  # пустую ячейку не считаем «стереть закупку»
            continue
        if saved.get(sku) == cost:
            unchanged += 1
            continue
        changes[sku] = cost
    economics.set_costs(ds.shop_id, changes)
    updated = len(changes)
    if not updated and not unchanged and not empty and unknown and not errors:
        raise HTTPException(status_code=400, detail="Ни один артикул не совпал с товарами магазина. "
                                                    "Проверьте, что в первой колонке — артикулы, как в выгрузке.")
    return {"updated": updated, "unchanged": unchanged, "empty": empty,
            "unknown": unknown[:20], "unknown_count": len(unknown), "errors": errors[:20]}
