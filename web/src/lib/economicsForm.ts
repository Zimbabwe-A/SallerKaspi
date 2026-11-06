import type { DeliveryType, EconomicsInput, Tariffs, WeightTier } from '../api/types'

/** Значения полей как строки: пока человек печатает, поле может быть пустым. */
export interface EconomicsForm {
  purchase_cost: string
  other_cost: string
  price: string
  commission_pct: string
  delivery_type: DeliveryType
  weight: WeightTier
  tax_pct: string
  target_margin_pct: string
}

export function emptyEconomics(tariffs: Tariffs): EconomicsForm {
  return {
    purchase_cost: '',
    other_cost: '',
    price: '',
    commission_pct: String(tariffs.commission_presets[0].pct),
    delivery_type: 'city',
    weight: 'to_5',
    tax_pct: String(tariffs.default_tax_pct),
    target_margin_pct: String(tariffs.default_target_margin_pct),
  }
}

/** null — пока заполнено не всё, что нужно для расчёта. */
export function toEconomicsInput(form: EconomicsForm): EconomicsInput | null {
  const purchase = Number(form.purchase_cost)
  const price = Number(form.price)
  const percents = [form.commission_pct, form.tax_pct, form.target_margin_pct].map(Number)
  const other = Number(form.other_cost || 0)
  if (form.purchase_cost === '' || !(price > 0) || !(purchase >= 0) || !(other >= 0)) return null
  if (percents.some((value) => !(value >= 0 && value <= 50))) return null
  return {
    purchase_cost: Math.round(purchase),
    other_cost: Math.round(other),
    price: Math.round(price),
    commission_pct: percents[0],
    delivery_type: form.delivery_type,
    weight: form.weight,
    tax_pct: percents[1],
    target_margin_pct: percents[2],
  }
}
