import { useDeferredValue, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { currentShop, useProducts, useSaveCost, useSaveStock, useSource } from '../api/client'
import type { ProductRow } from '../api/types'
import { Card, ErrorBox, PageTitle } from '../components/ui'
import { money } from '../lib/format'

type ImportResult = { updated: number; unchanged: number; empty: number; unknown: string[]; unknown_count: number; errors: string[] }

/** Выгрузить закупку в Excel, заполнить и загрузить обратно. */
function ExcelBar() {
  const input = useRef<HTMLInputElement>(null)
  const client = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const shop = encodeURIComponent(currentShop())

  const upload = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const response = await fetch(`/api/costs/import?shop=${shop}`, { method: 'POST', body: form, credentials: 'same-origin' })
      const body = await response.json().catch(() => null)
      if (!response.ok) throw new Error(body?.detail ?? `Ошибка ${response.status}`)
      setResult(body)
      client.invalidateQueries()  // закупка меняет прибыль везде
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не получилось загрузить файл')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-ink-2">
          Много товаров? Скачайте таблицу, впишите закупку в колонку «Закупка» и загрузите обратно. Подойдёт и ваша
          таблица — нужны колонки «Артикул» и «Закупка» (или «Себестоимость»). Пустые ячейки не трогают сохранённое.
        </p>
        <div className="flex shrink-0 gap-2">
          <a
            href={`/api/costs/export.xlsx?shop=${shop}`}
            className="inline-flex h-11 items-center whitespace-nowrap rounded-xl border border-line bg-surface px-4 text-sm font-semibold text-ink hover:bg-hover"
          >
            Скачать Excel
          </a>
          <button
            type="button"
            disabled={busy}
            onClick={() => input.current?.click()}
            className="cta-gradient inline-flex h-11 items-center whitespace-nowrap rounded-xl px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? 'Загружаю…' : 'Загрузить из Excel'}
          </button>
          <input
            ref={input}
            type="file"
            hidden
            accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
            onChange={(e) => { upload(e.target.files?.[0]); e.target.value = '' }}
          />
        </div>
      </div>
      {error && <p className="mt-3 text-sm text-critical">{error}</p>}
      {result && (
        <div className="mt-3 text-sm">
          <p>
            Обновлено: <b>{result.updated}</b>
            {result.unchanged > 0 && <> · без изменений: {result.unchanged}</>}
            {result.empty > 0 && <> · пустых ячеек: {result.empty}</>}
            {result.unknown_count > 0 && <> · артикулов нет в магазине: {result.unknown_count}</>}
          </p>
          {result.unknown.length > 0 && <p className="mt-1 text-xs text-muted">Не найдены: {result.unknown.join(', ')}{result.unknown_count > result.unknown.length ? '…' : ''}</p>}
          {result.errors.length > 0 && <p className="mt-1 text-xs text-critical">Пропущено: {result.errors.join('; ')}</p>}
        </div>
      )}
    </Card>
  )
}

/** Поле с числом: сохраняется по Enter или когда уходите из поля. */
function NumberCell({ value, label, placeholder, onSave, error }: {
  value: number | null
  label: string
  placeholder: string
  onSave: (value: number | null) => void
  error: Error | null
}) {
  const saved = value !== null ? String(value) : ''
  const [text, setText] = useState(saved)
  const commit = () => {
    if (text === saved) return
    onSave(text === '' ? null : Math.max(0, Math.round(Number(text))))
  }
  return (
    <div className="flex items-center justify-end gap-2">
      {error && <span className="text-xs text-critical">{error.message}</span>}
      <input
        type="number"
        inputMode="numeric"
        min={0}
        aria-label={label}
        placeholder={placeholder}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && commit()}
        className="tabular w-28 rounded-lg border border-line bg-surface px-2 py-1 text-right text-sm placeholder:text-muted"
      />
    </div>
  )
}

