import { useDeferredValue, useState } from 'react'
import { Link } from 'react-router'
import { useProducts, useSettings, useSource } from '../api/client'
import type { Abc, ProductSort } from '../api/types'
import { Card, ErrorBox, PageTitle } from '../components/ui'
import { dec, int, money } from '../lib/format'
import { shiftDate, usePeriodSearch } from '../lib/period'

/** За какой срок показывать «Продано». */
const SALES_PERIODS = [
  { days: 1, label: 'Сегодня' },
  { days: 3, label: '3 дня' },
  { days: 7, label: 'Неделя' },
  { days: 30, label: 'Месяц' },
  { days: 90, label: '3 месяца' },
]

type SortKey = ProductSort | 'importance'

const COLUMNS: { key: SortKey | null; label: string; hint: string; align?: 'right' }[] = [
  { key: 'name', label: 'Товар', hint: 'артикул · категория' },
  { key: 'importance', label: 'Важность', hint: 'по выручке за месяц' },
  { key: null, label: 'Актуальная цена', hint: 'и место на Kaspi', align: 'right' },
  { key: 'units', label: 'Продано', hint: 'штук за выбранный срок', align: 'right' },
  { key: 'days_of_cover', label: 'Остаток', hint: 'на складе', align: 'right' },
]

const IMPORTANCE: Record<Abc, { label: string; className: string }> = {
  A: { label: 'Большая выручка', className: 'bg-ink text-page' },
  B: { label: 'Средняя выручка', className: 'bg-ink-2/15 text-ink' },
  C: { label: 'Маленькая выручка', className: 'bg-hover text-ink-2 ring-1 ring-line' },
}

