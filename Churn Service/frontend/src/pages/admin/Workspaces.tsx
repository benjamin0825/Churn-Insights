import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router'
import { ErrorBox, Input, Select, Spinner, Td, Th } from '../../components/ui'
import { api } from '../../lib/api'
import { fmt, timeAgo } from '../../lib/format'
import { useDebouncedParam, usePlans } from './hooks'
import { AdminHeader, Pager, Pill, type AdminOrg, type Page } from './shared'

export default function Workspaces() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [q, setQ] = useDebouncedParam(params, setParams, 'q')
  const plans = usePlans()
  const planName = (key: string) => plans.data?.find((p) => p.key === key)?.name ?? key

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }
  const query = useQuery({
    queryKey: ['admin', 'orgs', params.toString()],
    queryFn: () => api<Page<AdminOrg>>(`/api/admin/organizations?${params.toString()}`),
    placeholderData: keepPreviousData,
  })

  return (
    <>
      <AdminHeader title="Workspaces" subtitle="Every organization that has signed up" />
      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative min-w-60 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name or member email" className="w-full pl-9" aria-label="Search workspaces" />
        </div>
        <Select value={params.get('plan') ?? ''} onChange={(e) => set('plan', e.target.value)} className="w-40" aria-label="Plan">
          <option value="">All plans</option>
          {plans.data?.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
        </Select>
        <Select value={params.get('status') ?? ''} onChange={(e) => set('status', e.target.value)} className="w-40" aria-label="Status">
          <option value="">Any status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </Select>
      </div>

      {query.error && <ErrorBox error={query.error} />}
      {query.isPending ? <Spinner /> : query.data && (
        <div className="rounded-lg bg-surface shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr><Th>Workspace</Th><Th>Owner</Th><Th>Plan</Th><Th>Status</Th><Th align="right">Users</Th><Th align="right">Customers</Th><Th>Model</Th><Th>Last activity</Th><Th>Created</Th></tr>
              </thead>
              <tbody>
                {query.data.items.map((o) => (
                  <tr key={o.id} tabIndex={0} className="cursor-pointer hover:bg-surface-2"
                    onClick={() => navigate(`/admin/workspaces/${o.id}`)}
                    onKeyDown={(e) => e.key === 'Enter' && navigate(`/admin/workspaces/${o.id}`)}>
                    <Td><span className="font-medium text-ink">{o.name}</span> <span className="text-xs text-muted">#{o.id}</span></Td>
                    <Td className="text-ink-2">{o.owner_email ?? '–'}</Td>
                    <Td><Pill tone="accent">{planName(o.plan)}</Pill></Td>
                    <Td>{o.status === 'active' ? <Pill tone="good">Active</Pill> : <Pill tone="bad">Suspended</Pill>}</Td>
                    <Td align="right">{fmt.int(o.users)}</Td>
                    <Td align="right">{o.customers == null ? '–' : fmt.int(o.customers)}{o.data_source === 'demo' && <span className="ml-1 text-xs text-muted">demo</span>}</Td>
                    <Td className="text-ink-2">{o.model_version ? `v${o.model_version}` : '–'}</Td>
                    <Td className="text-ink-2">{timeAgo(o.last_activity)}</Td>
                    <Td className="text-ink-2">{timeAgo(o.created_at)}</Td>
                  </tr>
                ))}
                {query.data.items.length === 0 && (
                  <tr><td colSpan={9} className="px-3 py-10 text-center text-sm text-ink-2">No workspaces match.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <Pager page={query.data.page} total={query.data.total} pageSize={query.data.page_size} onPage={(p) => set('page', String(p))} />
        </div>
      )}
    </>
  )
}
