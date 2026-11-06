import { useState } from 'react'
import { Link } from 'react-router'
import { useBot, useBotLog, useBotRun, useBotSwitch, useSaveRule, useSource } from '../api/client'
import type { BotRow, BotRule, BotStatus } from '../api/types'
import { Card, ErrorBox, Kpi, Loading, Notice, PageTitle } from '../components/ui'
import { int, money } from '../lib/format'
import { usePeriodSearch } from '../lib/period'

const time = (iso: string) =>
  new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

function Toggle({ checked, onChange, label, disabled }: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-10 shrink-0 rounded-full transition-colors disabled:opacity-50 ${checked ? 'bg-ink' : 'bg-line'}`}
    >
      <span className={`absolute top-0.5 size-5 rounded-full bg-surface shadow transition-all ${checked ? 'left-[18px]' : 'left-0.5'}`} />
    </button>
  )
}

/** Большой переключатель ON / OFF: зелёный — бот работает с товаром, красный — нет. */
function OnOff({ on, onChange, disabled }: { on: boolean; onChange: (value: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={on ? 'Бот включён для товара' : 'Бот выключен для товара'}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`relative flex h-8 w-[76px] shrink-0 items-center rounded-full border-2 border-white/70 shadow-inner transition-colors disabled:opacity-50 ${
        on ? 'bg-good-fill' : 'bg-critical'
      }`}
    >
      <span
        className={`absolute top-1/2 h-6 w-8 -translate-y-1/2 rounded-full bg-white shadow transition-all ${on ? 'left-[38px]' : 'left-1'}`}
      />
      <span className={`absolute text-xs font-bold tracking-wide text-white ${on ? 'left-2.5' : 'right-2.5'}`}>{on ? 'ON' : 'OFF'}</span>
    </button>
  )
}

/** Сводка: сколько товаров в боте, сколько на 1-м месте, сколько упёрлись в минимум. */
function Summary({ status }: { status: BotStatus }) {
  const c = status.counts
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Kpi label="Товаров в боте" value={`${int(c.in_bot)} из ${int(c.total)}`} hint="остальные бот не трогает" />
      <Kpi
        label="На 1-м месте"
        value={`${int(c.first)} из ${int(c.in_bot)}`}
        tone={c.in_bot && c.first === c.in_bot ? 'good' : undefined}
        hint="самая низкая цена на карточке"
      />
      <Kpi
        label="Стоят на минимуме"
        value={int(c.at_min)}
        tone={c.at_min ? 'bad' : undefined}
        hint="не на 1-м месте: конкурент дешевле вашего минимума"
      />
      <Kpi label="На 2-м месте" value={int(c.second)} hint="по вашему выбору или из-за минимума" />
    </div>
  )
}

function Controls({ status }: { status: BotStatus }) {
  const toggle = useBotSwitch()
  const run = useBotRun()
  const running = status.enabled

  return (
    <Card>
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="font-semibold">
            {!running ? 'Бот остановлен' : status.dry_run ? 'Бот работает в тестовом режиме' : 'Бот работает и меняет цены'}
          </p>
          <p className="mt-1 text-sm text-ink-2">
            {!running
              ? 'Цены не пересчитываются. Нажмите «Запустить бота», когда настроите товары.'
              : status.dry_run
                ? 'Бот считает, какую цену поставил бы, и пишет это в журнал. Настоящие цены на Kaspi не меняются.'
                : `Пересчитывает цены каждые ${Math.round(status.interval_seconds / 60)} мин и отправляет их в Kaspi.`}
          </p>
          {status.last_run && <p className="mt-1 text-xs text-muted">Последний пересчёт: {time(status.last_run)}</p>}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 md:flex-nowrap">
          <button
            type="button"
            onClick={() => run.mutate()}
            disabled={run.isPending}
            className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-line bg-surface px-4 text-sm font-semibold text-ink shadow-sm transition hover:bg-hover disabled:opacity-50"
          >
            <svg viewBox="0 0 24 24" className={`size-4 ${run.isPending ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5" />
            </svg>
            {run.isPending ? 'Считаю…' : 'Пересчитать'}
          </button>
          <button
            type="button"
            disabled={toggle.isPending}
            onClick={() => toggle.mutate({ enabled: !running, dry_run: status.dry_run })}
            className={`inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-xl px-5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50 ${
              running ? 'bg-critical shadow-sm' : 'cta-gradient'
            }`}
          >
            <svg viewBox="0 0 24 24" className="size-4" fill="currentColor" aria-hidden>
              {running ? <path d="M7 6h3.5v12H7zM13.5 6H17v12h-3.5z" /> : <path d="M8 5.5v13l10.5-6.5z" />}
            </svg>
            {running ? 'Остановить' : 'Запустить бота'}
          </button>
        </div>
      </div>

      <div className="mt-4 flex items-start gap-3 border-t border-line pt-4">
        <Toggle
          label="Тестовый режим"
          checked={status.dry_run}
          disabled={toggle.isPending}
          onChange={(dry_run) => {
            if (!dry_run && !confirm('Выключить тестовый режим? Бот начнёт менять настоящие цены на Kaspi.')) return
            toggle.mutate({ enabled: status.enabled, dry_run })
          }}
        />
        <div className="text-sm">
          <p className="font-medium">Тестовый режим {status.dry_run ? 'включён' : 'выключен'}</p>
          <p className="mt-0.5 text-ink-2">
            Пока он включён, бот ничего не меняет на Kaspi — только показывает, какие цены поставил бы. Оставьте его
            на пару дней, проверьте журнал внизу, потом выключите.
          </p>
        </div>
      </div>

      {(toggle.error || run.error) && (
        <p className="mt-3 text-sm text-critical">{(toggle.error ?? run.error)?.message}</p>
      )}
    </Card>
  )
}

