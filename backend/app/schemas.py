from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


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


DeliveryType = Literal["city", "kazakhstan", "express"]
WeightTier = Literal["to_5", "to_15", "to_30", "to_60", "to_100", "over_100"]


class EconomicsInput(BaseModel):
    purchase_cost: int = Field(ge=0)  # закупка за 1 шт
    other_cost: int = Field(default=0, ge=0)  # упаковка, доставка до склада и прочее за 1 шт
    price: int = Field(gt=0)
    commission_pct: float = Field(default=12.5, ge=0, le=50)  # с НДС
    delivery_type: DeliveryType = "city"
    weight: WeightTier = "to_5"
    tax_pct: float = Field(default=4, ge=0, le=50)
    target_margin_pct: float = Field(default=15, ge=0, le=90)


class Economics(BaseModel):
    price: int
    commission: int
    delivery: int
    tax: int
    cost: int
    profit: int
    margin_pct: float
    roi_pct: float | None
    break_even_price: int | None
    target_price: int | None


class CandidateInput(EconomicsInput):
    name: str = Field(min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    sellers: int = Field(default=1, ge=1)
    reviews: int = Field(default=0, ge=0)
    min_price: int | None = Field(default=None, gt=0)  # самая низкая цена на карточке
    notes: str = Field(default="", max_length=1000)


class ScoreParts(BaseModel):
    margin: int
    demand: int
    competition: int


class Candidate(CandidateInput):
    id: int
    updated_at: date
    economics: Economics
    score: int  # 0–100
    score_parts: ScoreParts
    verdict: Literal["good", "check", "reject"]
    profit_at_min_price: int | None
    warnings: list[str]


class CommissionPreset(BaseModel):
    id: str
    label: str
    pct: float


class Option(BaseModel):
    id: str
    label: str


class Tariffs(BaseModel):
    commission_presets: list[CommissionPreset]
    delivery_types: list[Option]
    weight_tiers: list[Option]
    default_tax_pct: float
    default_target_margin_pct: float
    commission_source: str
    delivery_source: str
    checked_at: date
