import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Button, ErrorBox, JobBadge, Notice, Select, Spinner, Td, Th } from '../../components/ui'
import { api } from '../../lib/api'
import { fmt, timeAgo } from '../../lib/format'
import { AdminHeader, Dialog, Pager, type AdminJob, type Page } from './shared'

const duration = (j: AdminJob) => {
  if (!j.started_at) return '–'
  const seconds = ((j.finished_at ? new Date(j.finished_at) : new Date()).getTime() - new Date(j.started_at).getTime()) / 1000
  return seconds < 90 ? `${Math.round(seconds)} s` : `${Math.round(seconds / 60)} min`
}

export default function Jobs() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState<AdminJob | null>(null)
  const [confirmFail, setConfirmFail] = useState<AdminJob | null>(null)

  const query = useQuery({
    queryKey: ['admin', 'jobs', params.toString()],
    queryFn: () => api<Page<AdminJob>>(`/api/admin/jobs?${params.toString()}`),
    placeholderData: keepPreviousData,
    refetchInterval: 5000,
  })
  const fail = useMutation({
    mutationFn: (id: number) => api(`/api/admin/jobs/${id}/fail`, { method: 'POST' }),
    onSuccess: () => {
      setConfirmFail(null)
      void queryClient.invalidateQueries({ queryKey: ['admin'] })
    },
  })
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next, { replace: true })
  }
  const orgFilter = params.get('organization_id')

  return (
    <>
      <AdminHeader title="Background jobs" subtitle="Data loads, training, scoring and drift checks in every workspace. Refreshes every 5 seconds." />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select value={params.get('status') ?? ''} onChange={(e) => set('status', e.target.value)} className="w-40" aria-label="Status">
          <option value="">Any status</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
        </Select>
        <Select value={params.get('kind') ?? ''} onChange={(e) => set('kind', e.target.value)} className="w-40" aria-label="Kind">
          <option value="">Any kind</option>
          <option value="demo">Demo data</option>
          <option value="train">Training</option>
          <option value="score">Scoring</option>
          <option value="monitor">Drift check</option>
        </Select>
        {orgFilter && (
          <button type="button" onClick={() => set('organization_id', '')} className="rounded-full bg-accent-soft px-3 py-1.5 text-xs font-semibold text-accent">
            Workspace #{orgFilter} ✕
          </button>
        )}
      </div>

      {query.error && <ErrorBox error={query.error} />}
      {query.isPending ? <Spinner /> : query.data && (
        <div className="rounded-lg bg-surface shadow-card">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr><Th>Job</Th><Th>Workspace</Th><Th>Status</Th><Th>Message</Th><Th>Created</Th><Th align="right">Duration</Th><Th /></tr></thead>
              <tbody>
                {query.data.items.map((j) => (
                  <tr key={j.id}>
                    <Td><button type="button" onClick={() => setOpen(j)} className="font-medium text-ink hover:text-accent">#{j.id} {j.kind}</button></Td>
                    <Td><Link to={`/admin/workspaces/${j.organization_id}`} className="text-accent hover:underline">{j.organization_name ?? `#${j.organization_id}`}</Link></Td>
                    <Td><JobBadge status={j.status} /></Td>
                    <Td className="max-w-80 truncate text-ink-2">{j.status === 'failed' ? j.error?.split('\n')[0] : j.message}</Td>
                    <Td className="text-ink-2">{timeAgo(j.created_at)}</Td>
                    <Td align="right">{duration(j)}</Td>
                    <Td align="right">
                      {(j.status === 'queued' || j.status === 'running') && (
                        <Button variant="danger" onClick={() => setConfirmFail(j)}>Mark failed</Button>
                      )}
                    </Td>
                  </tr>
                ))}
                {query.data.items.length === 0 && (
                  <tr><td colSpan={7} className="px-3 py-10 text-center text-sm text-ink-2">No jobs match.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <Pager page={query.data.page} total={query.data.total} pageSize={query.data.page_size} onPage={(p) => set('page', String(p))} />
        </div>
      )}

      <Dialog open={confirmFail != null} title={`Mark job #${confirmFail?.id} as failed?`} onClose={() => setConfirmFail(null)}>
        <Notice tone="warning">
          Use this for jobs stuck as queued or running, for example after a server restart, so the workspace can load data and
          train again. A job that is genuinely still working keeps running in the background.
        </Notice>
        {fail.error && <div className="mt-3"><ErrorBox error={fail.error} /></div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirmFail(null)}>Cancel</Button>
          <Button variant="danger" loading={fail.isPending} onClick={() => confirmFail && fail.mutate(confirmFail.id)}>Mark failed</Button>
        </div>
      </Dialog>

      <Dialog open={open != null} title={`Job #${open?.id} · ${open?.kind}`} onClose={() => setOpen(null)}>
        {open && (
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between"><JobBadge status={open.status} /><span className="text-ink-2">{open.organization_name}</span></div>
            <dl className="grid grid-cols-[110px_1fr] gap-y-1.5">
              <dt className="text-ink-2">Created</dt><dd>{fmt.date(open.created_at)}</dd>
              <dt className="text-ink-2">Started</dt><dd>{fmt.date(open.started_at)}</dd>
              <dt className="text-ink-2">Finished</dt><dd>{fmt.date(open.finished_at)}</dd>
              <dt className="text-ink-2">Message</dt><dd>{open.message || '–'}</dd>
            </dl>
            {Object.keys(open.params).length > 0 && (
              <pre className="overflow-x-auto rounded-lg bg-surface-2 p-3 text-xs">{JSON.stringify(open.params, null, 2)}</pre>
            )}
            {open.error && <pre className="max-h-64 overflow-auto rounded-lg bg-critical-soft p-3 text-xs whitespace-pre-wrap text-critical-ink">{open.error}</pre>}
            {Object.keys(open.result).length > 0 && (
              <pre className="max-h-48 overflow-auto rounded-lg bg-surface-2 p-3 text-xs">{JSON.stringify(open.result, null, 2)}</pre>
            )}
          </div>
        )}
      </Dialog>
    </>
  )
}
