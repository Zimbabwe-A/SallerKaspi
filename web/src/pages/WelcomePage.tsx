import { useEffect, useState, type FormEvent } from 'react'
import { useLogin, useRegisterStart, useRegisterVerify, useResendCode, type CodeSent } from '../api/auth'

const FEATURES = [
  { title: 'Реальная прибыль', text: 'Выручка минус комиссия Kaspi, доставка, себестоимость и налог — по каждому товару.' },
  { title: 'Цены конкурентов', text: 'Кто дешевле на вашей карточке и где вы теряете первое место.' },
  { title: 'Бот цен', text: 'Сам держит цену в заданных границах, пока вы занимаетесь делом.' },
]

type Mode = 'register' | 'login'

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="cta-gradient grid size-10 place-items-center rounded-xl text-white">
        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 3v18h18" strokeLinecap="round" />
          <path d="m7 15 4-4 3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <span className="text-xl font-bold tracking-tight">
        Аналитика <span className="bg-gradient-to-r from-[#d48bff] to-[#ff7ac6] bg-clip-text text-transparent">Kaspi</span>
      </span>
    </div>
  )
}

function Field({ label, trailing, ...props }: { label: string; trailing?: React.ReactNode } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-semibold text-ink-2">{label}</span>
      <span className="relative">
        <input
          {...props}
          className={`w-full rounded-xl border border-line bg-page px-3.5 py-2.5 text-ink outline-none placeholder:text-muted focus:border-cta focus:ring-2 focus:ring-cta/30 ${trailing ? 'pr-12' : ''}`}
        />
        {trailing && <span className="absolute inset-y-0 right-1.5 flex items-center">{trailing}</span>}
      </span>
    </label>
  )
}

/** Глаз: открытый — пароль виден, перечёркнутый — скрыт. */
function EyeButton({ shown, onToggle }: { shown: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={shown ? 'Скрыть пароль' : 'Показать пароль'}
      aria-pressed={shown}
      title={shown ? 'Скрыть пароль' : 'Показать пароль'}
      className="grid size-9 place-items-center rounded-lg text-muted hover:bg-hover hover:text-ink"
    >
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
        <circle cx="12" cy="12" r="3" />
        {!shown && <path d="M4 4l16 16" />}
      </svg>
    </button>
  )
}

/** 10 цифр после +7 → «+7 (771) 905 8130». */
function formatPhone(d: string) {
  if (!d) return ''
  let out = `+7 (${d.slice(0, 3)}`
  if (d.length > 3) out += `) ${d.slice(3, 6)}`
  if (d.length > 6) out += ` ${d.slice(6, 10)}`
  return out
}

/** Из того, что ввели или вставили, достаём 10 цифр номера. */
function parsePhone(raw: string, prev: string) {
  let digits = (raw.startsWith('+7') ? raw.slice(2) : raw).replace(/\D/g, '')
  if (digits.length === 11 && /^[78]/.test(digits)) digits = digits.slice(1) // вставили 8771… или 7771…
  if (!prev && digits === '8') return '' // привычная «8» в начале — это и есть +7
  // Стёрли скобку или пробел — стираем и цифру перед ними.
  if (digits === prev && raw.length < formatPhone(prev).length) digits = digits.slice(0, -1)
  return digits.slice(0, 10)
}

function PhoneField({ digits, onChange }: { digits: string; onChange: (d: string) => void }) {
  return (
    <Field
      label="Номер телефона"
      type="tel"
      inputMode="tel"
      value={formatPhone(digits)}
      onChange={(e) => onChange(parsePhone(e.target.value, digits))}
      placeholder="+7 (___) ___ ____"
      autoComplete="tel"
      required
    />
  )
}

function ErrorBox({ error }: { error: Error | null }) {
  if (!error) return null
  return (
    <p role="alert" className="rounded-xl border border-critical/40 bg-critical/10 px-3 py-2 text-sm text-critical">
      {error.message}
    </p>
  )
}

/** Секунды до повторной отправки кода (каждая новая отправка — новый CodeStep). */
function useCountdown(from: number) {
  const [left, setLeft] = useState(from)
  useEffect(() => {
    const id = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(id)
  }, [])
  return left
}

