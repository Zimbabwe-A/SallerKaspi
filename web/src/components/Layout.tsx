import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { currentShop, useShops, useSource } from '../api/client'
import { usePeriodSearch } from '../lib/period'
import { PeriodPicker } from './PeriodPicker'

const NAV = [
  { to: '/', label: 'Аналитика магазина', end: true },
  { to: '/products', label: 'Товары', end: false },
  { to: '/market', label: 'Рынок', end: false },
  { to: '/bot', label: 'Бот цен', end: false },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid size-8 place-items-center rounded-lg bg-on-brand text-brand">
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 3v18h18" strokeLinecap="round" />
          <path d="m7 15 4-4 3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <span className="font-semibold">Аналитика Kaspi</span>
    </div>
  )
}

const syncedText = (iso: string | null) =>
  iso ? `обновлено ${new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}` : ''

/** Выбор магазина. Смена магазина перезагружает страницу, чтобы не смешать данные двух магазинов. */
function ShopPicker() {
  const shops = useShops()
  const source = useSource()
  const value = currentShop()

  const choose = (id: string) => {
    const params = new URLSearchParams(window.location.search)
    if (id === 'demo') params.delete('shop')
    else params.set('shop', id)
    window.location.assign(`${window.location.pathname}${params.size ? `?${params}` : ''}`)
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="shop" className="text-xs text-on-brand/70">Магазин</label>
      <select
        id="shop"
        value={value}
        onChange={(e) => choose(e.target.value)}
        className="w-full rounded-lg border-0 bg-on-brand px-2 py-1.5 text-sm text-ink"
      >
        {(shops.data ?? [{ id: 'demo', name: 'Демо-магазин', kind: 'test' as const, ready: true }]).map((s) => (
          <option key={s.id} value={s.id}>
            {s.kind === 'test' ? `${s.name} (тестовые данные)` : s.name}
          </option>
        ))}
      </select>
      <p className="text-xs text-on-brand/70">
        {source.data?.source === 'kaspi'
          ? `Данные Kaspi · ${syncedText(source.data.synced_at)}`
          : source.error
            ? 'Заказы ещё не загружены'
            : 'Тестовые данные'}
      </p>
    </div>
  )
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const search = usePeriodSearch()
  // На «Товарах» свой выбор срока, а боту период не нужен — общий выбор дат там лишний.
  const { pathname } = useLocation()
  const showPeriod = !['/products', '/bot', '/costs'].includes(pathname)

  const links = NAV.map((item) => (
    <NavLink
      key={item.to}
      to={{ pathname: item.to, search }}
      end={item.end}
      onClick={() => setMenuOpen(false)}
      className={({ isActive }) =>
        `rounded-lg px-3 py-2 text-sm transition-colors ${
          isActive ? 'bg-on-brand font-semibold text-brand shadow-sm' : 'text-on-brand/80 hover:bg-on-brand/10 hover:text-on-brand'
        }`
      }
    >
      {item.label}
    </NavLink>
  ))

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[220px_1fr]">
      <aside className="brand-gradient sticky top-0 hidden h-dvh flex-col gap-6 p-4 text-on-brand md:flex">
        <Logo />
        <nav className="flex flex-col gap-1">{links}</nav>
        <div className="mt-auto"><ShopPicker /></div>
      </aside>

      <header className="brand-gradient sticky top-0 z-20 px-4 py-3 text-on-brand md:hidden">
        <div className="flex items-center justify-between">
          <Logo />
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="rounded-lg bg-on-brand px-3 py-1.5 text-sm text-brand"
            aria-expanded={menuOpen}
          >
            Меню
          </button>
        </div>
        {menuOpen && (
          <div className="mt-3 flex flex-col gap-3">
            <nav className="flex flex-col gap-1">{links}</nav>
            <ShopPicker />
          </div>
        )}
      </header>

      <main className="min-w-0 px-4 py-5 md:px-8 md:py-7">
        <div className="mx-auto flex max-w-6xl flex-col gap-5">
          {showPeriod && <PeriodPicker />}
          <Outlet />
        </div>
      </main>
    </div>
  )
}
