import { useDeferredValue, useState } from 'react'
import { Link } from 'react-router'
import { useProducts, useSettings } from '../api/client'
import type { Abc, ProductSort } from '../api/types'
import { AbcBadge, Card, ErrorBox, PageTitle, StockBadge } from '../components/ui'
import { dec, int, money, pct } from '../lib/format'
import { usePeriodSearch } from '../lib/period'

const COLUMNS: { key: ProductSort | null; label: string; align?: 'right' }[] = [
  { key: 'name', label: 'Товар' },
  { key: null, label: 'ABC' },
  { key: null, label: 'Цена и место', align: 'right' },
  { key: 'units', label: 'Продано', align: 'right' },
  { key: 'revenue', label: 'Выручка', align: 'right' },
  { key: 'profit', label: 'Прибыль', align: 'right' },
  { key: 'margin_pct', label: 'Маржа', align: 'right' },
  { key: 'days_of_cover', label: 'Остаток', align: 'right' },
]

const selectClass = 'rounded-lg border border-line bg-surface px-3 py-2 text-sm'

export function ProductsPage() {
  const [category, setCategory] = useState('')
  const [abc, setAbc] = useState<Abc | ''>('')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<ProductSort>('revenue')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const deferredSearch = useDeferredValue(search)
  const periodSearch = usePeriodSearch()

  const { data: settings } = useSettings()
  const { data, error, isFetching } = useProducts({ category, abc, search: deferredSearch, sort, order })

  const toggleSort = (key: ProductSort) => {
    if (key === sort) setOrder(order === 'desc' ? 'asc' : 'desc')
    else {
      setSort(key)
      setOrder(key === 'name' || key === 'days_of_cover' ? 'asc' : 'desc')
    }
  }

  return (
    <>
      <PageTitle subtitle="Юнит-экономика, ABC-анализ и позиция вашей цены на карточке">Товары</PageTitle>

      <div className="flex flex-wrap gap-2">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Название или артикул"
          className={`${selectClass} min-w-0 flex-1 sm:max-w-xs`}
        />
        <select value={category} onChange={(e) => setCategory(e.target.value)} className={selectClass}>
          <option value="">Все категории</option>
          {settings?.categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <select value={abc} onChange={(e) => setAbc(e.target.value as Abc | '')} className={selectClass}>
          <option value="">ABC: все</option>
          <option value="A">A — 80% выручки</option>
          <option value="B">B — следующие 15%</option>
          <option value="C">C — остальные</option>
        </select>
      </div>

      {error && <ErrorBox error={error} />}

      <Card className={`overflow-hidden !p-0 transition-opacity ${isFetching ? 'opacity-60' : ''}`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr>
                {COLUMNS.map((col) => (
                  <th key={col.label} className={`px-4 py-3 font-medium ${col.align === 'right' ? 'text-right' : ''}`}>
                    {col.key ? (
                      <button type="button" onClick={() => toggleSort(col.key!)} className="hover:text-ink">
                        {col.label}
                        {sort === col.key && <span aria-hidden> {order === 'desc' ? '↓' : '↑'}</span>}
                      </button>
                    ) : (
                      col.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular divide-y divide-line">
              {data?.items.map((p) => (
                <tr key={p.id} className="hover:bg-hover">
                  <td className="max-w-72 px-4 py-3">
                    <Link to={{ pathname: `/products/${p.id}`, search: periodSearch }} className="block truncate font-medium hover:underline">
                      {p.name}
                    </Link>
                    <span className="text-xs text-muted">{p.sku} · {p.category_name}</span>
                  </td>
                  <td className="px-4 py-3"><AbcBadge abc={p.abc} /></td>
                  <td className="px-4 py-3 text-right">
                    {money(p.price)}
                    <span className={`block text-xs ${p.price_position === 1 ? 'text-good' : 'text-muted'}`}>
                      {p.price_position === 1 ? '✓ самая низкая' : `${p.price_position} из ${p.sellers}`}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">{int(p.units)}</td>
                  <td className="px-4 py-3 text-right font-medium">{money(p.revenue)}</td>
                  <td className={`px-4 py-3 text-right ${p.profit < 0 ? 'text-critical' : ''}`}>{money(p.profit)}</td>
                  <td className="px-4 py-3 text-right">{p.margin_pct !== null ? pct(p.margin_pct) : '—'}</td>
                  <td className="px-4 py-3 text-right">
                    {int(p.stock)} шт
                    <span className="block text-xs text-muted">
                      {p.days_of_cover !== null ? `≈ ${dec(p.days_of_cover)} дн.` : 'нет продаж'}
                    </span>
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
          {data.total} товаров · остатки: <StockBadge status="critical" /> меньше 7 дней, <StockBadge status="low" /> меньше 14 дней
        </p>
      )}
    </>
  )
}
