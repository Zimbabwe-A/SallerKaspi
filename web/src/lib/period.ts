import { useSearchParams } from 'react-router'

/** Период хранится в адресе (?from=&to=), чтобы ссылку можно было отправить и обновить страницу. */
export function usePeriod() {
  const [params, setParams] = useSearchParams()
  const from = params.get('from') ?? undefined
  const to = params.get('to') ?? undefined

  const setPeriod = (next: { from?: string; to?: string }) => {
    setParams((current) => {
      const updated = new URLSearchParams(current)
      for (const key of ['from', 'to'] as const) {
        if (next[key]) updated.set(key, next[key]!)
        else updated.delete(key)
      }
      return updated
    })
  }

  return { from, to, setPeriod }
}

/** Строка ?from=&to= текущего периода — чтобы ссылки между страницами его не теряли. */
export function usePeriodSearch() {
  const { from, to } = usePeriod()
  const query = new URLSearchParams()
  if (from) query.set('from', from)
  if (to) query.set('to', to)
  return query.size ? `?${query}` : ''
}

export function shiftDate(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}
