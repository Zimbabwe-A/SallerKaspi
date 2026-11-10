// Типы ответов API. Повторяют backend/app/schemas.py — меняйте их вместе.

export interface Period {
  start: string
  end: string
}

export interface Totals {
  orders: number
  units: number
  cancelled: number
  returned: number
  revenue: number
  commission: number
  delivery: number
  penalties: number
  kaspi_total: number
  payout: number
  cost: number
  profit: number
  tax: number
  profit_after_tax: number
  avg_check: number
  pending_orders: number
  pending_amount: number
}

export interface Summary {
  period: Period
  previous_period: Period
  current: Totals
  previous: Totals
  change_pct: Record<string, number | null>
}

export interface BreakdownItem {
  key: string
  label: string
  amount: number
  share: number
}

export interface Breakdown {
  period: Period
  revenue: number
  items: BreakdownItem[]
}

export interface DailyPoint {
  date: string
  orders: number
  units: number
  revenue: number
  payout: number
  profit: number
}

export interface Category {
  id: string
  name: string
  commission: number
}

export type StockStatus = 'out' | 'critical' | 'low' | 'ok' | 'unknown'
export type Abc = 'A' | 'B' | 'C'

export interface ProductRow {
  id: number
  sku: string
  name: string
  category_id: string
  category_name: string
  price: number
  min_market_price: number
  price_position: number
  sellers: number
  units: number
  revenue: number
  kaspi_fees: number
  cost: number
  profit: number
  margin_pct: number | null
  abc: Abc | null
  stock: number
  days_of_cover: number | null
  stock_status: StockStatus
  kaspi_url: string | null
  image_url: string | null
  cost_price: number | null
  stock_entered: number | null
  rating: number
  reviews: number
}

export interface ProductList {
  period: Period
  total: number
  items: ProductRow[]
}

export interface UnitEconomics {
  price: number
  commission: number
  delivery: number
  cost: number
  tax: number
  profit: number
  margin_pct: number
}

export interface ProductDetail {
  period: Period
  product: ProductRow
  cost_price: number
  commission_rate: number
  unit_economics: UnitEconomics
  daily: DailyPoint[]
}

export interface StockRow {
  product_id: number
  sku: string
  name: string
  category_id: string
  quantity: number
  avg_daily_sales: number
  days_of_cover: number | null
  status: StockStatus
  incoming_quantity: number
  incoming_date: string | null
  idle_days: number | null
  cost: number | null
  frozen: number | null
  reorder: number
}

export interface Offer {
  seller_id: string
  seller_name: string
  is_me: boolean
  price: number
  position: number
  rating: number | null
  delivery_days: number | null
}

export interface Offers {
  product_id: number
  date: string
  my_price: number
  my_position: number
  sellers: number
  min_price: number
  gap_to_min: number
  gap_to_min_pct: number
  offers: Offer[]
}

export interface PricePoint {
  date: string
  my_price: number
  min_price: number
  avg_price: number
  max_price: number
  rating: number
  reviews: number
}

export interface PriceHistory {
  product_id: number
  period: Period
  points: PricePoint[]
}

export interface CategoryMarket {
  id: string
  name: string
  products: number
  avg_sellers: number
  price_index: number
  cheapest_share: number
  revenue_30d: number
}

export type AlertSeverity = 'high' | 'medium' | 'low'

export interface Alert {
  type: 'lost_lowest_price' | 'competitor_undercut' | 'stock_low' | 'rating_drop'
  severity: AlertSeverity
  date: string
  product_id: number
  sku: string
  product_name: string
  message: string
}

export interface Settings {
  currency: string
  tax_rate: number
  categories: Category[]
  delivery: {
    seller_city: string
    small_order_limit: number
    by_order_sum: DeliveryTier[]
    by_weight: DeliveryTier[]
  }
  data_period: Period
}

export type ProductSort = 'revenue' | 'profit' | 'units' | 'margin_pct' | 'stock' | 'days_of_cover' | 'name'

export interface DeliveryTier {
  up_to: number | null
  city: number
  country: number
  express: number | null
}

export type BotStrategy = 'first' | 'second' | 'top3' | 'top5'

export interface BotRule {
  enabled: boolean
  min_price: number
  max_price: number
  step: number
  strategy: BotStrategy
  protect: boolean
}

export interface BotRow {
  product_id: number
  sku: string
  name: string
  price: number
  min_competitor: number | null
  sellers: number
  rule: BotRule | null
  position: number
  next_price: number | null
  next_position: number | null
  next_kind: 'target' | 'min' | 'max' | 'alone' | null
  next_reason: string | null
  cost: number | null
  break_even: number | null
  profit_now: number | null
  next_profit: number | null
  first_place_price: number | null
  first_place_profit: number | null
  units_30d: number
  stock: number | null
  last_time: string | null
  last_reason: string | null
  last_kind: string | null
}

export interface BotCounts {
  total: number
  in_bot: number
  first: number
  second: number
  at_min: number
  at_max: number
}

export interface BotStatus {
  enabled: boolean
  dry_run: boolean
  night_pause: boolean
  last_run: string | null
  interval_seconds: number
  source: string
  feed_path: string
  feed_ready: boolean
  counts: BotCounts
  rows: BotRow[]
}

export interface BotLogEntry {
  time: string
  product_id: number
  sku: string
  name: string
  old_price: number
  new_price: number
  reason: string
  dry_run: boolean
}

export interface ShipItem {
  sku: string
  name: string
  qty: number
}

export interface ShipOrder {
  code: string
  created: string
  town: string | null
  express: boolean
  assembled: boolean
  ship_by: string | null
  has_waybill: boolean
  cancelling: boolean
  total: number
  items: ShipItem[]
}

export interface ToShip {
  orders: ShipOrder[]
  pick_list: (ShipItem & { orders: number })[]
  count: number
  due_today: number
  not_assembled: number
  cancelling: number
  dates_known: boolean
}
