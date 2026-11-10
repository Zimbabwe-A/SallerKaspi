"""Накладные: склеить много PDF Kaspi в один для печати на термопринтере.

Файлы обрабатываются в памяти и сразу возвращаются — на диск ничего не пишется
(в накладных есть имена и адреса покупателей). Для владельца магазина запоминаем только
номера заказов (и отпечатки страниц) уже напечатанных накладных, чтобы не печатать их повторно.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Request, Response, UploadFile

from app import auth, config
from app.waybills import LAYOUTS, WaybillError, build


def same_site_only(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in config.CORS_ORIGINS:
        raise HTTPException(status_code=403, detail="Запрос не с сайта аналитики")


router = APIRouter(prefix="/waybills", tags=["Накладные"], dependencies=[Depends(same_site_only)])


@router.post("/merge", summary="Склеить накладные в один PDF")
async def merge_waybills(
    files: Annotated[list[UploadFile], File(description="PDF-накладные Kaspi")],
    size: Annotated[str, Form(description="Вариант печати: a4x1, a4x4, a4x8, a4x9, 75x120, 100x150, join")] = "75x120",
    skip_printed: Annotated[bool, Form(description="Не печатать уже напечатанные накладные (только у владельца)")] = True,
    sk_session: Annotated[str | None, Cookie()] = None,
):
    if size not in LAYOUTS:
        raise HTTPException(status_code=400, detail="Неизвестный вариант печати")
    user = auth.current_user(sk_session)
    history = bool(user and "waybill_history" in user["features"])
    data = [(f.filename or "", await f.read()) for f in files]
    try:
        built = build(data, size, skip=auth.printed_keys(user["id"]) if history and skip_printed else None)
    except WaybillError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    if built.count == 0:
        raise HTTPException(
            status_code=409,
            detail=f"Все эти накладные уже напечатаны ({built.skipped}). Новых нет.",
            headers={"X-Skipped": str(built.skipped)},
        )
    if history:
        auth.remember_printed(user["id"], built.keys)
    return Response(
        content=built.pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="nakladnye_{built.count}.pdf"',
            "Cache-Control": "no-store",
            "X-Labels": str(built.count),
            "X-Skipped": str(built.skipped),
        },
    )
