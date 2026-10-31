import { useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { usePeriodSearch } from '../lib/period'
import { PeriodPicker } from './PeriodPicker'

const NAV = [
  { to: '/', label: 'Обзор', end: true },
  { to: '/products', label: 'Товары', end: false },
  { to: '/market', label: 'Рынок', end: false },
  { to: '/stock', label: 'Остатки', end: false },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid size-8 place-items-center rounded-lg bg-ink text-page">
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 3v18h18" strokeLinecap="round" />
          <path d="m7 15 4-4 3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <span className="font-semibold">Аналитика Kaspi</span>
    </div>
  )
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const search = usePeriodSearch()

  const links = NAV.map((item) => (
    <NavLink
      key={item.to}
      to={{ pathname: item.to, search }}
      end={item.end}
      onClick={() => setMenuOpen(false)}
      className={({ isActive }) =>
        `rounded-lg px-3 py-2 text-sm transition-colors ${
          isActive ? 'bg-surface font-medium text-ink shadow-sm ring-1 ring-line' : 'text-ink-2 hover:bg-hover'
        }`
      }
    >
      {item.label}
    </NavLink>
  ))

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[220px_1fr]">
      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 border-r border-line p-4 md:flex">
        <Logo />
        <nav className="flex flex-col gap-1">{links}</nav>
        <p className="mt-auto text-xs text-muted">Тестовые данные</p>
      </aside>

      <header className="sticky top-0 z-20 border-b border-line bg-page/90 px-4 py-3 backdrop-blur md:hidden">
        <div className="flex items-center justify-between">
          <Logo />
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm"
            aria-expanded={menuOpen}
          >
            Меню
          </button>
        </div>
        {menuOpen && <nav className="mt-3 flex flex-col gap-1">{links}</nav>}
      </header>

      <main className="min-w-0 px-4 py-5 md:px-8 md:py-7">
        <div className="mx-auto flex max-w-6xl flex-col gap-5">
          <PeriodPicker />
          <Outlet />
        </div>
      </main>
    </div>
  )
}
