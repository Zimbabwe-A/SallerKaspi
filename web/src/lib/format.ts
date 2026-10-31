const number = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const decimal = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 })
const compact = new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 1 })

export const money = (value: number) => `${number.format(value)} ₸`
export const moneyCompact = (value: number) => `${compact.format(value)} ₸`
export const numberCompact = (value: number) => compact.format(value)
export const int = (value: number) => number.format(value)
export const pct = (value: number) => `${decimal.format(value)}%`
export const dec = (value: number) => decimal.format(value)

export function signedPct(value: number) {
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${decimal.format(Math.abs(value))}%`
}

const MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

export function shortDate(iso: string) {
  const [, m, d] = iso.split('-').map(Number)
  return `${d} ${MONTHS[m - 1]}`
}

export function dateRange(start: string, end: string) {
  const f = (iso: string) => iso.split('-').reverse().join('.')
  return start === end ? f(start) : `${f(start)} — ${f(end)}`
}
