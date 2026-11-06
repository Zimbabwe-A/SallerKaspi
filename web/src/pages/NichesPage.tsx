import { useState } from 'react'
import type { FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { useCandidates, useDeleteCandidate, useSaveCandidate, useTariffs } from '../api/client'
import type { Candidate, CandidateInput, Tariffs } from '../api/types'
import { EconomicsFields, Field, inputClass } from '../components/EconomicsFields'
import { Card, ErrorBox, Loading, PageTitle, VerdictBadge } from '../components/ui'
import { emptyEconomics, toEconomicsInput } from '../lib/economicsForm'
import type { EconomicsForm } from '../lib/economicsForm'
import { int, money, pct } from '../lib/format'

interface MarketForm {
  name: string
  url: string
  sellers: string
  reviews: string
  min_price: string
  notes: string
}

const EMPTY_MARKET: MarketForm = { name: '', url: '', sellers: '', reviews: '', min_price: '', notes: '' }

function fromCandidate(c: Candidate): { economics: EconomicsForm; market: MarketForm } {
  return {
    economics: {
      purchase_cost: String(c.purchase_cost),
      other_cost: String(c.other_cost),
      price: String(c.price),
      commission_pct: String(c.commission_pct),
      delivery_type: c.delivery_type,
      weight: c.weight,
      tax_pct: String(c.tax_pct),
      target_margin_pct: String(c.target_margin_pct),
    },
    market: {
      name: c.name,
      url: c.url ?? '',
      sellers: String(c.sellers),
      reviews: String(c.reviews),
      min_price: c.min_price === null ? '' : String(c.min_price),
      notes: c.notes,
    },
  }
}

function CandidateForm({ tariffs, candidate, prefill, onDone }: {
  tariffs: Tariffs
  candidate?: Candidate
  prefill?: EconomicsForm
  onDone: () => void
}) {
  const initial = candidate ? fromCandidate(candidate) : null
  const [economics, setEconomics] = useState(initial?.economics ?? prefill ?? emptyEconomics(tariffs))
  const [market, setMarket] = useState(initial?.market ?? EMPTY_MARKET)
  const save = useSaveCandidate()
  const set = (key: keyof MarketForm, value: string) => setMarket({ ...market, [key]: value })

  const input = toEconomicsInput(economics)
  const ready = input !== null && market.name.trim() !== ''

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!input || !ready) return
    const data: CandidateInput = {
      ...input,
      name: market.name.trim(),
      url: market.url.trim() || null,
      sellers: Math.max(1, Math.round(Number(market.sellers) || 1)),
      reviews: Math.max(0, Math.round(Number(market.reviews) || 0)),
      min_price: Number(market.min_price) > 0 ? Math.round(Number(market.min_price)) : null,
      notes: market.notes.trim(),
    }
    save.mutate({ id: candidate?.id, data }, { onSuccess: onDone })
  }

  return (
    <Card title={candidate ? 'Изменить товар' : 'Новый товар'}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Название">
            <input value={market.name} onChange={(e) => set('name', e.target.value)} maxLength={200} className={inputClass} />
          </Field>
          <Field label="Ссылка на товар">
            <input type="url" value={market.url} onChange={(e) => set('url', e.target.value)} placeholder="https://kaspi.kz/shop/p/…" className={inputClass} />
          </Field>
        </div>

        <h3 className="text-sm font-semibold">Что вы видите на карточке Kaspi</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Продавцов на карточке">
            <input type="number" min="1" value={market.sellers} onChange={(e) => set('sellers', e.target.value)} className={`${inputClass} tabular`} />
          </Field>
          <Field label="Отзывов">
            <input type="number" min="0" value={market.reviews} onChange={(e) => set('reviews', e.target.value)} className={`${inputClass} tabular`} />
          </Field>
          <Field label="Минимальная цена, ₸">
            <input type="number" min="1" value={market.min_price} onChange={(e) => set('min_price', e.target.value)} className={`${inputClass} tabular`} />
          </Field>
        </div>

        <h3 className="text-sm font-semibold">Ваша экономика</h3>
        <EconomicsFields form={economics} onChange={setEconomics} tariffs={tariffs} />

        <Field label="Заметки">
          <textarea value={market.notes} onChange={(e) => set('notes', e.target.value)} maxLength={1000} rows={2} placeholder="Поставщик, срок поставки, сезонность" className={inputClass} />
        </Field>

        {save.error && <ErrorBox error={save.error} />}
        <div className="flex flex-wrap items-center gap-2">
          <button type="submit" disabled={!ready || save.isPending} className="rounded-lg bg-ink px-3 py-2 text-sm font-medium text-page disabled:opacity-40">
            {candidate ? 'Сохранить' : 'Добавить'}
          </button>
          <button type="button" onClick={onDone} className="rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-hover">Отмена</button>
          {!ready && <span className="text-xs text-muted">Нужны название, закупка и цена продажи</span>}
        </div>
      </form>
    </Card>
  )
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={`tabular text-sm font-medium ${tone ?? ''}`}>{value}</dd>
    </div>
  )
}

