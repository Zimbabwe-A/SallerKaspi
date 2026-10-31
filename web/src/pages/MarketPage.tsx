import { useState } from 'react'
import { Link } from 'react-router'
import { useAlerts, useMarketCategories } from '../api/client'
import type { AlertSeverity } from '../api/types'
import { Card, ErrorBox, PageTitle, SeverityBadge } from '../components/ui'
import { dec, money, pct, shortDate } from '../lib/format'
import { usePeriodSearch } from '../lib/period'

function PriceIndex({ value }: { value: number }) {
  const diff = value - 100
  const text = Math.abs(diff) < 0.5 ? 'как рынок' : diff > 0 ? `дороже на ${pct(diff)}` : `дешевле на ${pct(-diff)}`
  return (
    <span>
      {dec(value)}
      <span className={`block text-xs ${diff > 0.5 ? 'text-critical' : diff < -0.5 ? 'text-good' : 'text-muted'}`}>{text}</span>
    </span>
  )
}

const FILTERS: { value: AlertSeverity | ''; label: string }[] = [
  { value: '', label: 'Все' },
  { value: 'high', label: 'Важные' },
  { value: 'medium', label: 'Внимание' },
  { value: 'low', label: 'Инфо' },
]

export function MarketPage() {
  const categories = useMarketCategories()
  const alerts = useAlerts()
  const [severity, setSeverity] = useState<AlertSeverity | ''>('')
  const search = usePeriodSearch()
  const shown = alerts.data?.filter((a) => !severity || a.severity === severity)

  return (
    <>
      <PageTitle subtitle="Ваши цены против конкурентов на тех же карточках — по состоянию на сегодня">Рынок</PageTitle>

      {categories.error && <ErrorBox error={categories.error} />}

      <Card title="Категории" className="overflow-hidden">
        <div className="-mx-4 overflow-x-auto md:-mx-5">
          <table className="tabular w-full min-w-[640px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-2 font-medium md:px-5">Категория</th>
                <th className="px-4 py-2 text-right font-medium" title="Ваша цена к средней цене продавцов, 100 — как рынок">Индекс цены</th>
                <th className="px-4 py-2 text-right font-medium">Вы самый дешёвый</th>
                <th className="px-4 py-2 text-right font-medium">Продавцов на карточке</th>
                <th className="px-4 py-2 text-right font-medium md:px-5">Выручка 30 дн.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {categories.data?.map((c) => (
                <tr key={c.id} className="hover:bg-hover">
                  <td className="px-4 py-3 md:px-5">
                    <span className="font-medium">{c.name}</span>
                    <span className="block text-xs text-muted">{c.products} товаров</span>
                  </td>
                  <td className="px-4 py-3 text-right"><PriceIndex value={c.price_index} /></td>
                  <td className="px-4 py-3 text-right">{pct(c.cheapest_share)} <span className="text-muted">товаров</span></td>
                  <td className="px-4 py-3 text-right">{dec(c.avg_sellers)}</td>
                  <td className="px-4 py-3 text-right font-medium md:px-5">{money(c.revenue_30d)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card
        title="Сигналы"
        action={
          <div className="flex gap-1">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                onClick={() => setSeverity(f.value)}
                className={`rounded-lg px-2.5 py-1 text-xs ${severity === f.value ? 'bg-ink text-page' : 'text-ink-2 hover:bg-hover'}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        }
      >
        {shown?.length === 0 && <p className="text-sm text-muted">Сигналов нет.</p>}
        <ul className="divide-y divide-line">
          {shown?.map((a, i) => (
            <li key={i} className="flex flex-col gap-1 py-3 text-sm sm:flex-row sm:gap-4">
              <div className="flex shrink-0 items-center gap-2 sm:w-36 sm:flex-col sm:items-start">
                <SeverityBadge severity={a.severity} />
                <span className="text-xs text-muted">{shortDate(a.date)}</span>
              </div>
              <div className="min-w-0">
                <Link to={{ pathname: `/products/${a.product_id}`, search }} className="font-medium hover:underline">
                  {a.product_name}
                </Link>
                <span className="ml-1.5 text-xs text-muted">{a.sku}</span>
                <p className="text-ink-2">{a.message}</p>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}
