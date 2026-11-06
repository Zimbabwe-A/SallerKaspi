import { useDeferredValue, useState } from 'react'
import { useProducts, useSaveCost, useSource } from '../api/client'
import type { ProductRow } from '../api/types'
import { Card, ErrorBox, PageTitle } from '../components/ui'
import { money } from '../lib/format'

/** Закупка одного товара: сохраняется по Enter или когда уходите из поля. */
function CostInput({ product, cost }: { product: ProductRow; cost: number | null }) {
  const saved = cost !== null ? String(cost) : ''
  const [value, setValue] = useState(saved)
  const save = useSaveCost()
  const commit = () => {
    if (value === saved) return
    save.mutate({ id: product.id, cost: value === '' ? null : Math.max(0, Number(value)) })
  }
  return (
    <div className="flex items-center justify-end gap-2">
      {save.isSuccess && <span className="text-xs text-good">сохранено</span>}
      {save.error && <span className="text-xs text-critical">{save.error.message}</span>}
      <input
        type="number"
        inputMode="numeric"
        min={0}
        aria-label={`Закупка: ${product.name}`}
        placeholder="не указана"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && commit()}
        className="tabular w-28 rounded-lg border border-line bg-surface px-2 py-1 text-right text-sm placeholder:text-muted"
      />
    </div>
  )
}

export function CostsPage() {
  const [search, setSearch] = useState('')
  const deferred = useDeferredValue(search)
  const { data, error } = useProducts({ search: deferred, sort: 'revenue', order: 'desc' })
  const source = useSource()

  return (
    <>
      <PageTitle subtitle="За сколько вы покупаете товар. Хранится только у вас на компьютере, в Kaspi не отправляется">
        Закупочные цены
      </PageTitle>
      {source.data && (
        <p className="text-sm text-ink-2">
          Указано у {source.data.products_with_cost} из {source.data.products} товаров. Нажмите Enter или перейдите к
          следующему полю — цена сохранится.
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
        <table className="tabular w-full text-sm">
          <thead className="border-b border-line text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Товар</th>
              <th className="px-4 py-3 text-right font-medium">Цена на Kaspi</th>
              <th className="px-4 py-3 text-right font-medium">Закупка, ₸</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data?.items.map((p) => (
              <tr key={p.id}>
                <td className="max-w-96 px-4 py-2">
                  <p className="truncate font-medium">{p.name}</p>
                  <p className="text-xs text-muted">{p.sku}</p>
                </td>
                <td className="whitespace-nowrap px-4 py-2 text-right">{money(p.price)}</td>
                <td className="px-4 py-2">
                  <CostInput product={p} cost={p.cost_price} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  )
}