function HowItWorks() {
  const steps: [string, string][] = [
    ['1. Включите ON', 'Задайте минимум и максимум цены и включите переключатель у товара.'],
    ['2. Бот ставит на 1\u00a0₸ дешевле', 'Конкурент продаёт за 10\u00a0000\u00a0₸ — у вас будет 9\u00a0999\u00a0₸. Подорожал — бот поднимет вашу цену, но не выше максимума.'],
    ['3. В минус — никогда', 'Ниже минимума и цены без убытка бот не опустится. Если конкурент дешевле — держит минимум.'],
  ]
  return (
    <Card title="Как работает бот">
      <ol className="grid gap-4 text-sm md:grid-cols-3">
        {steps.map(([title, text]) => (
          <li key={title}>
            <p className="font-medium">{title}</p>
            <p className="mt-1 text-ink-2">{text}</p>
          </li>
        ))}
      </ol>
      <p className="mt-4 border-t border-line pt-3 text-xs text-muted">
        Цель «На 2-м месте» — бот встаёт сразу за самым дешёвым продавцом: меньше ценовой войны, выше прибыль.
      </p>
    </Card>
  )
}

/** Итог по товару: какое место займёт и почему. */
function Outcome({ row }: { row: BotRow }) {
  if (row.next_price === null || row.next_position === null) {
    return <span className="text-muted">не в боте</span>
  }
  const atMin = row.next_kind === 'min' && row.next_position !== 1
  const badge = atMin
    ? { text: `На минимуме · ${row.next_position}-е место`, className: 'bg-warning/25 text-ink' }
    : row.next_position === 1
      ? { text: '1-е место', className: 'bg-good/10 text-good' }
      : { text: `${row.next_position}-е место`, className: 'bg-hover text-ink-2 ring-1 ring-line' }
  const change = row.next_price - row.price

  return (
    <div className="flex flex-col items-end gap-1">
      <p className="font-medium">
        {money(row.next_price)}
        {change !== 0 && (
          <span className={`ml-1.5 text-xs ${change < 0 ? 'text-critical' : 'text-good'}`}>
            {change > 0 ? '+' : '−'}{int(Math.abs(change))}
          </span>
        )}
      </p>
      <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}>{badge.text}</span>
      {row.next_profit !== null && (
        <p className={`text-xs ${row.next_profit < 0 ? 'text-critical' : 'text-ink-2'}`}>
          прибыль с продажи: <b>{money(row.next_profit)}</b>
        </p>
      )}
      <p className="max-w-56 whitespace-normal text-right text-xs text-muted">{row.next_reason}</p>
      {row.next_position !== 1 && row.first_place_price !== null && (
        <p className="max-w-56 whitespace-normal text-right text-xs text-muted">
          Чтобы быть 1-м, нужно {money(row.first_place_price)}
          {row.first_place_profit !== null && (
            <>
              {' '}— прибыль{' '}
              <span className={row.first_place_profit < 0 ? 'font-medium text-critical' : 'font-medium text-ink-2'}>
                {money(row.first_place_profit)}
              </span>
            </>
          )}
        </p>
      )}
    </div>
  )
}

