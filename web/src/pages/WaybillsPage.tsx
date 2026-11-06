import { useRef, useState } from 'react'
import { Card, PageTitle } from '../components/ui'

const SIZES = [
  { id: '75x120', label: '75 × 120 мм', hint: 'стандарт Kaspi' },
  { id: '100x150', label: '100 × 150 мм', hint: 'крупная этикетка' },
]

const kb = (n: number) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} МБ` : `${Math.max(1, Math.round(n / 1024))} КБ`)

/** Склеиваем накладные Kaspi в один PDF: по одной наклейке на страницу, подряд — для потоковой печати. */
export function WaybillsPage() {
  const [files, setFiles] = useState<File[]>([])
  const [size, setSize] = useState('75x120')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ url: string; count: number } | null>(null)
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const add = (list: FileList | null) => {
    if (!list) return
    const pdfs = [...list].filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length < list.length) setError('Добавлены только PDF-файлы, остальные пропущены.')
    else setError(null)
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => f.name + f.size))
      return [...prev, ...pdfs.filter((f) => !seen.has(f.name + f.size))]
    })
    setResult(null)
  }

  const build = async () => {
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      files.forEach((f) => form.append('files', f))
      form.append('size', size)
      const response = await fetch('/api/waybills/merge', { method: 'POST', body: form })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail ?? `Ошибка ${response.status}`)
      }
      const blob = await response.blob()
      if (result) URL.revokeObjectURL(result.url)
      const url = URL.createObjectURL(blob)
      setResult({ url, count: Number(response.headers.get('X-Labels') ?? 0) })
      window.open(url, '_blank', 'noopener')
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
          <li><b>2.</b> Перетащите их все сюда сразу.</li>
          <li><b>3.</b> Нажмите «Собрать и печатать» — откроется один PDF, напечатайте его.</li>
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
        <p className="text-sm text-ink-2">или нажмите, чтобы выбрать файлы · можно сразу много · только PDF</p>
        <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = '' }} />
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

          <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-line pt-4">
            <span className="text-sm text-ink-2">Размер наклейки:</span>
            <div className="flex gap-1 rounded-xl bg-hover p-1 text-sm">
              {SIZES.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSize(s.id)}
                  className={`rounded-lg px-3 py-1 ${size === s.id ? 'bg-surface font-semibold shadow-sm' : 'text-ink-2'}`}
                  title={s.hint}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={build}
              className="cta-gradient ml-auto inline-flex h-11 items-center gap-2 rounded-xl px-5 text-sm font-semibold text-white disabled:opacity-50"
            >
              <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v7H6z" />
              </svg>
              {busy ? 'Собираю…' : 'Собрать и печатать'}
            </button>
          </div>
        </Card>
      )}

      {error && <p className="text-sm text-critical">{error}</p>}
      {result && (
        <Card>
          <p className="text-sm">
            Готово: <b>{result.count}</b> наклеек в одном файле.{' '}
            <a href={result.url} target="_blank" rel="noopener" className="font-semibold text-accent hover:underline">Открыть PDF</a>
            {' · '}
            <a href={result.url} download={`nakladnye_${result.count}.pdf`} className="font-semibold text-accent hover:underline">Скачать</a>
          </p>
          <p className="mt-1 text-xs text-muted">Файлы никуда не сохраняются — накладные с адресами покупателей остаются только у вас.</p>
        </Card>
      )}
    </>
  )
}
