import { Link } from 'react-router'
import { useToShip } from '../api/client'
import type { ShipOrder } from '../api/types'
import { Card, ErrorBox, Kpi, Loading, Notice, PageTitle } from '../components/ui'
import { int, money, shortDate } from '../lib/format'

const today = () => new Date().toISOString().slice(0, 10)

function ShipBy({ order }: { order: ShipOrder }) {
  if (order.cancelling) return <span className="rounded-full bg-hover px-2 py-0.5 text-xs font-medium text-critical ring-1 ring-line">отменяется — не отправлять</span>
  if (!order.ship_by) return <span className="text-xs text-muted">срок неизвестен</span>
  const late = order.ship_by < today()
  const now = order.ship_by === today()
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-line ${late ? 'text-critical' : now ? 'text-warning' : 'text-ink-2'}`}>
      {late ? 'опаздывает · ' : now ? 'сегодня · ' : ''}передать {shortDate(order.ship_by)}
    </span>
  )
}

/** Заказы Kaspi Доставки, которые нужно собрать и передать курьеру, и общий сборочный лист. */
export function OrdersPage() {
  const { data, error } = useToShip()

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading />

  return (
    <>
      <PageTitle subtitle="Kaspi Доставка: заказы приняты, но ещё не переданы курьеру. Обновляется вместе с заказами Kaspi">
        Заказы к отправке
      </PageTitle>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="К отправке" value={int(data.count)} hint="заказов" />
        <Kpi label="Передать сегодня" value={int(data.due_today)} tone={data.due_today ? 'bad' : undefined} hint="и опаздывающие" />
        <Kpi label="Не собрано" value={int(data.not_assembled)} hint="заказов" />
        <Kpi label="Отменяются" value={int(data.cancelling)} hint="не упаковывайте их" />
      </div>

      {!data.dates_known && data.count > 0 && (
        <Notice title="Сроки передачи появятся после следующего обновления заказов">
          Kaspi отдаёт дату передачи курьеру вместе с заказом — она подтянется при ближайшем автообновлении.
        </Notice>
      )}

      {data.count === 0 && data.cancelling === 0 ? (
        <Card><p className="text-sm text-ink-2">Нечего отправлять — все заказы уже у курьера.</p></Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <Card
            className="print-area"
            title="Сборочный лист"
            action={
              <button type="button" onClick={() => window.print()} className="text-sm font-semibold text-accent hover:underline">
                Распечатать
              </button>
            }
          >
            <p className="mb-2 text-xs text-muted">Сколько каждого товара взять со склада для всех заказов сразу</p>
            <ul className="divide-y divide-line text-sm">
              {data.pick_list.map((r) => (
                <li key={r.sku} className="flex items-center gap-3 py-2">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{r.name}</span>
                    <span className="text-xs text-muted">{r.sku} · в {int(r.orders)} заказ{r.orders === 1 ? 'е' : 'ах'}</span>
                  </span>
                  <b className="tabular text-base">{int(r.qty)} шт</b>
                </li>
              ))}
            </ul>
          </Card>

          <Card title={`Заказы · ${data.orders.length}`} action={<Link to="/waybills" className="text-sm font-semibold text-accent hover:underline">Накладные →</Link>}>
            <ul className="divide-y divide-line text-sm">
              {data.orders.map((o) => (
                <li key={o.code} className={`py-3 ${o.cancelling ? 'opacity-60' : ''}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <b className="tabular">№ {o.code}</b>
                    <ShipBy order={o} />
                    {o.express && <span className="rounded-full bg-hover px-2 py-0.5 text-xs font-medium text-pink ring-1 ring-line">экспресс</span>}
                    {o.assembled && !o.cancelling && <span className="rounded-full bg-hover px-2 py-0.5 text-xs font-medium text-good ring-1 ring-line">собран</span>}
                    <span className="ml-auto text-xs text-muted">{o.town ?? ''} · {money(o.total)}</span>
                  </div>
                  <ul className="mt-1 text-ink-2">
                    {o.items.map((i, n) => (
                      <li key={i.sku + n} className="flex gap-2">
                        <span className="min-w-0 flex-1 truncate">{i.name}</span>
                        <span className="tabular">× {int(i.qty)}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
    </>
  )
}
