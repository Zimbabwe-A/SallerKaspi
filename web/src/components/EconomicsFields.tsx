import type { ReactNode } from 'react'
import type { DeliveryType, Tariffs, WeightTier } from '../api/types'
import type { EconomicsForm } from '../lib/economicsForm'

export const inputClass = 'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm'

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-sm text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  )
}

export function EconomicsFields({ form, onChange, tariffs }: {
  form: EconomicsForm
  onChange: (next: EconomicsForm) => void
  tariffs: Tariffs
}) {
  const set = <K extends keyof EconomicsForm>(key: K, value: EconomicsForm[K]) => onChange({ ...form, [key]: value })
  const preset = tariffs.commission_presets.find((p) => String(p.pct) === form.commission_pct)
  const number = (key: 'purchase_cost' | 'other_cost' | 'price' | 'commission_pct' | 'tax_pct' | 'target_margin_pct', step = '1') => (
    <input
      type="number"
      inputMode="decimal"
      min="0"
      step={step}
      value={form[key]}
      onChange={(e) => set(key, e.target.value)}
      className={`${inputClass} tabular`}
    />
  )

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label="Закупка за 1 шт, ₸">{number('purchase_cost')}</Field>
      <Field label="Прочие расходы за 1 шт, ₸" hint="Упаковка, доставка до склада">{number('other_cost')}</Field>
      <Field label="Цена продажи, ₸">{number('price')}</Field>
      <Field label="Налог с выручки, %" hint="Ставка вашего режима">{number('tax_pct', '0.1')}</Field>
      <div className="sm:col-span-2">
        <Field label="Категория">
          <select
            value={preset?.id ?? ''}
            onChange={(e) => {
              const next = tariffs.commission_presets.find((p) => p.id === e.target.value)
              if (next) set('commission_pct', String(next.pct))
            }}
            className={inputClass}
          >
            {!preset && <option value="">Своя ставка</option>}
            {tariffs.commission_presets.map((p) => (
              <option key={p.id} value={p.id}>{p.label} — {String(p.pct).replace('.', ',')}%</option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Комиссия Kaspi с НДС, %">{number('commission_pct', '0.1')}</Field>
      <Field label="Доставка">
        <select
          value={form.delivery_type}
          onChange={(e) => set('delivery_type', e.target.value as DeliveryType)}
          className={inputClass}
        >
          {tariffs.delivery_types.map((d) => (
            <option key={d.id} value={d.id}>{d.label}</option>
          ))}
        </select>
      </Field>
      <Field label="Вес заказа" hint="Влияет на тариф от 10 000 ₸">
        <select value={form.weight} onChange={(e) => set('weight', e.target.value as WeightTier)} className={inputClass}>
          {tariffs.weight_tiers.map((w) => (
            <option key={w.id} value={w.id}>{w.label}</option>
          ))}
        </select>
      </Field>
      <Field label="Желаемая маржа, %">{number('target_margin_pct', '0.1')}</Field>
    </div>
  )
}
