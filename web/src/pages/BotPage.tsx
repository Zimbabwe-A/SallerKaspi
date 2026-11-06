import { useState } from 'react'
import { useBot, useBotLog, useBotRun, useBotSwitch, useDeleteRule, useSaveCost, useSaveRule, useSource } from '../api/client'
import type { BotRow, BotRule, BotStatus } from '../api/types'
import { Card, ErrorBox, Kpi, Loading, Notice, PageTitle } from '../components/ui'
import { int, money } from '../lib/format'

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
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => run.mutate()}
            disabled={run.isPending}
            className="rounded-lg border border-line bg-surface px-3 py-2 text-sm font-medium hover:bg-hover disabled:opacity-50"
          >
            {run.isPending ? 'Считаю…' : 'Пересчитать сейчас'}
          </button>
          <button
            type="button"
            disabled={toggle.isPending}
            onClick={() => toggle.mutate({ enabled: !running, dry_run: status.dry_run })}
            className={`rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 ${
              running ? 'border border-critical/40 bg-critical/5 text-critical' : 'bg-ink text-page'
            }`}
          >
            {running ? 'Остановить бота' : 'Запустить бота'}
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
  return (
    <Card title="Как работает бот">
      <ol className="grid gap-4 text-sm md:grid-cols-3">
        <li>
          <p className="font-medium">1. Задайте минимум и максимум</p>
          <p className="mt-1 text-ink-2">
            <b>Минимум</b> — цена, ниже которой продавать невыгодно. <b>Максимум</b> — выше которой не поднимать.
            Нажмите «Добавить в бота».
          </p>
        </li>
        <li>
          <p className="font-medium">2. Бот встаёт на 1 ₸ дешевле</p>
          <p className="mt-1 text-ink-2">
            Конкурент продаёт за 10&nbsp;000&nbsp;₸ — бот поставит вам 9&nbsp;999&nbsp;₸, и вы на 1-м месте.
            Конкурент подорожал — бот поднимет вашу цену, но не выше максимума.
          </p>
        </li>
        <li>
          <p className="font-medium">3. Ниже минимума и в минус — никогда</p>
          <p className="mt-1 text-ink-2">
            Укажите закупку — сайт сам посчитает цену «без убытка» (закупка + комиссия Kaspi + доставка + налог), и
            бот не опустится ниже неё, даже если минимум меньше. Если конкурент дешевле — бот стоит на минимуме и
            пишет, сколько стоило бы 1-е место.
          </p>
        </li>
      </ol>
      <p className="mt-4 border-t border-line pt-3 text-xs text-muted">
        Цель «На 2-м месте» — бот не бьётся за самую низкую цену, а встаёт сразу за самым дешёвым продавцом: меньше
        ценовой войны, выше маржа. Kaspi обновляет цены раз в час, поэтому новая цена появляется не сразу.
        Цены конкурентов сейчас: тестовые данные.
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

/** Закупочная цена: сохраняется у вас, в Kaspi не отправляется. */
function CostCell({ row }: { row: BotRow }) {
  const [value, setValue] = useState(row.cost !== null ? String(row.cost) : '')
  const save = useSaveCost()
  const saved = row.cost !== null ? String(row.cost) : ''
  const commit = () => {
    if (value === saved) return
    save.mutate({ id: row.product_id, cost: value === '' ? null : Math.max(0, Number(value)) })
  }
  return (
    <div className="flex flex-col gap-1">
      <input
        type="number"
        inputMode="numeric"
        min={0}
        aria-label="Закупочная цена"
        placeholder="не указана"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && commit()}
        className="tabular w-24 rounded-lg border border-line bg-surface px-2 py-1 text-right text-sm placeholder:text-muted"
      />
      {row.break_even !== null ? (
        <span className="text-xs text-muted">без убытка от {money(row.break_even)}</span>
      ) : (
        <span className="max-w-28 text-xs text-muted">укажите — бот не уйдёт в минус</span>
      )}
      {save.error && <span className="max-w-28 text-xs text-critical">{save.error.message}</span>}
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
  const remove = useDeleteRule()
  const dirty = JSON.stringify(draft) !== JSON.stringify(row.rule)
  const set = (patch: Partial<BotRule>) => setDraft((d) => ({ ...d, ...patch }))
  const invalid = draft.min_price <= 0 || draft.max_price < draft.min_price

  return (
    <tr className="align-top hover:bg-hover">
      <td className="py-3 pl-4 pr-1 text-right text-xs text-muted">{index}</td>
      <td className="max-w-64 px-3 py-3">
        <p className="truncate font-medium">{row.name}</p>
        <p className="text-xs text-muted">{row.sku} · продавцов {row.sellers}</p>
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-right">
        <p className="font-medium">{money(row.price)}</p>
        <p className="text-xs text-muted">{row.position}-е место</p>
        <p className="text-xs text-muted">дешевле всех: {row.min_competitor ? money(row.min_competitor) : '—'}</p>
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
          {row.rule && <Toggle label="Бот для товара" checked={draft.enabled} onChange={(enabled) => set({ enabled })} />}
          <label className="flex max-w-36 items-start gap-1.5 text-xs text-ink-2">
            <input type="checkbox" checked={draft.protect} onChange={(e) => set({ protect: e.target.checked })} className="mt-0.5" />
            не уходить в минус
          </label>
          {(dirty || !row.rule) && (
            <button
              type="button"
              disabled={invalid || save.isPending}
              onClick={() => save.mutate({ id: row.product_id, rule: draft })}
              className="whitespace-nowrap rounded-lg bg-ink px-2.5 py-1 text-xs font-medium text-page disabled:opacity-40"
            >
              {row.rule ? 'Сохранить' : 'Добавить в бота'}
            </button>
          )}
          {row.rule && !dirty && (
            <button type="button" onClick={() => remove.mutate(row.product_id)} className="whitespace-nowrap text-xs text-muted hover:underline">
              Убрать из бота
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
        <p className="text-sm text-muted">Пока пусто. Добавьте товары в бота и нажмите «Пересчитать сейчас».</p>
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

type SortKey = 'price' | 'cost'

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
  const [sort, setSort] = useState<{ key: SortKey; order: 'desc' | 'asc' }>({ key: 'price', order: 'desc' })
  const onSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, order: s.order === 'desc' ? 'asc' : 'desc' } : { key, order: 'desc' }))

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading />

  const value = (r: BotRow) => (sort.key === 'price' ? r.price : r.cost)
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
          <h2 className="font-semibold">Товары</h2>
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
                <Th title="Закупка, ₸" hint="хранится у вас" sortKey="cost" sort={sort} onSort={onSort} />
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
