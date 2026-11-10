import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useStock } from '../api/client'
import type { StockRow, StockStatus } from '../api/types'
import { Card, ErrorBox, Kpi, Loading, Notice, PageTitle, StockBadge } from '../components/ui'
import { dec, int, money, moneyCompact, shortDate } from '../lib/format'
import { usePeriodSearch } from '../lib/period'

const IDLE_DAYS = 30 // столько дней без продаж — товар «лежит»

type Tab = 'all' | 'reorder' | 'idle' | 'out'
const TABS: { id: Tab; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'reorder', label: 'Дозаказать' },
  { id: 'idle', label: 'Лежит без продаж' },
  { id: 'out', label: 'Нет в наличии' },
]

const isIdle = (r: StockRow) => r.idle_days !== null && r.idle_days >= IDLE_DAYS
const needsReorder = (r: StockRow) => r.reorder > 0 && (r.status === 'critical' || r.status === 'low' || r.status === 'out')

/** Склад: что заканчивается, что лежит без движения и сколько в этом денег. */
export function StockPage() {
  const { data, error } = useStock()
  const search = usePeriodSearch()
  const [tab, setTab] = useState<Tab>('all')

  const rows = useMemo(() => {
    if (!data) return []
    if (tab === 'reorder') return data.filter(needsReorder)
    if (tab === 'idle') return data.filter(isIdle).sort((a, b) => (b.frozen ?? 0) - (a.frozen ?? 0))
    if (tab === 'out') return data.filter((r) => r.status === 'out')
    return data
  }, [data, tab])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading />

  const count = (status: StockStatus) => data.filter((r) => r.status === status).length
  const known = data.filter((r) => r.status !== 'unknown')
  const idle = known.filter(isIdle)
  const frozenIdle = idle.reduce((sum, r) => sum + (r.frozen ?? 0), 0)
  const frozenAll = known.reduce((sum, r) => sum + (r.frozen ?? 0), 0)
  const noCost = known.filter((r) => r.quantity > 0 && r.cost === null).length

  if (!known.length) {
    return (
      <>
        <PageTitle>Склад</PageTitle>
        <Notice title="Остатки пока неизвестны">
          Остатки приходят из кабинета Kaspi или их можно вписать вручную на странице «Бот цен». Как только они появятся,
          здесь будет видно, на сколько дней хватит товара, что лежит без продаж и что пора дозаказать.
        </Notice>
      </>
    )
  }

  return (
    <>
      <PageTitle subtitle="Скорость продаж — средняя за последние 14 дней. Дозаказ — чтобы хватило на 30 дней">Склад</PageTitle>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Нет в наличии" value={String(count('out'))} tone={count('out') ? 'bad' : undefined} hint="товаров — заказы уходят конкурентам" />
        <Kpi label="Закончится за 7 дней" value={String(count('critical'))} hint={`ещё ${count('low')} — за 14 дней`} />
        <Kpi
          label="Заморожено в залежавшемся"
          value={moneyCompact(frozenIdle)}
          tone={frozenIdle ? 'bad' : undefined}
          hint={`${idle.length} товаров без продаж ${IDLE_DAYS}+ дней`}
        />
        <Kpi label="Всего в остатке" value={moneyCompact(frozenAll)} hint={noCost ? `по закупке; у ${noCost} товаров закупка не указана` : 'по закупке'} />
      </div>

      <div className="flex flex-wrap gap-2" role="tablist">
        {TABS.map((t) => {
          const n = t.id === 'reorder' ? data.filter(needsReorder).length : t.id === 'idle' ? idle.length : t.id === 'out' ? count('out') : data.length
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={`h-10 rounded-xl border px-4 text-sm font-semibold transition ${
                tab === t.id ? 'cta-gradient border-transparent text-white' : 'border-line bg-surface text-ink hover:border-[var(--cta)]'
              }`}
            >
              {t.label} <span className="opacity-70">{n}</span>
            </button>
          )
        })}
      </div>

      <Card className="overflow-hidden !p-0">
        {rows.length === 0 ? (
          <p className="p-6 text-sm text-ink-2">Здесь пусто — и это хорошо.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="tabular w-full min-w-[860px] text-sm">
              <thead className="border-b border-line text-left text-xs text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Товар</th>
                  <th className="px-4 py-3 font-medium">Статус</th>
                  <th className="px-4 py-3 text-right font-medium">Остаток</th>
                  <th className="px-4 py-3 text-right font-medium">Продаж в день</th>
                  <th className="px-4 py-3 text-right font-medium">Хватит на</th>
                  <th className="px-4 py-3 text-right font-medium">Без продаж</th>
                  <th className="px-4 py-3 text-right font-medium">В остатке денег</th>
                  <th className="px-4 py-3 text-right font-medium">Дозаказать</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r) => (
                  <tr key={r.product_id} className="hover:bg-hover">
                    <td className="max-w-72 px-4 py-3">
                      <Link to={{ pathname: `/products/${r.product_id}`, search }} className="block truncate font-medium hover:underline">
                        {r.name}
                      </Link>
                      <span className="text-xs text-muted">{r.sku}</span>
                    </td>
                    <td className="px-4 py-3"><StockBadge status={r.status} /></td>
                    <td className="px-4 py-3 text-right">{r.status === 'unknown' ? '—' : `${int(r.quantity)} шт`}</td>
                    <td className="px-4 py-3 text-right">{dec(r.avg_daily_sales)}</td>
                    <td className="px-4 py-3 text-right font-medium">{r.days_of_cover !== null ? `${dec(r.days_of_cover)} дн.` : '—'}</td>
                    <td className={`px-4 py-3 text-right ${isIdle(r) ? 'font-medium text-warning' : 'text-ink-2'}`}>
                      {r.idle_days !== null ? `${int(r.idle_days)} дн.` : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-ink-2">{r.frozen !== null ? money(r.frozen) : '—'}</td>
                    <td className="px-4 py-3 text-right">
                      {r.reorder > 0 ? <b>{int(r.reorder)} шт</b> : <span className="text-muted">—</span>}
                      {r.incoming_date && (
                        <span className="block text-xs text-muted">едет {int(r.incoming_quantity)} шт · {shortDate(r.incoming_date)}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {tab === 'idle' && idle.length > 0 && (
        <p className="text-sm text-ink-2">
          Что можно сделать: снизить цену или минимум для бота, включить бонус Kaspi, поставить в рекламу — или перестать
          закупать. Деньги в этих товарах сейчас не работают.
        </p>
      )}
    </>
  )
}
