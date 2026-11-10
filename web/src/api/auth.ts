import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

export type User = { id: number; login: string; phone: string; email: string | null; name: string; shops: string[]; features?: string[] }

export type LoginBody = { phone: string; password: string }
export type RegisterBody = LoginBody & { name: string; email: string; code: string }

async function send<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/auth${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'same-origin',
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    const detail = data?.detail
    throw new Error(typeof detail === 'string' ? detail : `Ошибка ${response.status}`)
  }
  return response.json()
}

/** Кто вошёл. null — не вошёл. */
export const useMe = () =>
  useQuery({
    queryKey: ['me'],
    queryFn: () => send<User>('/me').catch(() => null),
    staleTime: Infinity,
    retry: false,
  })

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: LoginBody) => send<User>('/login', body),
    onSuccess: (user) => qc.setQueryData(['me'], user),
  })
}

/** Код отправлен. test_code приходит, пока SMS-сервис не подключён. */
export type CodeSent = { phone: string; resend_in: number; expires_in: number; test_code?: string }

/** Регистрация, шаг 1: данные → код в SMS. */
export const useRegisterStart = () =>
  useMutation({ mutationFn: (body: RegisterBody) => send<CodeSent>('/register/start', body) })

export const useResendCode = () =>
  useMutation({ mutationFn: (phone: string) => send<CodeSent>('/register/resend', { phone }) })

/** Регистрация, шаг 2: код из SMS → аккаунт и вход. */
export function useRegisterVerify() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { phone: string; code: string }) => send<User>('/register/verify', body),
    onSuccess: (user) => qc.setQueryData(['me'], user),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => send<{ ok: boolean }>('/logout', {}),
    onSuccess: () => {
      qc.setQueryData(['me'], null)
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
    },
  })
}
