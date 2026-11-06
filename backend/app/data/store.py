"""Откуда берутся данные сайта: демо-магазин (генератор) или настоящий магазин Kaspi (кэш заказов)."""

from functools import lru_cache

from app import config
from app.data.generator import generate
from app.data.models import Dataset

DEMO = "demo"
MAIN = "main"


def shops() -> list[dict]:
    """Список магазинов для выбора на сайте. Токены сюда не попадают."""
    from app.kaspi.sync import cache_file, load_cache

    result = [{"id": DEMO, "name": "Демо-магазин", "kind": "test", "ready": True, "synced_at": None, "orders": None}]
    if config.KASPI_API_TOKEN:
        cache = load_cache(MAIN) if cache_file(MAIN).exists() else {"orders": {}, "synced_at": None}
        result.append({
            "id": MAIN, "name": config.KASPI_COMPANY if config.KASPI_COMPANY != "Мой магазин" else "Мой магазин Kaspi",
            "kind": "kaspi", "ready": bool(cache["orders"]), "synced_at": cache.get("synced_at"),
            "orders": len(cache["orders"]),
        })
    return result


@lru_cache(maxsize=1)
def _demo() -> Dataset:
    return generate()


@lru_cache(maxsize=4)
def _kaspi(shop_id: str, mtime: float, costs_mtime: float, offers_mtime: float = 0.0, market_mtime: float = 0.0) -> Dataset:
    from app.kaspi.dataset import build
    name = next((s["name"] for s in shops() if s["id"] == shop_id), shop_id)
    return build(shop_id, name)


def get_dataset(shop: str = DEMO) -> Dataset:
    """Данные магазина. Кэш настоящего магазина перечитывается, когда файл заказов обновился."""
    if shop == DEMO:
        return _demo()
    from app.kaspi.sync import cache_file
    if shop != MAIN or not config.KASPI_API_TOKEN:
        raise LookupError("Магазин не найден")
    path = cache_file(shop)
    if not path.exists():
        raise LookupError("Заказы ещё не загружены. Запустите в Терминале: python -m app.kaspi.sync")
    costs = path.parent / "costs.json"
    offers = path.parent / "offers.json"
    market = path.parent / "market.json"
    return _kaspi(shop, path.stat().st_mtime, costs.stat().st_mtime if costs.exists() else 0.0,
                  offers.stat().st_mtime if offers.exists() else 0.0, market.stat().st_mtime if market.exists() else 0.0)
