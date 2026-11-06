import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  Alert,
  BotLogEntry,
  BotRule,
  BotStatus,
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

/** Выбранный магазин берётся из адреса страницы (?shop=). */
export const currentShop = () => new URLSearchParams(window.location.search).get('shop') ?? 'demo'

async function get<T>(path: string, params: Params = {}): Promise<T> {
  const query = new URLSearchParams()
  query.set('shop', currentShop())
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

async function send<T>(method: 'POST' | 'PUT' | 'DELETE', path: string, body: unknown = {}): Promise<T> {
  const response = await fetch(`/api${path}?shop=${encodeURIComponent(currentShop())}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: method === 'DELETE' ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    const detail = Array.isArray(data?.detail) ? data.detail.map((d: { msg: string }) => d.msg).join('; ') : data?.detail
    throw new Error(detail ?? `Ошибка ${response.status}`)
  }
  return response.json()
}

export interface Shop {
  id: string
  name: string
  kind: 'test' | 'kaspi'
  ready: boolean
  synced_at: string | null
  orders: number | null
}

export interface Source {
  source: 'test' | 'kaspi'
  name: string
  stock_known: boolean
  market_known: boolean
  synced_at: string | null
  products: number
  products_with_cost: number
}

export const useShops = () => useQuery({ queryKey: ['shops'], queryFn: () => get<Shop[]>('/shops') })
export const useSource = () => useQuery({ queryKey: ['source'], queryFn: () => get<Source>('/source'), retry: false })

export const useBot = () => useQuery({ queryKey: ['bot'], queryFn: () => get<BotStatus>('/bot'), refetchInterval: 30_000 })
export const useBotLog = () =>
  useQuery({ queryKey: ['bot-log'], queryFn: () => get<BotLogEntry[]>('/bot/log', { limit: 100 }), refetchInterval: 30_000 })

function useBotMutation<V>(fn: (vars: V) => Promise<unknown>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['bot'] })
      client.invalidateQueries({ queryKey: ['bot-log'] })
    },
  })
}

export const useSaveRule = () =>
  useBotMutation(({ id, rule }: { id: number; rule: BotRule }) => send('PUT', `/bot/products/${id}`, rule))
/** Закупка меняет прибыль везде (обзор, товары, бот) — после сохранения обновляем все данные. */
export const useSaveCost = () => {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, cost }: { id: number; cost: number | null }) => send('PUT', `/bot/products/${id}/cost`, { cost }),
    onSuccess: () => client.invalidateQueries(),
  })
}
export const useDeleteRule = () => useBotMutation((id: number) => send('DELETE', `/bot/products/${id}`))
export const useBotSwitch = () =>
  useBotMutation((body: { enabled: boolean; dry_run: boolean }) => send('POST', '/bot/switch', body))
export const useBotRun = () => useBotMutation(() => send('POST', '/bot/run'))
