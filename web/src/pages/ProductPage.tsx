import { Link, useParams } from 'react-router'
import { useOffers, usePriceHistory, useProduct } from '../api/client'
import type { UnitEconomics } from '../api/types'
import { DailyLineChart } from '../components/charts'
import { AbcBadge, Card, ErrorBox, Kpi, Loading, PageTitle, StockBadge } from '../components/ui'
import { dec, int, money, pct } from '../lib/format'
import { usePeriodSearch } from '../lib/period'

function UnitEconomicsTable({ ue }: { ue: UnitEconomics }) {
  const rows = [
    { label: 'Комиссия Kaspi', value: -ue.commission },
    { label: 'Доставка', value: -ue.delivery },
    { label: 'Себестоимость', value: -ue.cost },
    { label: 'Налог', value: -ue.tax },
  ]
  return (
    <dl className="tabular text-sm">
      <div className="flex justify-between py-1.5">
        <dt className="text-ink-2">Цена продажи</dt>
        <dd className="font-medium">{money(ue.price)}</dd>
      </div>
      {rows.map((r) => (
        <div key={r.label} className="flex justify-between py-1.5">
          <dt className="text-ink-2">{r.label}</dt>
          <dd>−{money(-r.value)}</dd>
        </div>
      ))}
      <div className="mt-1 flex justify-between border-t border-line pt-2.5">
        <dt className="font-medium">Прибыль с 1 шт</dt>
        <dd className={`font-semibold ${ue.profit >= 0 ? 'text-good' : 'text-critical'}`}>
          {money(ue.profit)} · {pct(ue.margin_pct)}
        </dd>
      </div>
    </dl>
  )
}

export function ProductPage() {
  const id = Number(useParams().id)
  const search = usePeriodSearch()
  const product = useProduct(id)
  const offers = useOffers(id)
  const history = usePriceHistory(id)

  if (product.error) return <ErrorBox error={product.error} />
  if (!product.data) return <Loading />

  const { product: p, unit_economics: ue, daily, cost_price, commission_rate } = product.data

  return (
    <>
      <div>
        <Link to={{ pathname: '/products', search }} className="text-sm text-accent hover:underline">← Все товары</Link>
        <div className="mt-2 flex items-start gap-3">
          <AbcBadge abc={p.abc} />
          <PageTitle subtitle={`${p.sku} · ${p.category_name} · ★ ${dec(p.rating)} (${int(p.reviews)} отзывов)`}>{p.name}</PageTitle>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Выручка" value={money(p.revenue)} hint={`${int(p.units)} шт продано`} />
        <Kpi label="Прибыль" value={money(p.profit)} tone={p.profit >= 0 ? 'good' : 'bad'} hint={p.margin_pct !== null ? `маржа ${pct(p.margin_pct)}` : 'нет продаж'} />
        <Kpi label="Удержал Kaspi" value={money(p.kaspi_fees)} tone="bad" hint={`комиссия категории ${pct(commission_rate * 100)}`} />
        <Kpi
          label="Остаток"
          value={`${int(p.stock)} шт`}
          hint={<span className="inline-flex items-center gap-1.5"><StockBadge status={p.stock_status} />{p.days_of_cover !== null && `≈ ${dec(p.days_of_cover)} дн.`}</span>}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
        <Card title="Продажи по дням">
          <DailyLineChart
            data={daily}
            series={[
              { key: 'revenue', label: 'Выручка', color: 'var(--s1)' },
              { key: 'profit', label: 'Прибыль', color: 'var(--s2)' },
            ]}
          />
        </Card>
        <Card title="Экономика 1 шт по текущей цене">
          <UnitEconomicsTable ue={ue} />
          <p className="mt-3 text-xs text-muted">Себестоимость {money(cost_price)} — из настроек товара.</p>
        </Card>
      </div>

      <h2 className="mt-2 text-lg font-semibold">Рынок</h2>

      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        <Card title="Цена на карточке: вы и конкуренты">
          {history.data ? (
            <DailyLineChart
              data={history.data.points}
              series={[
                { key: 'my_price', label: 'Моя цена', color: 'var(--s1)' },
                { key: 'min_price', label: 'Минимальная', color: 'var(--s2)' },
                { key: 'avg_price', label: 'Средняя', color: 'var(--s3)', dashed: true },
              ]}
            />
          ) : (
            <div className="h-64 animate-pulse rounded-lg bg-hover" />
          )}
        </Card>

        <Card
          title="Продавцы сейчас"
          action={offers.data && (
            <span className={`text-sm font-medium ${offers.data.my_position === 1 ? 'text-good' : 'text-ink-2'}`}>
              {offers.data.my_position === 1 ? '✓ Вы самый дешёвый' : `Место ${offers.data.my_position} из ${offers.data.sellers}`}
            </span>
          )}
        >
          {offers.data && (
            <>
              {offers.data.gap_to_min > 0 && (
                <p className="mb-3 rounded-lg bg-warning/15 px-3 py-2 text-sm">
                  ▲ Вы дороже минимальной цены на <b>{money(offers.data.gap_to_min)}</b> ({pct(offers.data.gap_to_min_pct)})
                </p>
              )}
              <ul className="tabular divide-y divide-line text-sm">
                {offers.data.offers.map((o) => (
                  <li key={o.seller_id} className={`flex items-center gap-3 py-2 ${o.is_me ? 'font-semibold' : ''}`}>
                    <span className="w-5 text-muted">{o.position}</span>
                    <span className="min-w-0 flex-1 truncate">
                      {o.seller_name}
                      {!o.is_me && <span className="ml-1.5 text-xs font-normal text-muted">★ {o.rating} · {o.delivery_days} дн.</span>}
                    </span>
                    <span>{money(o.price)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      </div>
    </>
  )
}
