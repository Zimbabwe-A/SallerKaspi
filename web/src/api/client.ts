import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  Alert,
  Breakdown,
  Candidate,
  CandidateInput,
  CategoryMarket,
  DailyPoint,
  Economics,
  EconomicsInput,
  Offers,
  PriceHistory,
  ProductDetail,
  ProductList,
  Settings,
  StockRow,
  Summary,
  Tariffs,
} from './types'
import { usePeriod } from '../lib/period'

type Params = Record<string, string | number | undefined | null>

async function get<T>(path: string, params: Params = {}): Promise<T> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  const url = query.size ? `/api${path}?${query}` : `/api${path}`
  return parse<T>(await fetch(url))
}

async function send<T>(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return parse<T>(response)
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Ошибка ${response.status}`)
  }
  return response.status === 204 ? (undefined as T) : response.json()
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

export const useTariffs = () =>
  useQuery({ queryKey: ['tariffs'], queryFn: () => get<Tariffs>('/tariffs'), staleTime: Infinity })

export const useCalculation = (input: EconomicsInput | null) =>
  useQuery({
    queryKey: ['calculator', input],
    queryFn: () => send<Economics>('POST', '/calculator', input),
    enabled: input !== null,
    placeholderData: keepPreviousData,
  })

export const useCandidates = () =>
  useQuery({ queryKey: ['candidates'], queryFn: () => get<Candidate[]>('/candidates') })

export function useSaveCandidate() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: CandidateInput }) =>
      id === undefined
        ? send<Candidate>('POST', '/candidates', data)
        : send<Candidate>('PUT', `/candidates/${id}`, data),
    onSuccess: () => client.invalidateQueries({ queryKey: ['candidates'] }),
  })
}

export function useDeleteCandidate() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => send<void>('DELETE', `/candidates/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: ['candidates'] }),
  })
}