function Row({ product, index, stockKnown }: { product: ProductRow; index: number; stockKnown: boolean }) {
  const cost = useSaveCost()
  const stock = useSaveStock()
  return (
    <tr className="hover:bg-hover">
      <td className="py-2 pl-4 pr-1 text-right text-xs text-muted">{index}</td>
      <td className="max-w-96 px-4 py-2">
        <p className="truncate font-medium">{product.name}</p>
        <p className="text-xs text-muted">{product.sku}</p>
      </td>
      <td className="whitespace-nowrap px-4 py-2 text-right">{money(product.price)}</td>
      <td className="px-4 py-2">
        <NumberCell
          value={product.cost_price}
          label={`Закупка: ${product.name}`}
          placeholder="не указана"
          onSave={(value) => cost.mutate({ id: product.id, cost: value })}
          error={cost.error}
        />
      </td>
      <td className="px-4 py-2">
        {stockKnown ? (
          <p className="text-right">{product.stock} шт</p>
        ) : (
          <NumberCell
            value={product.stock_entered}
            label={`Остаток: ${product.name}`}
            placeholder="не указан"
            onSave={(value) => stock.mutate({ id: product.id, quantity: value })}
            error={stock.error}
          />
        )}
      </td>
    </tr>
  )
}

type StockFilter = 'all' | 'out' | 'in'

export function CostsPage() {
  const [search, setSearch] = useState('')
  const [priceOrder, setPriceOrder] = useState<'desc' | 'asc' | null>(null)
  const [stockFilter, setStockFilter] = useState<StockFilter>('all')
  const deferred = useDeferredValue(search)
  const { data, error } = useProducts({ search: deferred, sort: 'revenue', order: 'desc' })
  const source = useSource()
  const stockKnown = source.data?.stock_known ?? true

  const items = data?.items ?? []
  const stockOf = (p: ProductRow) => (stockKnown ? p.stock : p.stock_entered)
  const outCount = items.filter((p) => stockOf(p) === 0).length
  const inCount = items.filter((p) => (stockOf(p) ?? 0) > 0).length
  const filtered = items.filter((p) => {
    if (stockFilter === 'out') return stockOf(p) === 0
    if (stockFilter === 'in') return (stockOf(p) ?? 0) > 0
    return true
  })
  const rows = priceOrder
    ? [...filtered].sort((a, b) => (priceOrder === 'desc' ? b.price - a.price : a.price - b.price))
    : filtered
  const filters: { key: StockFilter; label: string }[] = [
    { key: 'all', label: `Все (${items.length})` },
    { key: 'out', label: `Нет в наличии (${outCount})` },
    { key: 'in', label: `В наличии (${inCount})` },
  ]
  const togglePrice = () => setPriceOrder((o) => (o === 'desc' ? 'asc' : 'desc'))

  return (
    <>
      <PageTitle subtitle="За сколько вы покупаете товар и сколько осталось. Хранится только у вас на компьютере, в Kaspi не отправляется">
        Закупочные цены
      </PageTitle>
      {source.data && (
        <p className="text-sm text-ink-2">
          Закупка указана у {source.data.products_with_cost} из {source.data.products} товаров. Нажмите Enter или
          перейдите к следующему полю — значение сохранится.
        </p>
      )}
      <ExcelBar />
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Название или артикул"
        aria-label="Поиск по названию или артикулу"
        className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm"
      />
      <div className="flex flex-wrap self-start rounded-xl border border-line bg-surface p-1 shadow-sm">
        {filters.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setStockFilter(f.key)}
            aria-pressed={stockFilter === f.key}
            className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm ${
              stockFilter === f.key ? 'bg-ink font-medium text-page' : 'text-ink-2 hover:bg-hover'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      {error && <ErrorBox error={error} />}
      <Card className="overflow-hidden !p-0">
        <div className="overflow-x-auto">
          <table className="tabular w-full min-w-[640px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr>
                <th className="py-3 pl-4 pr-1 text-right font-medium">№</th>
                <th className="px-4 py-3 font-medium">Товар</th>
                <th className="px-4 py-3 text-right font-medium">
                  <button type="button" onClick={togglePrice} className="hover:text-ink" title="Сортировать по цене">
                    Цена на Kaspi {priceOrder === 'desc' ? '↓' : priceOrder === 'asc' ? '↑' : '↕'}
                  </button>
                </th>
                <th className="px-4 py-3 text-right font-medium">Закупка, ₸</th>
                <th className="px-4 py-3 text-right font-medium">Остаток, шт</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((p, i) => (
                <Row key={p.id} product={p} index={i + 1} stockKnown={stockKnown} />
              ))}
              {data && rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted">
                    {stockFilter === 'out' ? 'Нет товаров с нулевым остатком' : 'Ничего не найдено'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
