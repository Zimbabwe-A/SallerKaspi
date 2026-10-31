import { useQuery } from '@tanstack/react-query'
import type {
  Alert,
  Breakdown,
  CategoryMarket,
  DailyPoint,
  Offers,
  PriceHistory,
  ProductDetail,
  ProductList,
  Settings,
  StockRow,
  Summary,
} from './types'
import { usePeriod } from '../lib/period'

type Params = Record<string, string | number | undefined | null>

async function get<T>(path: string, params: Params = {}): Promise<T> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  const url = query.size ? `/api${path}?${query}` : `/api${path}`
  const response = await fetch(url)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Ошибка ${response.status}`)
  }
  return response.json()
}

function usePeriodQuery<T>(path: string, extra: Params = {}) {
  const { from, to } = usePeriod()
  const params = { from, to, ...extra }
  return useQuery({ queryKey: [path, params], queryFn: () => get<T>(path, params) })
}

export const useSettings = () =>
  useQuery({ queryKey: ['settings'], queryFn: () => get<Settings>('/settings'), staleTime: Infinity })

export const useSummary = () => usePeriodQuery<Summary>('/summary')
export const useBreakdown = () => usePeriodQuery<Breakdown>('/breakdown')
export const useDailySales = () => usePeriodQuery<DailyPoint[]>('/sales/daily')
export const useProducts = (filters: Params = {}) => usePeriodQuery<ProductList>('/products', filters)
export const useProduct = (id: number) => usePeriodQuery<ProductDetail>(`/products/${id}`)
export const usePriceHistory = (id: number) => usePeriodQuery<PriceHistory>(`/market/products/${id}/history`)

export const useStock = () => useQuery({ queryKey: ['stock'], queryFn: () => get<StockRow[]>('/stock') })
export const useOffers = (id: number) =>
  useQuery({ queryKey: ['offers', id], queryFn: () => get<Offers>(`/market/products/${id}/offers`) })
export const useMarketCategories = () =>
  useQuery({ queryKey: ['market-categories'], queryFn: () => get<CategoryMarket[]>('/market/categories') })
export const useAlerts = () => useQuery({ queryKey: ['alerts'], queryFn: () => get<Alert[]>('/market/alerts') })