function CandidateCard({ candidate: c, place, onEdit }: { candidate: Candidate; place: number; onEdit: () => void }) {
  const remove = useDeleteCandidate()
  const e = c.economics
  const link = c.url?.startsWith('https://') ? c.url : null

  return (
    <Card>
      <div className="flex items-start gap-3">
        <div className="w-14 shrink-0 text-center">
          <p className="text-2xl font-semibold tracking-tight">{c.score}</p>
          <p className="text-xs text-muted">из 100</p>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted">{place}.</span>
            {link ? (
              <a href={link} target="_blank" rel="noreferrer" className="min-w-0 break-words font-semibold hover:underline">{c.name}</a>
            ) : (
              <span className="min-w-0 break-words font-semibold">{c.name}</span>
            )}
            <VerdictBadge verdict={c.verdict} />
          </div>
          <p className="mt-1 text-xs text-muted">
            Маржа {c.score_parts.margin}/50 · Спрос {c.score_parts.demand}/25 · Конкуренция {c.score_parts.competition}/25
          </p>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Metric label="Цена" value={money(c.price)} />
        <Metric label="Прибыль с 1 шт" value={money(e.profit)} tone={e.profit > 0 ? 'text-good' : 'text-critical'} />
        <Metric label="Маржа" value={pct(e.margin_pct)} />
        <Metric label="Продавцов" value={int(c.sellers)} />
        <Metric label="Отзывов" value={int(c.reviews)} />
        <Metric
          label="Прибыль при мин. цене"
          value={c.profit_at_min_price !== null ? money(c.profit_at_min_price) : '—'}
          tone={c.profit_at_min_price !== null && c.profit_at_min_price <= 0 ? 'text-critical' : undefined}
        />
      </dl>

      {c.warnings.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1 text-sm text-ink-2">
          {c.warnings.map((w) => <li key={w}>▲ {w}</li>)}
        </ul>
      )}
      {c.notes && <p className="mt-3 whitespace-pre-wrap break-words text-sm text-ink-2">{c.notes}</p>}

      <div className="mt-3 flex items-center gap-1 border-t border-line pt-3">
        <button type="button" onClick={onEdit} className="rounded-lg px-2.5 py-1 text-sm text-ink-2 hover:bg-hover">Изменить</button>
        <button
          type="button"
          disabled={remove.isPending}
          onClick={() => window.confirm(`Удалить «${c.name}»?`) && remove.mutate(c.id)}
          className="rounded-lg px-2.5 py-1 text-sm text-critical hover:bg-hover"
        >
          Удалить
        </button>
        <span className="ml-auto text-xs text-muted">Данные от {c.updated_at.split('-').reverse().join('.')}</span>
      </div>
    </Card>
  )
}

export function NichesPage() {
  const { data: tariffs, error: tariffsError } = useTariffs()
  const { data: candidates, error } = useCandidates()
  const prefill = (useLocation().state as { prefill?: EconomicsForm } | null)?.prefill
  const navigate = useNavigate()
  const [editing, setEditing] = useState<number | 'new' | null>(prefill ? 'new' : null)

  if (error || tariffsError) return <ErrorBox error={error ?? tariffsError} />
  if (!candidates || !tariffs) return <Loading />

  const close = () => {
    setEditing(null)
    // Иначе данные из калькулятора снова откроют форму при обновлении страницы.
    if (prefill) navigate('.', { replace: true, state: null })
  }

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle subtitle="Сравните товары-кандидаты и выберите, с чего начать">Подбор ниш</PageTitle>
        {editing === null && (
          <button type="button" onClick={() => setEditing('new')} className="rounded-lg bg-ink px-3 py-2 text-sm font-medium text-page">
            Добавить товар
          </button>
        )}
      </div>

      <p className="text-sm text-ink-2">
        Цифры с карточек вносятся вручную: Kaspi запрещает автоматический сбор данных. Отзывы — лишь примерный признак спроса,
        а оценка помогает сравнить кандидатов, но не обещает продажи.
      </p>

      {editing === 'new' && <CandidateForm tariffs={tariffs} prefill={prefill} onDone={close} />}

      {candidates.length === 0 && editing === null && (
        <Card><p className="text-sm text-muted">Пока нет ни одного товара. Добавьте первого кандидата, чтобы увидеть оценку.</p></Card>
      )}

      {candidates.map((c, index) =>
        editing === c.id ? (
          <CandidateForm key={c.id} tariffs={tariffs} candidate={c} onDone={close} />
        ) : (
          <CandidateCard key={c.id} candidate={c} place={index + 1} onEdit={() => setEditing(c.id)} />
        ),
      )}
    </>
  )
}
