import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, KeyRound, Search } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Button, ErrorBox, Input, Notice, Select, Spinner, Td, Th } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { timeAgo } from '../../lib/format'
import { useDebouncedParam } from './hooks'
import { AdminHeader, Dialog, Pager, Pill, type AdminUser, type Page } from './shared'

export default function Users() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { user: me } = useAuth()
  const [q, setQ] = useDebouncedParam(params, setParams, 'q')
  const [reset, setReset] = useState<{ email: string; temporary_password: string } | null>(null)
  const [confirmReset, setConfirmReset] = useState<AdminUser | null>(null)
  const [copied, setCopied] = useState(false)

  const query = useQuery({
    queryKey: ['admin', 'users', params.toString()],
    queryFn: () => api<Page<AdminUser>>(`/api/admin/users?${params.toString()}`),
    placeholderData: keepPreviousData,
  })
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<AdminUser> }) =>
      api<AdminUser>(`/api/admin/users/${id}`, { method: 'PATCH', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  })
  const resetPassword = useMutation({
    mutationFn: (id: number) => api<{ email: string; temporary_password: string }>(`/api/admin/users/${id}/reset-password`, { method: 'POST' }),
    onSuccess: (data) => {
      setConfirmReset(null)
      setCopied(false)
      setReset(data)
    },
  })
  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }

  return (
    <>
      <AdminHeader title="Users" subtitle="Every account across all workspaces" />
      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative min-w-60 flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, email or workspace" className="w-full pl-9" aria-label="Search users" />
        </div>
        <Select value={params.get('admins_only') ?? ''} onChange={(e) => setParam('admins_only', e.target.value)} className="w-44" aria-label="Filter">
          <option value="">Everyone</option>
          <option value="true">Admins only</option>
        </Select>
      </div>
      {update.error && <div className="mb-4"><ErrorBox error={update.error} /></div>}

      {query.error && <ErrorBox error={query.error} />}
      {query.isPending ? <Spinner /> : query.data && (
        <div className="rounded-lg bg-surface shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr><Th>User</Th><Th>Workspace</Th><Th>Role</Th><Th>Status</Th><Th>Admin</Th><Th>Joined</Th><Th /></tr></thead>
              <tbody>
                {query.data.items.map((u) => {
                  const self = u.id === me?.id
                  const busy = update.isPending && update.variables?.id === u.id
                  return (
                    <tr key={u.id}>
                      <Td>
                        <div className="font-medium text-ink">{u.name}{self && <span className="ml-2 text-xs text-muted">(you)</span>}</div>
                        <div className="text-xs text-ink-2">{u.email}</div>
                      </Td>
                      <Td><Link to={`/admin/workspaces/${u.organization_id}`} className="text-accent hover:underline">{u.organization_name}</Link></Td>
                      <Td>
                        <Select value={u.role} disabled={busy} className="w-28" aria-label={`Role for ${u.email}`}
                          onChange={(e) => update.mutate({ id: u.id, body: { role: e.target.value as AdminUser['role'] } })}>
                          <option value="owner">Owner</option>
                          <option value="analyst">Analyst</option>
                        </Select>
                      </Td>
                      <Td>
                        <button type="button" disabled={busy || self} title={self ? "You can't disable yourself" : undefined}
                          onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}
                          className="disabled:cursor-not-allowed">
                          {u.is_active ? <Pill tone="good">Active</Pill> : <Pill>Disabled</Pill>}
                        </button>
                      </Td>
                      <Td>
                        <label className="relative inline-flex cursor-pointer items-center gap-2 text-sm">
                          <input type="checkbox" checked={u.is_admin} disabled={busy || self} className="size-4 accent-[var(--accent)]"
                            onChange={(e) => update.mutate({ id: u.id, body: { is_admin: e.target.checked } })} />
                          <span className="sr-only">Admin access for {u.email}</span>
                        </label>
                      </Td>
                      <Td className="text-ink-2">{timeAgo(u.created_at)}</Td>
                      <Td align="right">
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" onClick={() => setConfirmReset(u)}><KeyRound className="size-4" aria-hidden /> Reset password</Button>
                          <Button variant="ghost" disabled={busy || self} onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                            {u.is_active ? 'Disable' : 'Enable'}
                          </Button>
                        </div>
                      </Td>
                    </tr>
                  )
                })}
                {query.data.items.length === 0 && (
                  <tr><td colSpan={7} className="px-3 py-10 text-center text-sm text-ink-2">No users match.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <Pager page={query.data.page} total={query.data.total} pageSize={query.data.page_size} onPage={(p) => setParam('page', String(p))} />
        </div>
      )}

      <Dialog open={confirmReset != null} title="Reset password?" onClose={() => setConfirmReset(null)}>
        <p className="text-sm text-ink-2">
          <b className="text-ink">{confirmReset?.email}</b> gets a new temporary password, and the current password stops
          working. You'll see the new password once, to pass on to them.
        </p>
        {resetPassword.error && <div className="mt-3"><ErrorBox error={resetPassword.error} /></div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirmReset(null)}>Cancel</Button>
          <Button loading={resetPassword.isPending} onClick={() => confirmReset && resetPassword.mutate(confirmReset.id)}>Reset password</Button>
        </div>
      </Dialog>

      <Dialog open={reset != null} title="Temporary password" onClose={() => setReset(null)}>
        <p className="text-sm text-ink-2">Send this to <b className="text-ink">{reset?.email}</b> over a secure channel. It won't be shown again.</p>
        <div className="mt-4 flex items-center gap-2">
          <code className="flex-1 rounded-lg bg-surface-2 px-3 py-2 font-mono text-sm text-ink select-all">{reset?.temporary_password}</code>
          <Button variant="secondary" onClick={() => {
            void navigator.clipboard?.writeText(reset?.temporary_password ?? '').then(() => setCopied(true))
          }}>
            <Copy className="size-4" aria-hidden /> {copied ? 'Copied' : 'Copy'}
          </Button>
        </div>
        <div className="mt-4"><Notice>They can sign in with it right away.</Notice></div>
        <div className="mt-5 flex justify-end"><Button onClick={() => setReset(null)}>Done</Button></div>
      </Dialog>
    </>
  )
}
