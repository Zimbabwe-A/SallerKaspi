import { useRef, useState } from 'react'
import { Card, PageTitle } from '../components/ui'
import { useMe } from '../api/auth'

// Варианты печати: три ряда, как в привычных ботах для накладных.
const LAYOUTS = [
  [
    { id: 'a4x4', label: '4 на A4' },
    { id: 'a4x8', label: '8 на A4' },
    { id: 'a4x9', label: '9 на A4' },
    { id: 'a4x1', label: '1 на A4' },
  ],
  [
    { id: '75x120', label: 'Термопринтер 75/120' },
    { id: '100x150', label: 'Термопринтер 100/150' },
  ],
  [{ id: 'join', label: 'Просто объединить' }],
]

const fileName = (count: number) => {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `nakladnye_${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}_${pad(d.getHours())}-${pad(d.getMinutes())}_${count}sht.pdf`
}

/** Сразу сохраняет файл в папку загрузок браузера, без открытия вкладки. */
const save = (url: string, name: string) => {
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
}

const kb = (n: number) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} МБ` : `${Math.max(1, Math.round(n / 1024))} КБ`)

/** Склеиваем накладные Kaspi в один PDF: по одной наклейке на страницу, подряд — для потоковой печати. */
export function WaybillsPage() {
  const [files, setFiles] = useState<File[]>([])
  const [size, setSize] = useState('75x120')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ url: string; count: number; name: string; skipped: number } | null>(null)
  const me = useMe()
  const canSkip = me.data?.features?.includes('waybill_history') ?? false
  const [skipPrinted, setSkipPrinted] = useState(true)
  const [allPrinted, setAllPrinted] = useState(false)
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const add = (list: FileList | null) => {
    if (!list) return
    const pdfs = [...list].filter((f) => {
      const name = f.name.toLowerCase()
      return f.type === 'application/pdf' || name.endsWith('.pdf') || name.endsWith('.zip') || /zip/.test(f.type)
    })
    if (pdfs.length < list.length) setError('Добавлены только PDF и ZIP, остальные файлы пропущены.')
    else setError(null)
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => f.name + f.size))
      return [...prev, ...pdfs.filter((f) => !seen.has(f.name + f.size))]
    })
    setResult(null)
  }

  const build = async (skip = canSkip && skipPrinted) => {
    setBusy(true)
    setError(null)
    setAllPrinted(false)
    try {
      const form = new FormData()
      files.forEach((f) => form.append('files', f))
      form.append('size', size)
      form.append('skip_printed', String(skip))
      const response = await fetch('/api/waybills/merge', { method: 'POST', body: form, credentials: 'same-origin' })
      if (response.status === 409) setAllPrinted(true)
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail ?? `Ошибка ${response.status}`)
      }
      const blob = await response.blob()
      if (result) URL.revokeObjectURL(result.url)
      const url = URL.createObjectURL(blob)
      const count = Number(response.headers.get('X-Labels') ?? 0)
      const name = fileName(count)
      setResult({ url, count, name, skipped: Number(response.headers.get('X-Skipped') ?? 0) })
      save(url, name)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не получилось собрать накладные')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageTitle subtitle="Все накладные одним файлом — принтер печатает их подряд, без открытия каждой по отдельности">
        Накладные
      </PageTitle>

      <Card>
        <ol className="grid gap-3 text-sm md:grid-cols-3">
          <li><b>1.</b> В кабинете Kaspi скачайте накладные заказов (файлы <code>W_….pdf</code>).</li>
          <li><b>2.</b> Перетащите их все сюда сразу — можно и одним ZIP-архивом.</li>
          <li><b>3.</b> Нажмите «Собрать и скачать» — один PDF сразу сохранится в папку загрузок.</li>
        </ol>
      </Card>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); add(e.dataTransfer.files) }}
        onClick={() => input.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        className={`card grid cursor-pointer place-items-center gap-2 rounded-2xl border-2 border-dashed p-10 text-center transition ${
          dragging ? 'border-[var(--cta)] bg-[color-mix(in_srgb,var(--cta)_10%,var(--surface))]' : 'border-line'
        }`}
      >
        <svg viewBox="0 0 24 24" className="size-10 text-[var(--accent)]" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v7H6z" />
        </svg>
        <p className="text-lg font-bold">Перетащите накладные сюда</p>
        <p className="text-sm text-ink-2">или нажмите, чтобы выбрать файлы · можно сразу много · PDF или ZIP-архив с PDF</p>
        <input ref={input} type="file" accept="application/pdf,.pdf,application/zip,.zip" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = '' }} />
      </div>

      {files.length > 0 && (
        <Card
          title={`Выбрано: ${files.length}`}
          action={
            <button type="button" onClick={() => { setFiles([]); setResult(null) }} className="text-sm text-ink-2 hover:underline">
              Очистить
            </button>
          }
        >
          <ul className="max-h-64 divide-y divide-line overflow-auto text-sm">
            {files.map((f, i) => (
              <li key={f.name + f.size} className="flex items-center gap-3 py-2">
                <span className="w-6 text-right text-xs text-muted">{i + 1}</span>
                <span className="min-w-0 flex-1 truncate">{f.name}</span>
                <span className="text-xs text-muted">{kb(f.size)}</span>
                <button
                  type="button"
                  aria-label={`Убрать ${f.name}`}
                  onClick={() => setFiles((prev) => prev.filter((x) => x !== f))}
                  className="text-muted hover:text-critical"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>

          <div className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
            <span className="text-sm font-semibold text-ink-2">Как печатать:</span>
            <div className="grid gap-2">
              {LAYOUTS.map((row, i) => (
                <div key={i} className={`grid gap-2 ${row.length === 4 ? 'grid-cols-2 sm:grid-cols-4' : row.length === 2 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                  {row.map((l) => (
                    <button
                      key={l.id}
                      type="button"
                      onClick={() => setSize(l.id)}
                      aria-pressed={size === l.id}
                      className={`h-12 rounded-xl border text-sm font-semibold transition ${
                        size === l.id ? 'cta-gradient border-transparent text-white' : 'border-line bg-hover text-ink hover:border-[var(--cta)]'
                      }`}
                    >
                      {l.label}
                    </button>
                  ))}
                </div>
              ))}
            </div>
            {canSkip && (
              <label className="flex cursor-pointer items-start gap-2 text-sm">
                <input type="checkbox" checked={skipPrinted} onChange={(e) => setSkipPrinted(e.target.checked)} className="mt-0.5 size-4 accent-[var(--cta)]" />
                <span>
                  <b>Не печатать повторно</b> — накладные, которые вы уже печатали (по номеру заказа), пропускаются.
                  <span className="block text-xs text-muted">Например, напечатали 1–6, теперь загрузили 1–15 — в файл попадут только 7–15.</span>
                </span>
              </label>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() => build()}
              className="cta-gradient mt-1 inline-flex h-12 items-center justify-center gap-2 rounded-xl px-5 text-base font-bold text-white disabled:opacity-50"
            >
              <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v7H6z" />
              </svg>
              {busy ? 'Собираю…' : 'Собрать и скачать'}
            </button>
          </div>
        </Card>
      )}

      {error && (
        <p className="text-sm text-critical">
          {error}
          {allPrinted && (
            <>
              {' '}
              <button type="button" onClick={() => build(false)} className="font-semibold text-accent hover:underline">
                Напечатать всё равно
              </button>
            </>
          )}
        </p>
      )}
      {result && (
        <Card>
          <p className="text-sm">
            Готово: <b>{result.count}</b> {size === 'join' ? 'страниц' : 'наклеек'} — файл <b>{result.name}</b> сохранён в загрузки.
            {result.skipped > 0 && <> Пропущено уже напечатанных: <b>{result.skipped}</b>.</>}{' '}
            <a href={result.url} target="_blank" rel="noopener" className="font-semibold text-accent hover:underline">Открыть PDF</a>
            {' · '}
            <a href={result.url} download={result.name} className="font-semibold text-accent hover:underline">Скачать ещё раз</a>
          </p>
          <p className="mt-1 text-xs text-muted">Файл сохраняется только на вашем компьютере, на сервере накладные не хранятся. Папку для загрузок можно сменить в настройках браузера.</p>
        </Card>
      )}
    </>
  )
}
