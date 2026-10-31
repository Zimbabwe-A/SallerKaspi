from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.data.store import get_dataset
from app.routers import internal, market


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_dataset()  # генерируем данные при старте, а не на первом запросе
    yield


app = FastAPI(
    title="Kaspi Seller Analytics — тестовый API",
    description="Mock-сервер с генерируемыми данными. Контракт совпадает с будущим боевым API.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(internal.router, prefix="/api")
app.include_router(market.router, prefix="/api")


@app.get("/api/health", tags=["Служебное"])
def health():
    ds = get_dataset()
    return {"status": "ok", "data_start": ds.start, "data_end": ds.end,
            "products": len(ds.products), "orders": len(ds.orders)}