const draftFor = (row: BotRow): BotRule =>
  row.rule ?? {
    enabled: true,
    // Минимум по умолчанию — цена без убытка (если закупка указана).
    min_price: row.break_even ?? Math.round((row.price * 0.9) / 10) * 10,
    max_price: Math.max(Math.round((row.price * 1.15) / 10) * 10, row.break_even ?? 0),
    step: 1,
    strategy: 'first',
    protect: true,
  }

/** Закупка — только показываем: берётся со страницы «Закупочные цены», вписывать здесь не нужно. */
function CostCell({ row }: { row: BotRow }) {
  const search = usePeriodSearch()
  if (row.cost === null) {
    return (
      <Link to={{ pathname: '/costs', search }} className="text-sm font-semibold text-accent hover:underline">
        вписать →
      </Link>
    )
  }
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-semibold">{money(row.cost)}</span>
      {row.break_even !== null && <span className="text-xs text-muted">без убытка от {money(row.break_even)}</span>}
    </div>
  )
}

function PriceInput({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
  return (
    <input
      type="number"
      inputMode="numeric"
      min={1}
      aria-label={label}
      value={value || ''}
      onChange={(e) => onChange(Number(e.target.value))}
      className="tabular w-24 rounded-lg border border-line bg-surface px-2 py-1 text-right text-sm"
    />
  )
}

function RuleRow({ row, index }: { row: BotRow; index: number }) {
  const [draft, setDraft] = useState<BotRule>(() => draftFor(row))
  const save = useSaveRule()
  const dirty = JSON.stringify(draft) !== JSON.stringify(row.rule)
  const set = (patch: Partial<BotRule>) => setDraft((d) => ({ ...d, ...patch }))
  const invalid = draft.min_price <= 0 || draft.max_price < draft.min_price
  const on = !!row.rule?.enabled

  return (
    <tr className="align-top hover:bg-hover">
      <td className="py-3 pl-4 pr-1 text-right text-xs text-muted">{index}</td>
      <td className="max-w-64 px-3 py-3">
        <p className="truncate font-medium">{row.name}</p>
        <p className="text-xs text-muted">{row.sku} · продавцов {row.sellers}</p>
        <p className="text-xs text-ink-2">продано за 30 дней: <b>{row.units_30d} шт</b></p>
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-right">
        <p className="font-medium">{money(row.price)}</p>
        <p className="text-xs text-muted">{row.position}-е место</p>
        <p className="text-xs text-muted">дешевле всех: {row.min_competitor ? money(row.min_competitor) : '—'}</p>
        <p className="text-xs text-ink-2">на складе: <b>{row.stock !== null ? `${row.stock} шт` : 'нет данных'}</b></p>
      </td>
      <td className="px-3 py-3"><CostCell row={row} /></td>
      <td className="px-3 py-3">
        <div className="flex flex-col gap-1">
          <PriceInput label="Минимум" value={draft.min_price} onChange={(v) => set({ min_price: v })} />
          {row.break_even !== null && draft.min_price < row.break_even && (
            <button type="button" onClick={() => set({ min_price: row.break_even! })} className="w-fit text-left text-xs text-critical hover:underline">
              ниже — в минус. Поставить {money(row.break_even)}
            </button>
          )}
        </div>
      </td>
      <td className="px-3 py-3"><PriceInput label="Максимум" value={draft.max_price} onChange={(v) => set({ max_price: v })} /></td>
      <td className="px-3 py-3">
        <select
          aria-label="Цель"
          value={draft.strategy}
          onChange={(e) => set({ strategy: e.target.value as BotRule['strategy'] })}
          className="rounded-lg border border-line bg-surface px-2 py-1 text-sm"
        >
          <option value="first">На 1-м месте</option>
          <option value="second">На 2-м месте</option>
        </select>
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-right"><Outcome row={row} /></td>
      <td className="px-4 py-3">
        <div className="flex flex-col items-start gap-1.5">
          <OnOff
            on={on}
            disabled={invalid || save.isPending}
            onChange={(value) => save.mutate({ id: row.product_id, rule: { ...draft, enabled: value, protect: true } })}
          />
          {on && dirty && (
            <button
              type="button"
              disabled={invalid || save.isPending}
              onClick={() => save.mutate({ id: row.product_id, rule: { ...draft, enabled: true } })}
              className="whitespace-nowrap rounded-lg bg-ink px-2.5 py-1 text-xs font-medium text-page disabled:opacity-40"
            >
              Сохранить
            </button>
          )}
          {invalid && <p className="max-w-36 text-xs text-critical">Максимум должен быть не меньше минимума</p>}
          {save.error && <p className="max-w-36 text-xs text-critical">{save.error.message}</p>}
        </div>
      </td>
    </tr>
  )
}

type Filter = 'all' | 'bot' | 'not_first'

const FILTERS: { id: Filter; label: (s: BotStatus) => string }[] = [
  { id: 'all', label: (s) => `Все · ${s.counts.total}` },
  { id: 'bot', label: (s) => `В боте · ${s.counts.in_bot}` },
  { id: 'not_first', label: (s) => `Не на 1-м месте · ${s.counts.in_bot - s.counts.first}` },
]

function Log() {
  const { data } = useBotLog()
  return (
    <Card title="Журнал изменений" className="overflow-hidden">
      {!data?.length ? (
        <p className="text-sm text-muted">Пока пусто. Включите ON у товаров и нажмите «Пересчитать сейчас».</p>
      ) : (
        <ul className="divide-y divide-line text-sm">
          {data.map((e, i) => (
            <li key={`${e.time}-${e.product_id}-${i}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2">
              <span className="w-28 shrink-0 text-xs text-muted">{time(e.time)}</span>
              <span className="min-w-0 flex-1 truncate">{e.name}</span>
              <span className="tabular whitespace-nowrap">
                {money(e.old_price)} → <b>{money(e.new_price)}</b>
              </span>
              {e.dry_run && <span className="rounded-full bg-hover px-2 py-0.5 text-xs text-ink-2 ring-1 ring-line">тест, не изменено</span>}
              <span className="w-full text-xs text-muted">{e.reason}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

type SortKey = 'sales' | 'price' | 'cost'

function Th({ title, hint, right, sortKey, sort, onSort }: {
  title: string
  hint?: string
  right?: boolean
  sortKey?: SortKey
  sort?: { key: SortKey; order: 'desc' | 'asc' }
  onSort?: (key: SortKey) => void
}) {
  const active = sortKey && sort?.key === sortKey
  return (
    <th className={`px-3 py-3 align-bottom font-medium ${right ? 'text-right' : ''}`}>
      {sortKey && onSort ? (
        <button type="button" onClick={() => onSort(sortKey)} className={`block whitespace-nowrap text-ink-2 hover:text-ink ${right ? 'ml-auto' : ''}`} title="Сортировать">
          {title} {active ? (sort!.order === 'desc' ? '↓' : '↑') : '↕'}
        </button>
      ) : (
        <span className="block whitespace-nowrap text-ink-2">{title}</span>
      )}
      {hint && <span className="block font-normal">{hint}</span>}
    </th>
  )
}

export function BotPage() {
  const source = useSource()
  if (source.data && !source.data.market_known) {
    return (
      <>
        <PageTitle>Бот цен</PageTitle>
        <Notice title="Для вашего магазина бот пока выключен">
          Бот ставит цену на 1 ₸ дешевле конкурента — для этого нужны цены других продавцов с kaspi.kz. Пока их нет,
          бот мог бы ошибиться (например, поднять все цены до максимума), поэтому на настоящем магазине он
          заблокирован. Попробовать бота можно на «Демо-магазине» — выберите его слева внизу.
        </Notice>
      </>
    )
  }
  return <BotScreen />
}

function BotScreen() {
  const { data, error } = useBot()
  const [filter, setFilter] = useState<Filter>('all')
  // По умолчанию — от дорогих к дешёвым. Нажатие на заголовок меняет порядок.
  const [sort, setSort] = useState<{ key: SortKey; order: 'desc' | 'asc' }>({ key: 'sales', order: 'desc' })
  const onSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, order: s.order === 'desc' ? 'asc' : 'desc' } : { key, order: 'desc' }))

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading />

  const value = (r: BotRow) => (sort.key === 'sales' ? r.units_30d : sort.key === 'price' ? r.price : r.cost)
  const rows = data.rows
    .filter((r) => (filter === 'bot' ? r.rule : filter === 'not_first' ? r.next_position !== null && r.next_position !== 1 : true))
    .sort((a, b) => {
      const va = value(a), vb = value(b)
      if (va === null && vb === null) return 0
      if (va === null) return 1 // без закупки — в конец
      if (vb === null) return -1
      return sort.order === 'desc' ? vb - va : va - vb
    })

  return (
    <>
      <PageTitle subtitle="Держит ваши товары на 1-м месте: ставит цену на 1 ₸ дешевле конкурента, но не ниже минимума">
        Бот цен
      </PageTitle>
      <Summary status={data} />
      <Controls status={data} />
      <HowItWorks />

      <Card className="overflow-hidden !p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-4 md:px-5">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-semibold">Товары</h2>
            <div className="flex flex-wrap items-center gap-1 rounded-xl bg-hover p-1 text-sm">
              <span className="px-2 text-ink-2">Сначала:</span>
              {([['sales', 'Топ продаж'], ['price', 'Дорогие'], ['cost', 'Закупка']] as const).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSort({ key, order: 'desc' })}
                  className={`rounded-lg px-3 py-1 ${sort.key === key ? 'bg-surface font-medium shadow-sm' : 'text-ink-2'}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-1 rounded-xl bg-hover p-1 text-sm">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                className={`rounded-lg px-3 py-1 ${filter === f.id ? 'bg-surface font-medium shadow-sm' : 'text-ink-2'}`}
              >
                {f.label(data)}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="tabular w-full min-w-[1000px] text-sm">
            <thead className="border-y border-line text-left text-xs text-muted">
              <tr>
                <th className="py-3 pl-4 pr-1 text-right align-bottom font-medium">№</th>
                <Th title="Товар" />
                <Th title="Ваша цена" hint="и место сейчас" right sortKey="price" sort={sort} onSort={onSort} />
                <Th title="Закупка, ₸" hint="со страницы «Закупочные цены»" sortKey="cost" sort={sort} onSort={onSort} />
                <Th title="Минимум, ₸" hint="ниже не опустится" />
                <Th title="Максимум, ₸" hint="выше не поднимет" />
                <Th title="Цель" hint="какое место держать" />
                <Th title="Бот поставит" hint="место и почему" right />
                <Th title="Бот" hint="для этого товара" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((row, i) => (
                <RuleRow key={`${row.product_id}-${JSON.stringify(row.rule)}`} row={row} index={i + 1} />
              ))}
            </tbody>
          </table>
          {!rows.length && <p className="px-4 py-6 text-sm text-muted">Таких товаров нет.</p>}
        </div>
      </Card>

      <Log />
    </>
  )
}
