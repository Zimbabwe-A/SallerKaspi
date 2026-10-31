import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { BreakdownItem } from '../api/types'
import { money, numberCompact, pct, shortDate } from '../lib/format'

/** Цвета частей цены — фиксированы за статьёй, а не за порядком. */
const BREAKDOWN_COLORS: Record<string, string> = {
  commission: 'var(--s1)',
  delivery: 'var(--s2)',
  penalties: 'var(--s3)',
  cost: 'var(--s4)',
  tax: 'var(--s5)',
  profit: 'var(--s6)',
}

export function BreakdownBar({ items, revenue }: { items: BreakdownItem[]; revenue: number }) {
  const [hovered, setHovered] = useState<string | null>(null)
  const visible = items.filter((i) => i.amount > 0)
  const active = items.find((i) => i.key === hovered)

  return (
    <div>
      <div className="flex h-9 gap-0.5 overflow-hidden rounded-lg" onMouseLeave={() => setHovered(null)}>
        {visible.map((item) => (
          <div
            key={item.key}
            role="img"
            aria-label={`${item.label}: ${money(item.amount)}, ${pct(item.share)}`}
            onMouseEnter={() => setHovered(item.key)}
            className="h-full min-w-1 transition-opacity first:rounded-l-lg last:rounded-r-lg"
            style={{
              width: `${(item.amount / revenue) * 100}%`,
              background: BREAKDOWN_COLORS[item.key],
              opacity: hovered && hovered !== item.key ? 0.35 : 1,
            }}
          />
        ))}
      </div>
      <p className="mt-2 h-5 text-sm text-ink-2" aria-live="polite">
        {active ? (
          <>
            <span className="font-medium text-ink">{active.label}</span> — {money(active.amount)} · {pct(active.share)} от цены
          </>
        ) : (
          'Наведите на полосу, чтобы увидеть сумму'
        )}
      </p>
      <ul className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        {items.map((item) => (
          <li
            key={item.key}
            className="flex items-center gap-2"
            onMouseEnter={() => setHovered(item.key)}
            onMouseLeave={() => setHovered(null)}
          >
            <span className="size-2.5 shrink-0 rounded-full" style={{ background: BREAKDOWN_COLORS[item.key] }} />
            <span className="text-ink-2">{item.label}</span>
            <span className="tabular ml-auto font-medium">{pct(item.share)}</span>
            <span className="tabular w-28 text-right text-muted">{money(item.amount)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export interface Series {
  key: string
  label: string
  color: string
  dashed?: boolean
}

interface TooltipPayload {
  dataKey?: string | number
  value?: number
  color?: string
}

function ChartTooltip({ active, payload, label, series }: {
  active?: boolean
  payload?: readonly TooltipPayload[]
  label?: string | number
  series: Series[]
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-sm shadow-lg">
      <p className="mb-1 font-medium">{shortDate(String(label))}</p>
      {series.map((s) => {
        const entry = payload.find((p) => p.dataKey === s.key)
        if (!entry) return null
        return (
          <p key={s.key} className="flex items-center gap-2">
            <span className="size-2 rounded-full" style={{ background: s.color }} />
            <span className="text-ink-2">{s.label}</span>
            <span className="tabular ml-auto pl-4 font-medium">{money(Number(entry.value))}</span>
          </p>
        )
      })}
    </div>
  )
}

/** Линейный график по дням. Все серии — в тенге, одна ось. */
export function DailyLineChart<T extends { date: string }>({ data, series, height = 260 }: {
  data: T[]
  series: Series[]
  height?: number
}) {
  return (
    <div>
      {series.length > 1 && (
        <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2">
          {series.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span
                className="h-0.5 w-4 rounded"
                style={{
                  background: s.dashed ? `repeating-linear-gradient(90deg, ${s.color} 0 4px, transparent 4px 7px)` : s.color,
                }}
              />
              {s.label}
            </li>
          ))}
        </ul>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--grid)" />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tick={{ fill: 'var(--muted)', fontSize: 12 }}
            axisLine={{ stroke: 'var(--axis)' }}
            tickLine={false}
            minTickGap={28}
          />
          <YAxis
            tickFormatter={numberCompact}
            tick={{ fill: 'var(--muted)', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={56}
            domain={['auto', 'auto']}
          />
          <Tooltip
            cursor={{ stroke: 'var(--axis)', strokeWidth: 1 }}
            content={(props) => (
              <ChartTooltip
                active={props.active}
                payload={props.payload as readonly TooltipPayload[] | undefined}
                label={props.label}
                series={series}
              />
            )}
          />
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              strokeDasharray={s.dashed ? '4 3' : undefined}
              dot={false}
              activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
