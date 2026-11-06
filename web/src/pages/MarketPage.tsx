import { useState } from 'react'
import { useInsights } from '../api/client'
import type { Insights } from '../api/client'
import { Card, ErrorBox, Kpi, Loading, PageTitle } from '../components/ui'
import { dec, int, money } from '../lib/format'

type Tab = 'order' | 'trends' | 'risks'

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: 'order', icon: '📦', label: 'Умный заказ' },
  { id: 'trends', icon: '🚀', label: 'Что закупать нового' },
  { id: 'risks', icon: '📉', label: 'Риски закупа' },
]

const STATUS: Record<Insights['reorder'][number]['status'], { label: string; className: string }> = {
  out: { label: 'Закончился', className: 'bg-pink text-white' },
  urgent: { label: 'Срочно', className: 'bg-critical/20 text-critical' },
  soon: { label: 'Скоро', className: 'bg-warning/20 text-warning' },
  ok: { label: 'Хватает', className: 'bg-good/15 text-good' },
  no_sales: { label: 'Нет продаж', className: 'bg-hover text-muted' },
}

function Badge({ text, className }: { text: string; className: string }) {
  return <span className={`whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-bold ${className}`}>{text}</span>
}

function SmartOrder({ data }: { data: Insights }) {
  const needOrder = data.reorder.filter((r) => r.status === 'out' || r.status === 'urgent' || r.status === 'soon')
  const counts = { A: 0, B: 0, C: 0 }
  data.abc.forEach((r) => r.abc && counts[r.abc]++)
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-3">
        <Kpi label="Пора заказать" value={`${needOrder.length} товаров`} tone={needOrder.length ? 'bad' : 'good'} hint="закончились или скоро закончатся" />
        <Kpi label="Упущенная выручка" value={`${money(data.lost_total_per_day)} / день`} tone={data.lost_total_per_day ? 'bad' : 'good'} hint="столько теряете из-за товаров, которых нет" />
        <Kpi label="Главные товары (A)" value={`${counts.A}`} hint={`дают 80% ${data.based_on} · B: ${counts.B} · C: ${counts.C}`} />
      </div>

      <Card title="Сколько заказать" className="overflow-hidden !p-0">
        <p className="px-4 pb-2 text-sm text-ink-2 md:px-5">
          Скорость продаж — средняя за 2 недели. Заказ считаем на 30 дней продаж + 7 дней на поставку.
        </p>
        <div className="overflow-x-auto">
          <table className="tabular w-full min-w-[720px] text-sm">
            <thead className="border-y border-line text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Товар</th>
                <th className="px-3 py-3 text-right font-medium">Продаётся в день</th>
                <th className="px-3 py-3 text-right font-medium">На складе</th>
                <th className="px-3 py-3 text-right font-medium">Хватит на</th>
                <th className="px-3 py-3 text-right font-medium">Заказать</th>
                <th className="px-4 py-3 font-medium">Что делать</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.reorder.filter((r) => r.status !== 'no_sales').map((r) => (
                <tr key={r.product_id} className="hover:bg-hover">
                  <td className="max-w-72 px-4 py-3">
                    <p className="truncate font-semibold">{r.name}</p>
                    <p className="text-xs text-muted">{r.sku}</p>
                  </td>
                  <td className="px-3 py-3 text-right">{dec(r.per_day)} шт</td>
                  <td className="px-3 py-3 text-right font-semibold">{r.stock !== null ? `${int(r.stock)} шт` : '—'}</td>
                  <td className="px-3 py-3 text-right">{r.days_left !== null ? `${dec(r.days_left)} дн.` : '—'}</td>
                  <td className="px-3 py-3 text-right text-base font-bold">{r.order_qty ? `${int(r.order_qty)} шт` : '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <Badge text={STATUS[r.status].label} className={STATUS[r.status].className} />
                      <span className="text-xs text-ink-2">{r.message}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {data.lost.length > 0 && (
        <Card title="Упущенная выручка — товара нет, а его покупают">
          <ul className="divide-y divide-line text-sm">
            {data.lost.map((r) => (
              <li key={r.product_id} className="flex flex-wrap items-baseline gap-x-3 py-2">
                <span className="min-w-0 flex-1 truncate font-semibold">{r.name}</span>
                <span className="text-xs text-muted">{dec(r.per_day)} шт/день × {money(r.price)}</span>
                <span className="font-bold text-critical">−{money(r.lost_per_day)} в день</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title={`ABC / XYZ — какие товары закупать (по ${data.based_on} за 90 дней)`} className="overflow-hidden !p-0">
        <div className="grid gap-2 px-4 pb-3 text-xs text-ink-2 sm:grid-cols-2 md:px-5">
          <p><b>A</b> — дают 80% денег, заказывать всегда · <b>B</b> — средние · <b>C</b> — мёртвый груз, не закупать.</p>
          <p><b>X</b> — продаётся ровно · <b>Y</b> — колеблется · <b>Z</b> — рывками, держать маленький запас.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="tabular w-full min-w-[640px] text-sm">
            <thead className="border-y border-line text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Товар</th>
                <th className="px-3 py-3 text-center font-medium">Класс</th>
                <th className="px-3 py-3 text-right font-medium">За 90 дней</th>
                <th className="px-4 py-3 font-medium">Совет</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.abc.map((r) => (
                <tr key={r.product_id} className="hover:bg-hover">
                  <td className="max-w-72 truncate px-4 py-3 font-semibold">{r.name}</td>
                  <td className="px-3 py-3 text-center">
                    <span className={`inline-block min-w-12 rounded-lg px-2 py-0.5 text-sm font-bold ${
                      r.abc === 'A' ? 'cta-gradient text-white' : r.abc === 'B' ? 'bg-hover text-ink' : 'bg-pink/20 text-pink'
                    }`}>
                      {r.abc ?? '—'}{r.xyz ?? ''}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right">{money(r.amount)}</td>
                  <td className="px-4 py-3 text-xs text-ink-2">{r.advice}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

function Trends() {
  const items: [string, string, string][] = [
    ['Поисковые магниты', 'Что покупатели ищут на Kaspi, но не находят — готовый список идей для закупа.',
      'Kaspi эти запросы продавцам не отдаёт. Нужен ночной анализ поиска kaspi.kz (с 03:00 до 06:00) — сделаем отдельно.'],
    ['Тренды TikTok / Instagram', 'Сигнал, когда товар или бренд завирусился в Reels: спрос растёт.',
      'Нужен доступ к данным соцсетей (их официальные API или сервис-партнёр). Обсудим источник.'],
    ['Новички-взлёты', 'Карточки, которые вышли меньше месяца назад, но уже много продают.',
      'Нужен ночной обход категорий kaspi.kz и сравнение отзывов по дням. Запланируем на ночное окно 03:00–06:00.'],
  ]
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {items.map(([title, what, how]) => (
        <Card key={title}>
          <div className="flex items-center justify-between gap-2">
            <p className="text-base font-bold">{title}</p>
            <Badge text="скоро" className="bg-[color-mix(in_srgb,var(--cta)_20%,transparent)] text-accent" />
          </div>
          <p className="mt-2 text-sm text-ink-2">{what}</p>
          <p className="mt-3 border-t border-line pt-3 text-xs text-muted">{how}</p>
        </Card>
      ))}
    </div>
  )
}

function Risks({ data }: { data: Insights }) {
  const monopoly = data.risks.filter((r) => r.monopoly).length
  const crowded = data.risks.filter((r) => r.sellers >= 10).length
  const maxHistory = Math.max(0, ...data.risks.map((r) => r.history_days))
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-3">
        <Kpi label="Крупный продавец на карточке" value={`${monopoly}`} tone={monopoly ? 'bad' : 'good'} hint="Kaspi Магазин или продавец с тысячами отзывов" />
        <Kpi label="Тесные карточки" value={`${crowded}`} hint="10 и больше продавцов — ценовая война" />
        <Kpi label="История цен" value={`${maxHistory} дн.`} hint="индекс демпинга точнее, чем дольше история" />
      </div>
      <Card title="Риски по товарам" className="overflow-hidden !p-0">
        <div className="overflow-x-auto">
          <table className="tabular w-full min-w-[640px] text-sm">
            <thead className="border-y border-line text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Товар</th>
                <th className="px-3 py-3 text-right font-medium">Продавцов</th>
                <th className="px-3 py-3 text-right font-medium">Индекс демпинга</th>
                <th className="px-4 py-3 font-medium">Вывод</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.risks.map((r) => (
                <tr key={r.product_id} className="hover:bg-hover">
                  <td className="max-w-72 truncate px-4 py-3 font-semibold">{r.name}</td>
                  <td className="px-3 py-3 text-right text-base font-bold">{r.sellers}</td>
                  <td className="px-3 py-3 text-right">
                    {r.price_drop_pct !== null ? (
                      <span className={r.price_drop_pct >= 15 ? 'font-bold text-critical' : r.price_drop_pct > 0 ? 'text-warning' : 'text-good'}>
                        {r.price_drop_pct > 0 ? `−${dec(r.price_drop_pct)}%` : r.price_drop_pct < 0 ? `+${dec(-r.price_drop_pct)}%` : '0%'}
                      </span>
                    ) : (
                      <span className="text-xs text-muted">копим историю</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs ${r.monopoly ? 'font-bold text-pink' : 'text-ink-2'}`}>{r.advice}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="text-xs text-muted">
        Индекс демпинга — на сколько упала самая низкая цена конкурентов с начала истории. Цены записываются каждый день
        автообновлением; через 3 месяца индекс покажет полную картину.
      </p>
    </>
  )
}

export function MarketPage() {
  const { data, error } = useInsights()
  const [tab, setTab] = useState<Tab>('order')

  return (
    <>
      <PageTitle subtitle="Что и сколько закупать, где вы теряете деньги и где опасно заходить с товаром">Аналитика рынка</PageTitle>
      <div className="flex flex-wrap gap-1 rounded-2xl border border-line bg-surface p-1.5">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`flex-1 whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-bold transition ${
              tab === t.id ? 'cta-gradient text-white' : 'text-ink-2 hover:bg-hover'
            }`}
          >
            <span aria-hidden className="mr-1.5">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>
      {error && <ErrorBox error={error} />}
      {tab === 'trends' ? <Trends /> : !data ? <Loading /> : tab === 'order' ? <SmartOrder data={data} /> : <Risks data={data} />}
    </>
  )
}