/** Регистрация, шаг 2: код из SMS. */
function CodeStep({ sent, onResent, onBack }: { sent: CodeSent; onResent: (s: CodeSent) => void; onBack: () => void }) {
  const [code, setCode] = useState('')
  const verify = useRegisterVerify()
  const resend = useResendCode()
  const left = useCountdown(sent.resend_in)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    verify.mutate({ phone: sent.phone, code })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div>
        <p className="text-xs font-bold uppercase tracking-wide text-muted">Шаг 2 из 2</p>
        <h2 className="mt-1 text-xl font-bold">Подтвердите номер</h2>
        <p className="mt-1 text-sm text-ink-2">
          Мы отправили код в SMS на <b className="whitespace-nowrap text-ink">{formatPhone(sent.phone.slice(2))}</b>
        </p>
      </div>

      {sent.test_code && (
        <p className="rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
          SMS пока не подключены. Тестовый код: <b className="tabular tracking-widest">{sent.test_code}</b>
        </p>
      )}

      <input
        value={code}
        onChange={(e) => {
          const next = e.target.value.replace(/\D/g, '').slice(0, 4)
          setCode(next)
          if (next.length === 4 && !verify.isPending) verify.mutate({ phone: sent.phone, code: next })
        }}
        inputMode="numeric"
        autoComplete="one-time-code"
        aria-label="Код из SMS"
        placeholder="_ _ _ _"
        autoFocus
        required
        className="tabular rounded-xl border border-line bg-page px-3.5 py-3 text-center text-2xl font-bold tracking-[0.6em] text-ink outline-none placeholder:text-muted focus:border-cta focus:ring-2 focus:ring-cta/30"
      />

      <ErrorBox error={verify.error ?? resend.error} />

      <button type="submit" disabled={verify.isPending || code.length < 4} className="cta-gradient rounded-xl py-3 font-bold text-white disabled:opacity-60">
        {verify.isPending ? 'Проверяем…' : 'Подтвердить'}
      </button>

      <div className="flex items-center justify-between text-sm">
        <button type="button" onClick={onBack} className="font-bold text-accent hover:underline">← Изменить данные</button>
        {left > 0 ? (
          <span className="text-muted">Новый код через {left} с</span>
        ) : (
          <button
            type="button"
            disabled={resend.isPending}
            onClick={() => resend.mutate(sent.phone, { onSuccess: onResent })}
            className="font-bold text-accent hover:underline disabled:opacity-60"
          >
            Отправить код ещё раз
          </button>
        )}
      </div>
    </form>
  )
}

