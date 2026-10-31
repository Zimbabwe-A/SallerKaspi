import { Link } from 'react-router'
import { useAlerts, useBreakdown, useDailySales, useProducts, useSummary } from '../api/client'
import { BreakdownBar, DailyLineChart } from '../components/charts'
import { AbcBadge, Card, ErrorBox, Kpi, Loading, PageTitle, SeverityBadge } from '../components/ui'
import { int, money, pct } from '../lib/format'
import { usePeriodSearch } from '../lib/period'

export function OverviewPage() {
  const summary = useSummary()
  const breakdown = useBreakdown()
  const daily = useDailySales()
  const top = useProducts({ sort: 'revenue', order: 'desc' })
  const alerts = useAlerts()
  const search = usePeriodSearch()

  if (summary.error) return <ErrorBox error={summary.error} />
  if (!summary.data) return <Loading />

  const { current: t, change_pct: change } = summary.data
  const shareOfRevenue = (value: number) => (t.revenue ? pct((value / t.revenue) * 100) : '—')

  return (
    <>
      <PageTitle subtitle={`${int(t.orders)} заказов · ${int(t.units)} шт выкуплено · отмен ${t.cancelled}, возвратов ${t.returned}`}>
        Обзор
      </PageTitle>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Выручка" value={money(t.revenue)} change={change.revenue} hint={`Средний чек ${money(t.avg_check)}`} />
        <Kpi label="Удержал Kaspi" value={money(t.kaspi_total)} tone="bad" hint={`${shareOfRevenue(t.kaspi_total)} от выручки`} />
        <Kpi label="Пришло на счёт" value={money(t.payout)} tone="good" change={change.payout} hint={`${shareOfRevenue(t.payout)} от выручки`} />
        <Kpi
          label="Прибыль"
          value={money(t.profit)}
          tone={t.profit >= 0 ? 'good' : 'bad'}
          change={change.profit}
          hint={`После налога ${money(t.profit_after_tax)}`}
        />
      </div>

      <Card title="Куда уходит ваша цена">
        {breakdown.data ? (
          <BreakdownBar items={breakdown.data.items} revenue={breakdown.data.revenue} />
        ) : (
          <div className="h-32 animate-pulse rounded-lg bg-hover" />
        )}
      </Card>

      <Card title="Продажи по дням">
        {daily.data ? (
          <DailyLineChart
            data={daily.data}
            series={[
              { key: 'revenue', label: 'Выручка', color: 'var(--s1)' },
              { key: 'profit', label: 'Прибыль', color: 'var(--s2)' },
            ]}
          />
        ) : (
          <div className="h-64 animate-pulse rounded-lg bg-hover" />
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card
          title="Топ товаров по выручке"
          action={<Link to={{ pathname: '/products', search }} className="text-sm text-accent hover:underline">Все товары</Link>}
        >
          <ul className="divide-y divide-line">
            {top.data?.items.slice(0, 5).map((p) => (
              <li key={p.id}>
                <Link to={{ pathname: `/products/${p.id}`, search }} className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-hover">
                  <AbcBadge abc={p.abc} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{p.name}</span>
                    <span className="text-xs text-muted">{p.sku} · {int(p.units)} шт</span>
                  </span>
                  <span className="text-right">
                    <span className="tabular block text-sm font-medium">{money(p.revenue)}</span>
                    <span className="tabular text-xs text-muted">маржа {p.margin_pct !== null ? pct(p.margin_pct) : '—'}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>

        <Card
          title="Сигналы"
          action={<Link to={{ pathname: '/market', search }} className="text-sm text-accent hover:underline">Все сигналы</Link>}
        >
          {alerts.data?.length === 0 && <p className="text-sm text-muted">Всё спокойно — сигналов нет.</p>}
          <ul className="flex flex-col gap-3">
            {alerts.data?.slice(0, 5).map((a, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <SeverityBadge severity={a.severity} />
                <div className="min-w-0">
                  <Link to={{ pathname: `/products/${a.product_id}`, search }} className="font-medium hover:underline">
                    {a.product_name}
                  </Link>
                  <p className="text-ink-2">{a.message}</p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  )
}
