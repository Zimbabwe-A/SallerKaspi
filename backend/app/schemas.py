from datetime import date
from typing import Literal

from pydantic import BaseModel


class Period(BaseModel):
    start: date
    end: date


class Totals(BaseModel):
    orders: int
    units: int
    cancelled: int
    returned: int
    revenue: int  # выручка по выкупленным заказам
    commission: int
    delivery: int
    penalties: int
    kaspi_total: int  # всё, что удержал Kaspi
    payout: int  # пришло на счёт
    cost: int  # себестоимость проданного
    profit: int  # до налога
    tax: int
    profit_after_tax: int
    avg_check: int


class Summary(BaseModel):
    period: Period
    previous_period: Period
    current: Totals
    previous: Totals
    change_pct: dict[str, float | None]


class BreakdownItem(BaseModel):
    key: str
    label: str
    amount: int
    share: float  # доля от выручки, %


class Breakdown(BaseModel):
    period: Period
    revenue: int
    items: list[BreakdownItem]


class DailyPoint(BaseModel):
    date: date
    orders: int
    units: int
    revenue: int
    payout: int
    profit: int


class Category(BaseModel):
    id: str
    name: str
    commission: float


StockStatus = Literal["out", "critical", "low", "ok"]


class ProductRow(BaseModel):
    id: int
    sku: str
    name: str
    category_id: str
    category_name: str
    price: int  # моя текущая цена
    min_market_price: int  # минимальная цена на карточке, включая мою
    price_position: int  # место моей цены среди продавцов (1 — самая низкая)
    sellers: int
    units: int
    revenue: int
    kaspi_fees: int
    cost: int
    profit: int
    margin_pct: float | None
    abc: Literal["A", "B", "C"] | None
    stock: int
    days_of_cover: float | None
    stock_status: StockStatus
    rating: float
    reviews: int


class ProductList(BaseModel):
    period: Period
    total: int
    items: list[ProductRow]


class UnitEconomics(BaseModel):
    price: int
    commission: int
    delivery: int
    cost: int
    tax: int
    profit: int
    margin_pct: float


class ProductDetail(BaseModel):
    period: Period
    product: ProductRow
    cost_price: int
    commission_rate: float
    unit_economics: UnitEconomics
    daily: list[DailyPoint]


class StockRow(BaseModel):
    product_id: int
    sku: str
    name: str
    category_id: str
    quantity: int
    avg_daily_sales: float
    days_of_cover: float | None
    status: StockStatus
    incoming_quantity: int
    incoming_date: date | None


class Offer(BaseModel):
    seller_id: str
    seller_name: str
    is_me: bool
    price: int
    position: int
    rating: float | None
    delivery_days: int | None


class Offers(BaseModel):
    product_id: int
    date: date
    my_price: int
    my_position: int
    sellers: int
    min_price: int
    gap_to_min: int  # насколько я дороже минимальной цены, ₸ (0 — я самый дешёвый)
    gap_to_min_pct: float
    offers: list[Offer]


class PricePoint(BaseModel):
    date: date
    my_price: int
    min_price: int
    avg_price: int
    max_price: int
    rating: float
    reviews: int


class PriceHistory(BaseModel):
    product_id: int
    period: Period
    points: list[PricePoint]


class CategoryMarket(BaseModel):
    id: str
    name: str
    products: int
    avg_sellers: float
    price_index: float  # моя цена к средней цене рынка, % (100 — как рынок)
    cheapest_share: float  # доля товаров, где я самый дешёвый, %
    revenue_30d: int


class Alert(BaseModel):
    type: Literal["lost_lowest_price", "competitor_undercut", "stock_low", "rating_drop"]
    severity: Literal["high", "medium", "low"]
    date: date
    product_id: int
    sku: str
    product_name: str
    message: str


class DeliveryTier(BaseModel):
    up_to: int | None
    fee: int


class Settings(BaseModel):
    currency: str
    tax_rate: float
    categories: list[Category]
    delivery_tiers: list[DeliveryTier]
    data_period: Period
