import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import type { SetURLSearchParams } from 'react-router'
import { api } from '../../lib/api'
import type { Plan } from './shared'

export function usePlans() {
  return useQuery({ queryKey: ['admin', 'plans'], queryFn: () => api<Plan[]>('/api/admin/plans') })
}

/** A text box bound to a URL search param, written back after a short pause in typing. */
export function useDebouncedParam(params: URLSearchParams, setParams: SetURLSearchParams, key: string) {
  const [value, setValue] = useState(params.get(key) ?? '')
  const current = params.get(key) ?? ''
  useEffect(() => {
    if (value === current) return
    const id = window.setTimeout(() => {
      setParams((prev) => {
        const next = new URLSearchParams(prev)
        if (value) next.set(key, value)
        else next.delete(key)
        next.delete('page')
        return next
      }, { replace: true })
    }, 300)
    return () => window.clearTimeout(id)
  }, [value, current, key, setParams])
  return [value, setValue] as const
}
