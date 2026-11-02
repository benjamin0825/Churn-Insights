import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, getToken, setToken } from './api'
import type { TokenResponse, User } from './types'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (values: { organization: string; name: string; email: string; password: string }) => Promise<void>
  logout: () => void
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(Boolean(getToken()))
  const queryClient = useQueryClient()

  const refresh = useCallback(async () => {
    if (!getToken()) return // initial state already says "signed out, not loading"
    try {
      setUser(await api<User>('/api/me'))
    } catch {
      setToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const onLogout = () => {
      setUser(null)
      queryClient.clear()
    }
    window.addEventListener('churn-service:logout', onLogout)
    return () => window.removeEventListener('churn-service:logout', onLogout)
  }, [refresh, queryClient])

  const accept = useCallback(
    (response: TokenResponse) => {
      queryClient.clear()
      setToken(response.access_token)
      setUser(response.user)
    },
    [queryClient],
  )

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      refresh,
      login: async (email, password) => accept(await api<TokenResponse>('/api/auth/login', { body: { email, password } })),
      register: async (values) => accept(await api<TokenResponse>('/api/auth/register', { body: values })),
      logout: () => {
        // A full load of the home page: clearing the user in place would let the signed-in
        // pages redirect to /login first, and the reload drops every cached query too.
        setToken(null)
        window.location.replace('/')
      },
    }),
    [user, loading, refresh, accept],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