function AuthCard() {
  const [mode, setMode] = useState<Mode>('login')
  const [sent, setSent] = useState<(CodeSent & { at: number }) | null>(null)
  const codeSent = (s: CodeSent) => setSent({ ...s, at: Date.now() })
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const login = useLogin()
  const start = useRegisterStart()
  const action = mode === 'register' ? start : login

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (mode === 'register') start.mutate({ name, email, phone, password, code }, { onSuccess: codeSent })
    else login.mutate({ phone, password })
  }

  const switchMode = (next: Mode) => {
    setMode(next)
    setSent(null)
    login.reset()
    start.reset()
  }

  return (
    <div className="card w-full rounded-3xl p-5 md:p-7">
      <div className="mb-5 grid grid-cols-2 gap-1 rounded-xl bg-page p-1" role="tablist">
        {(['login', 'register'] as const).map((m) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            onClick={() => switchMode(m)}
            className={`rounded-lg py-2 text-sm font-bold transition ${mode === m ? 'nav-active' : 'text-ink-2 hover:text-ink'}`}
          >
            {m === 'register' ? 'Регистрация' : 'Вход'}
          </button>
        ))}
      </div>

      {sent ? (
        <CodeStep key={sent.at} sent={sent} onResent={codeSent} onBack={() => { setSent(null); start.reset() }} />
      ) : (
      <form onSubmit={submit} className="flex flex-col gap-4">
        {mode === 'register' && <p className="-mb-1 text-xs font-bold uppercase tracking-wide text-muted">Шаг 1 из 2</p>}
        {mode === 'register' && (
          <Field label="Имя" value={name} onChange={(e) => setName(e.target.value)} placeholder="Как к вам обращаться" autoComplete="name" required />
        )}
        <PhoneField digits={phone} onChange={setPhone} />
        {mode === 'register' && (
          <Field label="Почта" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" autoComplete="email" required />
        )}
        <Field
          label="Пароль"
          type={showPassword ? 'text' : 'password'}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={mode === 'register' ? 'Не короче 8 символов' : ''}
          autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
          minLength={mode === 'register' ? 8 : undefined}
          required
          trailing={<EyeButton shown={showPassword} onToggle={() => setShowPassword((v) => !v)} />}
        />
        {mode === 'register' && (
          <Field
            label="Код приглашения или скидки (если есть)"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="Необязательно"
            autoComplete="off"
          />
        )}

        <ErrorBox error={action.error} />

        <button type="submit" disabled={action.isPending} className="cta-gradient rounded-xl py-3 font-bold text-white disabled:opacity-60">
          {action.isPending ? 'Подождите…' : mode === 'register' ? 'Далее' : 'Войти'}
        </button>
      </form>
      )}

      <div className="my-5 flex items-center gap-3 text-xs text-muted">
        <span className="h-px flex-1 bg-line" />или<span className="h-px flex-1 bg-line" />
      </div>

      <button
        type="button"
        disabled
        title="Вход через Apple появится позже"
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-white py-3 font-bold text-black opacity-50"
      >
        <svg viewBox="0 0 24 24" className="size-5" fill="currentColor" aria-hidden>
          <path d="M16.37 12.6c.02 2.4 2.1 3.2 2.13 3.21-.02.06-.33 1.14-1.1 2.26-.66.97-1.35 1.94-2.43 1.96-1.06.02-1.4-.63-2.62-.63-1.21 0-1.6.61-2.6.65-1.05.04-1.85-1.05-2.52-2.02-1.37-1.98-2.42-5.6-1.01-8.04.7-1.21 1.95-1.98 3.3-2 1.03-.02 2 .7 2.63.7.63 0 1.81-.86 3.05-.73.52.02 1.98.21 2.92 1.58-.08.05-1.74 1.02-1.72 3.03M14.36 4.95c.56-.68.94-1.62.83-2.56-.8.03-1.78.54-2.36 1.21-.52.6-.97 1.56-.85 2.48.9.07 1.82-.45 2.38-1.13" />
        </svg>
        Войти с Apple · скоро
      </button>

      <p className="mt-4 text-center text-xs text-muted">
        {mode === 'register' ? 'Уже есть аккаунт? ' : 'Ещё нет аккаунта? '}
        <button type="button" onClick={() => switchMode(mode === 'register' ? 'login' : 'register')} className="font-bold text-accent hover:underline">
          {mode === 'register' ? 'Войти' : 'Зарегистрироваться'}
        </button>
      </p>
    </div>
  )
}

export function WelcomePage() {
  return (
    <div className="min-h-dvh px-4 py-8 md:px-8 md:py-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-10">
        <Logo />
        <div className="grid items-center gap-10 md:grid-cols-[1.15fr_1fr]">
          <div className="flex flex-col gap-6">
            <h1 className="text-4xl font-bold leading-tight tracking-tight md:text-5xl">
              Сколько вы <span className="bg-gradient-to-r from-[#d48bff] to-[#ff7ac6] bg-clip-text text-transparent">на самом деле</span> зарабатываете на Kaspi?
            </h1>
            <p className="text-lg text-ink-2">
              Аналитика для продавцов Kaspi.kz: прибыль, конкуренты и цены в одном месте. Создайте аккаунт и подключите свой магазин.
            </p>
            <ul className="flex flex-col gap-3">
              {FEATURES.map((f) => (
                <li key={f.title} className="flex gap-3">
                  <span aria-hidden className="mt-1 grid size-6 shrink-0 place-items-center rounded-full bg-good/15 text-good">
                    <svg viewBox="0 0 24 24" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5 9-10" /></svg>
                  </span>
                  <div>
                    <p className="font-bold">{f.title}</p>
                    <p className="text-sm text-ink-2">{f.text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <AuthCard />
        </div>
      </div>
    </div>
  )
}
