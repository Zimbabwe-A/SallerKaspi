import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { useLogout, useMe } from '../api/auth'
import { currentShop, useShops, useSource } from '../api/client'
import { usePeriodSearch } from '../lib/period'
import { PeriodPicker } from './PeriodPicker'

// Значки пунктов меню (линии 24×24).
const ICONS: Record<string, string> = {
  '/': 'M4 19V9M10 19V5M16 19v-7M22 19H2',
  '/products': 'M4 7l8-4 8 4v10l-8 4-8-4zM4 7l8 4 8-4M12 11v10',
  '/market': 'M3 17l6-6 4 4 8-8M15 7h6v6',
  '/orders': 'M9 5h6M9 3h6a1 1 0 0 1 1 1v2H8V4a1 1 0 0 1 1-1zM8 5H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M8 12h8M8 16h5',
  '/stock': 'M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10M7.5 5l9 4',
  '/bot': 'M12 3v3M7 9h10a3 3 0 0 1 3 3v4a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-4a3 3 0 0 1 3-3zM9 14h.01M15 14h.01',
  '/waybills': 'M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v7H6z',
}

const NAV = [
  { to: '/', label: 'Аналитика магазина', end: true },
  { to: '/products', label: 'Товары', end: false },
  { to: '/market', label: 'Аналитика рынка', end: false },
  { to: '/orders', label: 'Заказы', end: false },
  { to: '/stock', label: 'Склад', end: false },
  { to: '/bot', label: 'Бот цен', end: false },
  { to: '/waybills', label: 'Накладные', end: false },
]

function NavIcon({ to }: { to: string }) {
  return (
    <svg viewBox="0 0 24 24" className="size-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={ICONS[to]} />
    </svg>
  )
}

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="cta-gradient grid size-9 place-items-center rounded-xl text-white">
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 3v18h18" strokeLinecap="round" />
          <path d="m7 15 4-4 3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <span className="text-lg font-bold tracking-tight">
        Аналитика <span className="bg-gradient-to-r from-[#d48bff] to-[#ff7ac6] bg-clip-text text-transparent">Kaspi</span>
      </span>
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
        className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-sm text-ink"
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

function Account() {
  const me = useMe()
  const logout = useLogout()
  if (!me.data) return null
  return (
    <div className="flex items-center justify-between gap-2 border-t border-white/10 pt-3 text-xs text-on-brand/70">
      <span className="truncate" title={me.data.login}>{me.data.name || me.data.login}</span>
      <button type="button" onClick={() => logout.mutate()} className="shrink-0 font-bold text-on-brand hover:underline">Выйти</button>
    </div>
  )
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const search = usePeriodSearch()
  // На «Товарах» свой выбор срока, а боту период не нужен — общий выбор дат там лишний.
  const { pathname } = useLocation()
  const showPeriod = !['/products', '/bot', '/costs', '/waybills', '/market'].includes(pathname)

  const links = NAV.map((item) => (
    <NavLink
      key={item.to}
      to={{ pathname: item.to, search }}
      end={item.end}
      onClick={() => setMenuOpen(false)}
      className={({ isActive }) =>
        `flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-[15px] font-semibold tracking-tight transition-all ${
          isActive ? 'nav-active' : 'text-on-brand/85 hover:bg-white/10 hover:text-white'
        }`
      }
    >
      <NavIcon to={item.to} />
      {item.label}
    </NavLink>
  ))

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[260px_1fr]">
      <aside className="brand-gradient sticky top-0 hidden h-dvh flex-col gap-6 border-r border-line p-4 text-on-brand md:flex">
        <Logo />
        <nav className="flex flex-col gap-1">{links}</nav>
        <div className="mt-auto flex flex-col gap-3"><ShopPicker /><Account /></div>
      </aside>

      <header className="brand-gradient sticky top-0 z-20 px-4 py-3 text-on-brand md:hidden">
        <div className="flex items-center justify-between">
          <Logo />
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="cta-gradient inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-bold text-white"
            aria-expanded={menuOpen}
          >
            <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
              <path d={menuOpen ? 'M6 6l12 12M18 6L6 18' : 'M4 7h16M4 12h16M4 17h16'} />
            </svg>
            Меню
          </button>
        </div>
        {menuOpen && (
          <div className="mt-3 flex flex-col gap-3">
            <nav className="flex flex-col gap-1">{links}</nav>
            <ShopPicker />
            <Account />
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
