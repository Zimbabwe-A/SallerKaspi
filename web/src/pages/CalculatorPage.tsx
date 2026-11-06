import { useDeferredValue, useState } from 'react'
import { Link } from 'react-router'
import { useCalculation, useTariffs } from '../api/client'
import type { BreakdownItem, Economics, Tariffs } from '../api/types'
import { BreakdownBar } from '../components/charts'
import { EconomicsFields } from '../components/EconomicsFields'
import { Card, ErrorBox, Kpi, Loading, PageTitle } from '../components/ui'
import { emptyEconomics, toEconomicsInput } from '../lib/economicsForm'
import type { EconomicsForm } from '../lib/economicsForm'
import { money, pct } from '../lib/format'

function breakdownItems(e: Economics): BreakdownItem[] {
  const item = (key: string, label: string, amount: number) => ({
    key,
    label,
    amount,
    share: Math.round((amount / e.price) * 1000) / 10,
  })
  return [
    item('commission', 'Комиссия Kaspi', e.commission),
    item('delivery', 'Доставка', e.delivery),
    item('cost', 'Себестоимость', e.cost),
    item('tax', 'Налог', e.tax),
    item('profit', 'Прибыль', e.profit),
  ]
}

function Result({ economics: e, targetMargin }: { economics: Economics; targetMargin: number }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <Kpi label="Прибыль с 1 шт" value={money(e.profit)} tone={e.profit > 0 ? 'good' : 'bad'} hint={`маржа ${pct(e.margin_pct)}`} />
        <Kpi label="Возврат на вложения" value={e.roi_pct !== null ? pct(e.roi_pct) : '—'} hint="прибыль к себестоимости" />
        <Kpi label="Цена без убытка" value={e.break_even_price !== null ? money(e.break_even_price) : '—'} hint="ниже этой цены минус" />
        <Kpi label={`Цена для маржи ${pct(targetMargin)}`} value={e.target_price !== null ? money(e.target_price) : '—'} hint="минимальная цена" />
      </div>
      <Card title="Куда уходит цена">
        {e.profit < 0 && (
          <p className="mb-3 rounded-lg bg-critical/10 px-3 py-2 text-sm text-critical">
            ✕ Расходы больше цены: убыток {money(-e.profit)} с каждой продажи.
          </p>
        )}
        <BreakdownBar items={breakdownItems(e)} revenue={e.price} narrow />
      </Card>
    </>
  )
}

function Calculator({ tariffs }: { tariffs: Tariffs }) {
  const [form, setForm] = useState<EconomicsForm>(() => emptyEconomics(tariffs))
  const input = useDeferredValue(toEconomicsInput(form))
  const { data, error } = useCalculation(input)

  return (
    <div className="grid items-start gap-5 lg:grid-cols-2">
      <Card title="Данные о товаре">
        <EconomicsFields form={form} onChange={setForm} tariffs={tariffs} />
        <Link
          to="/niches"
          state={{ prefill: form }}
          className="mt-4 inline-block rounded-lg bg-ink px-3 py-2 text-sm font-medium text-page"
        >
          Добавить в подбор ниш
        </Link>
      </Card>
      <div className="flex min-w-0 flex-col gap-5">
        {error && <ErrorBox error={error} />}
        {input && data ? (
          <Result economics={data} targetMargin={input.target_margin_pct} />
        ) : (
          <Card><p className="text-sm text-muted">Введите закупку и цену продажи, и здесь появится расчёт.</p></Card>
        )}
      </div>
    </div>
  )
}

export function CalculatorPage() {
  const { data: tariffs, error } = useTariffs()
  if (error) return <ErrorBox error={error} />
  if (!tariffs) return <Loading />

  return (
    <>
      <PageTitle subtitle="Сколько останется с одной продажи на Kaspi, если покупатель не вернул товар">Калькулятор</PageTitle>
      <Calculator tariffs={tariffs} />
      <p className="text-xs text-muted">
        Тарифы проверены {tariffs.checked_at.split('-').reverse().join('.')}:{' '}
        <a href={tariffs.commission_source} target="_blank" rel="noreferrer" className="underline">комиссия</a>,{' '}
        <a href={tariffs.delivery_source} target="_blank" rel="noreferrer" className="underline">доставка</a> (плюс НДС 16%).
        Точную комиссию вашей категории сверьте по таблице. Акции Kaspi повышают комиссию, рекламу расчёт не учитывает.
      </p>
    </>
  )
}
