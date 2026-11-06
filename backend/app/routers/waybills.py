"""Накладные: склеить много PDF Kaspi в один для печати на термопринтере.

Файлы обрабатываются в памяти и сразу возвращаются — на диск ничего не пишется
(в накладных есть имена и адреса покупателей).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile

from app import config
from app.waybills import LAYOUTS, WaybillError, merge


def same_site_only(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in config.CORS_ORIGINS:
        raise HTTPException(status_code=403, detail="Запрос не с сайта аналитики")


router = APIRouter(prefix="/waybills", tags=["Накладные"], dependencies=[Depends(same_site_only)])


@router.post("/merge", summary="Склеить накладные в один PDF")
async def merge_waybills(
    files: Annotated[list[UploadFile], File(description="PDF-накладные Kaspi")],
    size: Annotated[str, Form(description="Вариант печати: a4x1, a4x4, a4x8, a4x9, 75x120, 100x150, join")] = "75x120",
):
    if size not in LAYOUTS:
        raise HTTPException(status_code=400, detail="Неизвестный вариант печати")
    data = [await f.read() for f in files]
    try:
        pdf, count = merge(data, size)
    except WaybillError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="nakladnye_{count}.pdf"',
            "Cache-Control": "no-store",
            "X-Labels": str(count),
        },
    )
