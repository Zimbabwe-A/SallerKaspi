import { useSettings } from '../api/client'
import { dateRange } from '../lib/format'
import { shiftDate, usePeriod } from '../lib/period'

const PRESETS = [
  { days: 7, label: '7 дней' },
  { days: 30, label: '30 дней' },
  { days: 90, label: '90 дней' },
]

export function PeriodPicker() {
  const { from, to, setPeriod } = usePeriod()
  const { data: settings } = useSettings()
  if (!settings) return <div className="h-10" />

  const { start: min, end: max } = settings.data_period
  const end = to ?? max
  const start = from ?? shiftDate(end, -6)
  const activeDays = !to || to === max ? PRESETS.find((p) => shiftDate(max, -(p.days - 1)) === start)?.days : undefined

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex rounded-xl border border-line bg-surface p-1 shadow-sm">
        {PRESETS.map((preset) => (
          <button
            key={preset.days}
            type="button"
            onClick={() => setPeriod(preset.days === 7 ? {} : { from: shiftDate(max, -(preset.days - 1)) })}
            className={`rounded-lg px-3 py-1.5 text-sm ${
              activeDays === preset.days ? 'bg-ink font-medium text-page' : 'text-ink-2 hover:bg-hover'
            }`}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <label className="flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-1.5 text-sm shadow-sm">
        <span className="sr-only">Начало периода</span>
        <input
          type="date"
          value={start}
          min={min}
          max={end}
          onChange={(e) => e.target.value && setPeriod({ from: e.target.value, to: end === max ? undefined : end })}
          className="bg-transparent"
        />
        <span className="text-muted">—</span>
        <span className="sr-only">Конец периода</span>
        <input
          type="date"
          value={end}
          min={start}
          max={max}
          onChange={(e) => e.target.value && setPeriod({ from: start, to: e.target.value })}
          className="bg-transparent"
        />
      </label>
      <span className="hidden text-sm text-muted sm:inline">{dateRange(start, end)}</span>
    </div>
  )
}
