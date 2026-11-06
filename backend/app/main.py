import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.data import store
from app.data.store import get_dataset
from app.bot import runner, storage
from app.deps import DatasetDep
from app.routers import bot, internal, market, waybills


@asynccontextmanager
async def lifespan(_: FastAPI):
    ds = get_dataset()  # генерируем данные при старте, а не на первом запросе
    storage.write_feed(runner.render_feed(ds, storage.load_state()))  # прайс-лист готов сразу
    task = asyncio.create_task(runner.loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="Kaspi Seller Analytics — тестовый API",
    description="Mock-сервер с генерируемыми данными. Контракт совпадает с будущим боевым API.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Labels"],
)

app.include_router(internal.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(bot.router, prefix="/api")
app.include_router(bot.write, prefix="/api")
app.include_router(waybills.router, prefix="/api")


@app.get("/api/health", tags=["Служебное"])
def health():
    ds = get_dataset()
    return {"status": "ok", "data_start": ds.start, "data_end": ds.end,
            "products": len(ds.products), "orders": len(ds.orders)}


@app.get("/api/shops", tags=["Служебное"], summary="Магазины для выбора на сайте")
def get_shops():
    return store.shops()


@app.get("/api/source", tags=["Служебное"], summary="Откуда данные выбранного магазина")
def get_source(ds: DatasetDep):
    from app import economics
    with_cost = sum(1 for p in ds.products.values() if economics.cost_of(ds, p) is not None)
    return {"source": ds.source, "name": ds.name, "stock_known": ds.stock_known,
            "market_known": ds.market_known, "synced_at": ds.synced_at,
            "data_start": ds.start, "data_end": ds.end,
            "products": len(ds.products), "products_with_cost": with_cost,
            "market_synced_at": _market_time(ds), "auto_update": _auto_update(ds)}


def _market_time(ds):
    if ds.source == "test":
        return None
    from app.kaspi.market import load_market
    snapshot = load_market(ds.shop_id)
    return snapshot.get("synced_at") if snapshot else None


def _auto_update(ds):
    if ds.source == "test":
        return None
    from app.kaspi.autoupdate import load_status
    return load_status()
