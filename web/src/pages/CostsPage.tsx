import { useDeferredValue, useState } from 'react'
import { useProducts, useSaveCost, useSaveStock, useSource } from '../api/client'
import type { ProductRow } from '../api/types'
import { Card, ErrorBox, PageTitle } from '../components/ui'
import { money } from '../lib/format'

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

export function CostsPage() {
  const [search, setSearch] = useState('')
  const [priceOrder, setPriceOrder] = useState<'desc' | 'asc' | null>(null)
  const deferred = useDeferredValue(search)
  const { data, error } = useProducts({ search: deferred, sort: 'revenue', order: 'desc' })
  const source = useSource()
  const stockKnown = source.data?.stock_known ?? true

  const items = data?.items ?? []
  const rows = priceOrder
    ? [...items].sort((a, b) => (priceOrder === 'desc' ? b.price - a.price : a.price - b.price))
    : items
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
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Название или артикул"
        aria-label="Поиск по названию или артикулу"
        className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm"
      />
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
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
