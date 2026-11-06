import { Link } from 'react-router'
import { useAlerts, useBreakdown, useDailySales, useProducts, useSource, useSummary } from '../api/client'
import { BreakdownBar, DailyLineChart } from '../components/charts'
import { AbcBadge, Card, ErrorBox, Kpi, Loading, Notice, PageTitle, SeverityBadge } from '../components/ui'
import { int, money, pct } from '../lib/format'
import { usePeriodSearch } from '../lib/period'

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  )
}

export function OverviewPage() {
  const summary = useSummary()
  const breakdown = useBreakdown()
  const daily = useDailySales()
  const top = useProducts({ sort: 'revenue', order: 'desc' })
  const alerts = useAlerts()
  const search = usePeriodSearch()
  const source = useSource()
  const missingCost = source.data ? source.data.products - source.data.products_with_cost : 0

  if (summary.error) return <ErrorBox error={summary.error} />
  if (!summary.data) return <Loading />

  const { current: t, change_pct: change } = summary.data
  const shareOfRevenue = (value: number) => (t.revenue ? pct((value / t.revenue) * 100) : '—')

  return (
    <>
      <PageTitle
        subtitle={`${int(t.orders)} заказов · ${int(t.units)} шт выкуплено${
          t.pending_orders ? ` · в пути ${int(t.pending_orders)} на ${money(t.pending_amount)}` : ''
        } · отмен ${t.cancelled}, возвратов ${t.returned}`}
      >
        Аналитика магазина
      </PageTitle>

      {missingCost > 0 && source.data && (
        <Notice accent title="Впишите, за сколько вы покупаете товары — иначе прибыль неточная">
          Сайт не знает, сколько вы платите поставщику, поэтому прибыль выходит больше настоящей. Не вписано у{' '}
          {missingCost} из {source.data.products} товаров.
          <Link
            to={{ pathname: '/costs', search }}
            className="cta-gradient mt-3 block w-fit rounded-lg px-4 py-2 text-base font-semibold text-white hover:opacity-90"
          >
            Вписать закупочные цены
          </Link>
        </Notice>
      )}

      <div className="grid gap-3 sm:grid-cols-3">
        <Kpi
          label="Выручка"
          accent="var(--cta)"
          icon={<Icon d="M3 7h18v12H3zM3 7l3-3h12l3 3M16 13h2" />}
          value={money(t.revenue)}
          change={change.revenue}
          hint={t.pending_orders ? `+ ${money(t.pending_amount)} в пути · средний чек ${money(t.avg_check)}` : `Средний чек ${money(t.avg_check)}`}
        />
        <Kpi
          label="Удержал Kaspi"
          accent="var(--critical)"
          icon={<Icon d="M19 5 5 19M7.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM16.5 18a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" />}
          value={money(t.kaspi_total)}
          tone="bad"
          hint={`${shareOfRevenue(t.kaspi_total)} от выручки`}
        />
        <Kpi
          label="Прибыль"
          accent="var(--good)"
          icon={<Icon d="m3 17 6-6 4 4 8-8M15 7h6v6" />}
          value={money(t.profit)}
          tone={t.profit >= 0 ? 'good' : 'bad'}
          change={change.profit}
          hint={missingCost > 0 ? `без учёта закупки · после налога ${money(t.profit_after_tax)}` : `После налога ${money(t.profit_after_tax)}`}
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
