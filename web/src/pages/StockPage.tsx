import { Link } from 'react-router'
import { useStock } from '../api/client'
import type { StockStatus } from '../api/types'
import { Card, ErrorBox, Kpi, Loading, PageTitle, StockBadge } from '../components/ui'
import { dec, int, shortDate } from '../lib/format'
import { usePeriodSearch } from '../lib/period'

export function StockPage() {
  const { data, error } = useStock()
  const search = usePeriodSearch()

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading />

  const count = (status: StockStatus) => data.filter((r) => r.status === status).length

  return (
    <>
      <PageTitle subtitle="Скорость продаж — средняя за последние 14 дней">Остатки</PageTitle>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Нет в наличии" value={String(count('out'))} tone={count('out') ? 'bad' : undefined} hint="товаров" />
        <Kpi label="Меньше 7 дней" value={String(count('critical'))} hint="нужна поставка срочно" />
        <Kpi label="Меньше 14 дней" value={String(count('low'))} hint="пора заказывать" />
        <Kpi label="В норме" value={String(count('ok'))} tone="good" hint="товаров" />
      </div>

      <Card className="overflow-hidden !p-0">
        <div className="overflow-x-auto">
          <table className="tabular w-full min-w-[720px] text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Товар</th>
                <th className="px-4 py-3 font-medium">Статус</th>
                <th className="px-4 py-3 text-right font-medium">Остаток</th>
                <th className="px-4 py-3 text-right font-medium">Продаж в день</th>
                <th className="px-4 py-3 text-right font-medium">Хватит на</th>
                <th className="px-4 py-3 text-right font-medium">Поставка</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((r) => (
                <tr key={r.product_id} className="hover:bg-hover">
                  <td className="max-w-72 px-4 py-3">
                    <Link to={{ pathname: `/products/${r.product_id}`, search }} className="block truncate font-medium hover:underline">
                      {r.name}
                    </Link>
                    <span className="text-xs text-muted">{r.sku}</span>
                  </td>
                  <td className="px-4 py-3"><StockBadge status={r.status} /></td>
                  <td className="px-4 py-3 text-right">{int(r.quantity)} шт</td>
                  <td className="px-4 py-3 text-right">{dec(r.avg_daily_sales)}</td>
                  <td className="px-4 py-3 text-right font-medium">
                    {r.days_of_cover !== null ? `${dec(r.days_of_cover)} дн.` : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-ink-2">
                    {r.incoming_date ? `${int(r.incoming_quantity)} шт · ${shortDate(r.incoming_date)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