function Importance({ abc }: { abc: Abc | null | undefined }) {
  if (!abc) return <span className="text-xs text-muted">Нет продаж</span>
  const s = IMPORTANCE[abc]
  return <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${s.className}`}>{s.label}</span>
}

/** Фото товара; пока фото нет — первая буква названия. */
function Thumb({ name, src }: { name: string; src: string | null }) {
  return src ? (
    <img src={src} alt="" className="size-10 shrink-0 rounded-lg bg-hover object-cover" loading="lazy" />
  ) : (
    <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-lg bg-hover text-sm font-medium text-muted">
      {name.slice(0, 1).toUpperCase()}
    </span>
  )
}

const selectClass = 'rounded-lg border border-line bg-surface px-3 py-2 text-sm'

export function ProductsPage() {
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [days, setDays] = useState(1)
  const [sort, setSort] = useState<SortKey>('importance')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const deferredSearch = useDeferredValue(search)
  const periodSearch = usePeriodSearch()

  const { data: settings } = useSettings()
  const source = useSource()
  const marketKnown = source.data?.market_known ?? true
  const stockKnown = source.data?.stock_known ?? true

  // Срок «Продано» считаем от последнего дня данных (сегодня).
  const to = settings?.data_period.end
  const range = to ? { from: shiftDate(to, -(days - 1)), to } : {}
  const monthRange = to ? { from: shiftDate(to, -29), to } : {}

  const filters = { category, search: deferredSearch }
  const serverSort: ProductSort = sort === 'importance' ? 'units' : sort
  const { data, error, isFetching } = useProducts({ ...filters, ...range, sort: serverSort, order })
  // Важность — всегда по месяцу, чтобы она не прыгала при выборе «1 день».
  const month = useProducts({ ...filters, ...monthRange, sort: 'revenue', order: 'desc' })
  const importance = new Map(month.data?.items.map((p) => [p.id, p.abc]))
  // Место товара по выручке за месяц: 0 — самый важный.
  const rank = new Map(month.data?.items.map((p, i) => [p.id, p.revenue > 0 ? i : Number.MAX_SAFE_INTEGER]))
  const items = data?.items ?? []
  const rows = sort === 'importance'
    ? [...items].sort((a, b) => {
        const diff = (rank.get(a.id) ?? Number.MAX_SAFE_INTEGER) - (rank.get(b.id) ?? Number.MAX_SAFE_INTEGER)
        return order === 'desc' ? diff : -diff
      })
    : items

  const toggleSort = (key: SortKey) => {
    if (key === sort) setOrder(order === 'desc' ? 'asc' : 'desc')
    else {
      setSort(key)
      setOrder(key === 'name' || key === 'days_of_cover' ? 'asc' : 'desc')
    }
  }

  const periodLabel = days === 1 ? 'сегодня' : `за ${SALES_PERIODS.find((p) => p.days === days)?.label.toLowerCase()}`

  return (
    <>
      <PageTitle subtitle="Актуальная цена, сколько продано и сколько осталось на складе">Товары</PageTitle>

      <Card className="!p-3">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Название или артикул"
            aria-label="Поиск по названию или артикулу"
            className={`${selectClass} min-w-56 flex-1`}
          />
          <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Категория" className={`${selectClass} w-48 shrink-0`}>
            <option value="">Все категории</option>
            {settings?.categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <span className="text-sm text-ink-2">Продано за:</span>
            <div className="flex flex-wrap gap-1 rounded-xl bg-hover p-1 text-sm">
              {SALES_PERIODS.map((p) => (
                <button
                  key={p.days}
                  type="button"
                  onClick={() => setDays(p.days)}
                  aria-pressed={days === p.days}
                  className={`whitespace-nowrap rounded-lg px-3 py-1 ${days === p.days ? 'bg-surface font-medium shadow-sm' : 'text-ink-2'}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {error && <ErrorBox error={error} />}

      <Card className={`overflow-hidden !p-0 transition-opacity ${isFetching ? 'opacity-60' : ''}`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr>
                <th className="py-3 pl-4 pr-1 text-right align-bottom font-medium">№</th>
                {COLUMNS.map((col) => (
                  <th key={col.label} className={`px-4 py-3 align-bottom font-medium ${col.align === 'right' ? 'text-right' : ''}`}>
                    {col.key ? (
                      <button type="button" onClick={() => toggleSort(col.key!)} className="text-ink-2 hover:text-ink">
                        {col.label}
                        {sort === col.key && <span aria-hidden> {order === 'desc' ? '↓' : '↑'}</span>}
                      </button>
                    ) : (
                      <span className="text-ink-2">{col.label}</span>
                    )}
                    <span className="block whitespace-nowrap font-normal">{col.hint}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular divide-y divide-line">
              {rows.map((p, i) => (
                <tr key={p.id} className="hover:bg-hover">
                  <td className="py-3 pl-4 pr-1 text-right text-xs text-muted">{i + 1}</td>
                  <td className="max-w-96 px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Thumb name={p.name} src={p.image_url} />
                      <div className="min-w-0">
                        <Link to={{ pathname: `/products/${p.id}`, search: periodSearch }} className="block truncate font-medium hover:underline">
                          {p.name}
                        </Link>
                        <span className="block truncate text-xs text-muted">{p.sku} · {p.category_name}</span>
                        {p.kaspi_url && (
                          <a href={p.kaspi_url} target="_blank" rel="noreferrer noopener" className="text-xs text-accent hover:underline">
                            Открыть на Kaspi ↗
                          </a>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3"><Importance abc={importance.get(p.id)} /></td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <span className="font-medium">{money(p.price)}</span>
                    {marketKnown ? (
                      <span className={`block text-xs ${p.price_position === 1 ? 'text-good' : 'text-muted'}`}>
                        {p.price_position === 1 ? `✓ 1-е место из ${p.sellers}` : `${p.price_position}-е место из ${p.sellers}`}
                      </span>
                    ) : (
                      <span className="block text-xs text-muted">последняя продажа</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <span className="font-medium">{int(p.units)} шт</span>
                    <span className="block text-xs text-muted">{periodLabel}</span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    {stockKnown ? (
                      <>
                        <span className={`font-medium ${p.stock_status === 'out' ? 'text-critical' : ''}`}>{int(p.stock)} шт</span>
                        <span className="block text-xs text-muted">
                          {p.stock_status === 'out'
                            ? 'закончился'
                            : p.days_of_cover !== null
                              ? `хватит ≈ на ${dec(p.days_of_cover)} дн.`
                              : 'продаж нет'}
                        </span>
                      </>
                    ) : (
                      <span className="text-xs text-muted">нет данных</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data && data.items.length === 0 && <p className="p-6 text-center text-sm text-muted">Ничего не найдено</p>}
      </Card>
      {data && (
        <p className="text-xs text-muted">
          {data.total} товаров
          {!marketKnown && ' · место среди продавцов и фото появятся, когда подключим чтение страниц товаров на kaspi.kz'}
        </p>
      )}
    </>
  )
}
