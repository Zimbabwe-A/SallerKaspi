import type { ReactNode } from 'react'
import type { AlertSeverity, StockStatus } from '../api/types'
import { signedPct } from '../lib/format'

export function Card({ title, action, children, className = '' }: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-2xl border border-line bg-surface p-4 shadow-sm md:p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="font-semibold">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function PageTitle({ children, subtitle }: { children: ReactNode; subtitle?: ReactNode }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">{children}</h1>
      {subtitle && <p className="mt-1 text-sm text-ink-2">{subtitle}</p>}
    </div>
  )
}

/** Изменение к прошлому периоду. inverse — когда рост это плохо (например, расходы). */
export function Change({ value, inverse = false }: { value: number | null | undefined; inverse?: boolean }) {
  if (value === null || value === undefined) return null
  const good = inverse ? value < 0 : value > 0
  const color = value === 0 ? 'text-muted' : good ? 'text-good' : 'text-critical'
  const arrow = value > 0 ? '↑' : value < 0 ? '↓' : '→'
  return (
    <span className={`text-xs font-medium ${color}`} title="К прошлому периоду той же длины">
      {arrow} {signedPct(value)}
    </span>
  )
}

export function Kpi({ label, value, tone, change, inverseChange, hint }: {
  label: string
  value: string
  tone?: 'good' | 'bad'
  change?: number | null
  inverseChange?: boolean
  hint?: ReactNode
}) {
  const color = tone === 'good' ? 'text-good' : tone === 'bad' ? 'text-critical' : 'text-ink'
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
      <p className="text-sm text-ink-2">{label}</p>
      <p className={`mt-1.5 text-xl font-semibold tracking-tight md:text-2xl ${color}`}>{value}</p>
      {(hint || change != null) && (
        <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-muted">
          <Change value={change} inverse={inverseChange} />
          {hint}
        </p>
      )}
    </div>
  )
}

const STOCK: Record<StockStatus, { label: string; icon: string; className: string }> = {
  out: { label: 'Нет в наличии', icon: '✕', className: 'bg-critical/10 text-critical' },
  critical: { label: 'Критично', icon: '!', className: 'bg-serious/15 text-serious' },
  low: { label: 'Мало', icon: '▲', className: 'bg-warning/20 text-ink-2' },
  ok: { label: 'В норме', icon: '✓', className: 'bg-good/10 text-good' },
}

export function StockBadge({ status }: { status: StockStatus }) {
  const s = STOCK[status]
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${s.className}`}>
      <span aria-hidden>{s.icon}</span>
      {s.label}
    </span>
  )
}

const SEVERITY: Record<AlertSeverity, { label: string; icon: string; className: string }> = {
  high: { label: 'Важно', icon: '!', className: 'bg-critical text-white' },
  medium: { label: 'Внимание', icon: '▲', className: 'bg-warning text-black' },
  low: { label: 'Инфо', icon: 'i', className: 'bg-hover text-ink-2 ring-1 ring-line' },
}

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const s = SEVERITY[severity]
  return (
    <span className={`inline-flex h-fit shrink-0 items-center gap-1 self-start whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${s.className}`}>
      <span aria-hidden>{s.icon}</span>
      {s.label}
    </span>
  )
}

export function AbcBadge({ abc }: { abc: 'A' | 'B' | 'C' | null }) {
  if (!abc) return <span className="text-muted">—</span>
  const className = abc === 'A' ? 'bg-ink text-page' : abc === 'B' ? 'bg-ink-2/20 text-ink' : 'bg-hover text-ink-2 ring-1 ring-line'
  return <span className={`inline-grid size-6 place-items-center rounded-md text-xs font-semibold ${className}`}>{abc}</span>
}

export function Loading() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-busy>
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="h-24 animate-pulse rounded-2xl bg-hover" />
      ))}
    </div>
  )
}

export function ErrorBox({ error }: { error: unknown }) {
  const text = error instanceof Error ? error.message : 'Неизвестная ошибка'
  return (
    <div className="rounded-2xl border border-critical/30 bg-critical/5 p-4 text-sm">
      <p className="font-medium text-critical">Не удалось загрузить данные</p>
      <p className="mt-1 text-ink-2">{text}. Проверьте, что сервер запущен на порту 8000.</p>
    </div>
  )
}
