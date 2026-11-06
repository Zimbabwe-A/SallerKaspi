"""Отдельный мини-сервер, который отдаёт Kaspi только XML-прайс-лист.

Это единственное, что можно открыть в интернет (через туннель или сервер).
Аналитика, бот, токен и данные покупателей сюда не входят.

Ссылка: /kaspi/<секрет>/price.xml. Без правильного секрета — 404, как будто файла нет.

Запуск: uvicorn app.feed_app:app --port 8001
"""

import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from app.bot import storage


@asynccontextmanager
async def lifespan(_: FastAPI):
    print(f"\n  Ссылка для Kaspi (путь): /kaspi/{storage.feed_secret()}/price.xml\n", flush=True)
    yield


# Никаких страниц документации наружу.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.get("/kaspi/{secret}/price.xml", include_in_schema=False)
def price_list(secret: str) -> Response:
    if not hmac.compare_digest(secret.encode(), storage.feed_secret().encode()):
        return Response(status_code=404)
    xml = storage.read_feed()
    if xml is None:
        return Response(status_code=404)
    return Response(
        content=xml,
        media_type="application/xml; charset=utf-8",
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex", "X-Content-Type-Options": "nosniff"},
    )


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
               include_in_schema=False)
def everything_else(path: str) -> Response:
    return Response(status_code=404)
