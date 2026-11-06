from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    commission: float


@dataclass(frozen=True)
class Product:
    id: int
    sku: str
    name: str
    category_id: str
    cost_price: int
    base_price: int
    weight_kg: float
    base_daily: float  # средний спрос, шт/день — только для генерации
    kaspi_code: str | None = None  # код карточки на kaspi.kz (для ссылки и поиска конкурентов)
    image_url: str | None = None  # фото из кабинета


@dataclass(frozen=True)
class Order:
    id: int
    day: date
    product_id: int
    qty: int
    price: int
    status: str  # delivered | cancelled | returned | active (ещё в пути)
    city: str
    commission: int
    delivery: int
    penalty: int
    cost: int
    order_key: str = ""  # номер заказа Kaspi: в одном заказе бывает несколько товаров

    @property
    def revenue(self) -> int:
        return self.price * self.qty if self.status == "delivered" else 0


@dataclass(frozen=True)
class Competitor:
    id: str
    name: str
    rating: float
    delivery_days: int


@dataclass(frozen=True)
class MarketDay:
    day: date
    my_price: int
    competitor_prices: dict[str, int]
    rating: float
    reviews: int


@dataclass
class StockState:
    product_id: int
    quantity: int
    incoming_quantity: int = 0
    incoming_date: date | None = None


@dataclass
class Dataset:
    start: date
    end: date
    categories: dict[str, Category]
    products: dict[int, Product]
    competitors: dict[str, Competitor]
    orders: list[Order]
    market: dict[int, list[MarketDay]]  # product_id -> история по дням
    stock: dict[int, StockState]
    orders_by_day: dict[date, list[Order]] = field(default_factory=dict)
    source: str = "test"  # test — тестовые данные, kaspi — настоящий магазин
    shop_id: str = "demo"
    name: str = "Демо-магазин"
    stock_known: bool = True  # есть ли данные об остатках
    market_known: bool = True  # есть ли цены конкурентов
    synced_at: str | None = None  # когда последний раз загружали из Kaspi

    def __post_init__(self) -> None:
        for order in self.orders:
            self.orders_by_day.setdefault(order.day, []).append(order)
