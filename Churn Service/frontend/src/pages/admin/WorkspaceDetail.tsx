import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Ban, CheckCircle2, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Button, Card, ErrorBox, Field, Input, JobBadge, Notice, Select, Spinner, Stat, Td, Th } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { fmt, timeAgo } from '../../lib/format'
import { AdminHeader, Dialog, Pill, type AdminOrgDetail } from './shared'
import { usePlans } from './hooks'

export default function WorkspaceDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const plans = usePlans()
  const [confirmName, setConfirmName] = useState('')
  const [deleting, setDeleting] = useState(false)

  const query = useQuery({ queryKey: ['admin', 'org', id], queryFn: () => api<AdminOrgDetail>(`/api/admin/organizations/${id}`) })
  const update = useMutation({
    mutationFn: (body: Record<string, string>) => api<AdminOrgDetail>(`/api/admin/organizations/${id}`, { method: 'PATCH', body }),
    onSuccess: (data) => {
      queryClient.setQueryData(['admin', 'org', id], data)
      void queryClient.invalidateQueries({ queryKey: ['admin'] })
    },
  })
  const remove = useMutation({
    mutationFn: () => api<void>(`/api/admin/organizations/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      navigate('/admin/workspaces', { replace: true })
      // Refresh the lists, but don't refetch the workspace that no longer exists.
      void queryClient.invalidateQueries({ queryKey: ['admin'], predicate: (q) => q.queryKey[1] !== 'org' })
      queryClient.removeQueries({ queryKey: ['admin', 'org', id] })
    },
  })

  if (query.isPending) return <Spinner />
  if (query.error) return <ErrorBox error={query.error} />
  const o = query.data
  const own = user?.organization.id === o.id
  const suspended = o.status !== 'active'

  return (
    <>
      <Link to="/admin/workspaces" className="mb-4 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Workspaces
      </Link>
      <AdminHeader title={o.name}
        subtitle={<>Workspace #{o.id} · created {fmt.date(o.created_at)} {suspended ? <Pill tone="bad">Suspended</Pill> : <Pill tone="good">Active</Pill>}</>}
        actions={
          <>
            {suspended ? (
              <Button variant="secondary" loading={update.isPending} onClick={() => update.mutate({ status: 'active' })}>
                <CheckCircle2 className="size-4" aria-hidden /> Reactivate
              </Button>
            ) : (
              <Button variant="danger" loading={update.isPending} disabled={own} title={own ? "You can't suspend your own workspace" : undefined}
                onClick={() => update.mutate({ status: 'suspended' })}>
                <Ban className="size-4" aria-hidden /> Suspend
              </Button>
            )}
            <Button variant="danger" disabled={own} onClick={() => { setConfirmName(''); setDeleting(true) }}>
              <Trash2 className="size-4" aria-hidden /> Delete
            </Button>
          </>
        } />
      {update.error && <div className="mb-4"><ErrorBox error={update.error} /></div>}
      {suspended && <div className="mb-4"><Notice tone="warning">Members of this workspace can't sign in or use the app until it is reactivated.</Notice></div>}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Customers" value={o.customers == null ? '–' : fmt.int(o.customers)} note={o.data_source ? `${o.data_source} data` : 'no data yet'} />
        <Stat label="Production model" value={o.model_version ? `v${o.model_version}` : '–'} />
        <Stat label="Saved campaigns" value={fmt.int(o.campaigns)} />
        <Stat label="Last activity" value={timeAgo(o.last_activity)} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_2fr] [&>*]:min-w-0">
        <Card title="Plan">
          <Field label="Current plan" hint="Changes take effect immediately.">
            <Select value={o.plan} disabled={update.isPending} onChange={(e) => update.mutate({ plan: e.target.value })}>
              {plans.data?.map((p) => <option key={p.key} value={p.key}>{p.name} · ${p.monthly_price}/mo{p.active ? '' : ' (hidden)'}</option>)}
            </Select>
          </Field>
          <dl className="mt-5 space-y-2 border-t border-hairline pt-4 text-sm">
            <div className="flex justify-between"><dt className="text-ink-2">Offer cost</dt><dd>{fmt.cents(o.economics.offer_cost)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-2">Success rate</dt><dd>{fmt.pct(o.economics.retention_success_rate, 0)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-2">Months of value</dt><dd>{o.economics.months_of_value}</dd></div>
          </dl>
        </Card>
        <Card title={`Members (${o.users_list.length})`} action={<Link to={`/admin/users?q=${encodeURIComponent(o.name)}`} className="text-xs font-medium text-accent">Manage in Users</Link>}>
          <div className="-m-5 overflow-x-auto">
            <table className="w-full">
              <thead><tr><Th>Name</Th><Th>Email</Th><Th>Role</Th><Th>Status</Th><Th>Joined</Th></tr></thead>
              <tbody>
                {o.users_list.map((u) => (
                  <tr key={u.id}>
                    <Td className="font-medium">{u.name}{u.is_admin && <span className="ml-2"><Pill tone="bad">Admin</Pill></span>}</Td>
                    <Td className="text-ink-2">{u.email}</Td>
                    <Td className="capitalize">{u.role}</Td>
                    <Td>{u.is_active ? <Pill tone="good">Active</Pill> : <Pill>Disabled</Pill>}</Td>
                    <Td className="text-ink-2">{timeAgo(u.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card title="Recent jobs" className="mt-4" action={<Link to={`/admin/jobs?organization_id=${o.id}`} className="text-xs font-medium text-accent">All jobs</Link>}>
        {o.jobs.length === 0 ? <p className="text-sm text-ink-2">No jobs yet.</p> : (
          <div className="-m-5 overflow-x-auto">
            <table className="w-full">
              <thead><tr><Th>Job</Th><Th>Status</Th><Th>Message</Th><Th>Started</Th><Th>Finished</Th></tr></thead>
              <tbody>
                {o.jobs.map((j) => (
                  <tr key={j.id}>
                    <Td className="font-medium">#{j.id} {j.kind}</Td>
                    <Td><JobBadge status={j.status} /></Td>
                    <Td className="max-w-80 truncate text-ink-2">{j.status === 'failed' ? j.error?.split('\n')[0] : j.message}</Td>
                    <Td className="text-ink-2">{fmt.date(j.started_at ?? j.created_at)}</Td>
                    <Td className="text-ink-2">{fmt.date(j.finished_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Dialog open={deleting} title="Delete this workspace?" onClose={() => setDeleting(false)}>
        <p className="text-sm text-ink-2">
          This permanently deletes <b className="text-ink">{o.name}</b>, its {o.users_list.length} member account(s), all uploaded data,
          models, scores and campaigns. It can't be undone.
        </p>
        <Field label={`Type "${o.name}" to confirm`}>
          <Input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} autoFocus />
        </Field>
        {remove.error && <div className="mt-3"><ErrorBox error={remove.error} /></div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setDeleting(false)}>Cancel</Button>
          <Button variant="danger" loading={remove.isPending} disabled={confirmName.trim() !== o.name} onClick={() => remove.mutate()}>
            Delete permanently
          </Button>
        </div>
      </Dialog>
    </>
  )
}
