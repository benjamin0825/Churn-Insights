import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Upload } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Button, Card, ErrorBox, FailedJobNotice, Field, Input, JobBadge, Notice, PageHeader, Select, Spinner, Td, Th } from '../components/ui'
import { api, download, form } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmt } from '../lib/format'
import { useDataStatus } from '../lib/hooks'
import type { Job } from '../lib/types'

const TABLES = [
  { name: 'customers', label: 'Customers', columns: 'customer_id, signup_date, age, region, plan, internet_service, has_streaming, contract_type, payment_method, paperless_billing, dependents, acquisition_channel, churn_date' },
  { name: 'usage', label: 'Weekly usage', columns: 'customer_id, week_start, sessions, minutes, data_gb' },
  { name: 'billing', label: 'Invoices', columns: 'customer_id, invoice_date, amount, discount_pct, paid_late, days_late' },
  { name: 'tickets', label: 'Support tickets', columns: 'customer_id, created_at, category, text, resolution_hours, csat' },
] as const

interface DatasetRow { id: number; source: string; created_at: string; summary: Record<string, number | string>; warnings: string[] }

export default function Data() {
  const { user } = useAuth()
  const isOwner = user?.role === 'owner'
  const queryClient = useQueryClient()
  const status = useDataStatus()
  const history = useQuery({ queryKey: ['datasets'], queryFn: () => api<DatasetRow[]>('/api/data/datasets') })
  const [files, setFiles] = useState<Record<string, File | null>>({})
  const [train, setTrain] = useState(true)
  const [profile, setProfile] = useState('quick')
  const [demoSize, setDemoSize] = useState(10000)

  const refresh = () => queryClient.invalidateQueries()
  const upload = useMutation({
    mutationFn: () => {
      const body = form({ train, profile })
      for (const t of TABLES) body.append(t.name, files[t.name] as File)
      return api<{ summary: Record<string, number>; warnings: string[]; job: Job | null }>('/api/data/upload', { body })
    },
    onSuccess: () => { setFiles({}); void refresh() },
  })
  const demo = useMutation({
    mutationFn: () => api<Job>('/api/data/demo', { body: form({ customers: demoSize, profile }) }),
    onSuccess: refresh,
  })

  const busy = Boolean(status.data?.active_job)
  const ready = TABLES.every((t) => files[t.name])
  const ds = status.data?.dataset

  function submit(e: FormEvent) {
    e.preventDefault()
    upload.mutate()
  }

  return (
    <>
      <PageHeader title="Data" subtitle="Load your customer data. A new dataset replaces the current one; models are retrained on it." />
      {!isOwner && <div className="mb-4"><Notice>Only organization owners can load data.</Notice></div>}
      {!status.data?.active_job && status.data?.last_job?.status === 'failed' && !upload.data && (
        <div className="mb-4"><FailedJobNotice job={status.data.last_job} /></div>
      )}
      {status.data?.active_job && (
        <div className="mb-4"><Notice>
          <span className="inline-flex items-center gap-2"><JobBadge status={status.data.active_job.status} /> {status.data.active_job.message}</span>
        </Notice></div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Current dataset">
          {status.isPending ? <Spinner /> : !ds ? <p className="text-sm text-ink-2">No data loaded yet.</p> : (
            <dl className="space-y-2 text-sm">
              {[
                ['Source', ds.source === 'demo' ? 'Demo data' : 'Uploaded CSVs'],
                ['Loaded', fmt.date(ds.created_at)],
                ['Customers', fmt.int(Number(ds.summary.customers))],
                ['Usage rows', fmt.int(Number(ds.summary.usage_rows))],
                ['Invoices', fmt.int(Number(ds.summary.invoices))],
                ['Tickets', fmt.int(Number(ds.summary.tickets))],
                ['History', `${ds.summary.n_weeks} weeks`],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4"><dt className="text-ink-2">{k}</dt><dd className="tabular font-medium">{v}</dd></div>
              ))}
            </dl>
          )}
          <div className="mt-5 border-t border-hairline pt-4">
            <div className="text-xs font-semibold text-ink-2">Try it with demo data</div>
            <div className="mt-2 flex gap-2">
              <Select aria-label="Demo size" value={demoSize} onChange={(e) => setDemoSize(Number(e.target.value))}>
                <option value={2000}>2,000 customers</option>
                <option value={10000}>10,000 customers</option>
                <option value={25000}>25,000 customers</option>
              </Select>
              <Button variant="secondary" onClick={() => demo.mutate()} loading={demo.isPending} disabled={!isOwner || busy}>Load</Button>
            </div>
            {demo.error && <div className="mt-3"><ErrorBox error={demo.error} /></div>}
          </div>
        </Card>

        <Card title="Upload your data" className="lg:col-span-2">
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              {TABLES.map((t) => (
                <Field key={t.name} label={`${t.label} (${t.name}.csv)`} hint={<span className="line-clamp-2" title={t.columns}>{t.columns}</span>}>
                  <Input type="file" accept=".csv,text/csv" required disabled={!isOwner}
                    onChange={(e) => setFiles((f) => ({ ...f, [t.name]: e.target.files?.[0] ?? null }))} />
                </Field>
              ))}
            </div>
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={train} onChange={(e) => setTrain(e.target.checked)} className="size-4 accent-[var(--accent)]" />
                Train a model after upload
              </label>
              <Field label="Training preset">
                <Select value={profile} onChange={(e) => setProfile(e.target.value)} className="w-40">
                  <option value="quick">Quick</option><option value="standard">Standard</option><option value="thorough">Thorough</option>
                </Select>
              </Field>
              <Button type="submit" loading={upload.isPending} disabled={!isOwner || !ready || busy}>
                <Upload className="size-4" aria-hidden /> Upload and validate
              </Button>
            </div>
            {upload.error && <ErrorBox error={upload.error} />}
            {upload.data && (
              <Notice tone={upload.data.warnings.length ? 'warning' : 'info'}>
                Uploaded {fmt.int(upload.data.summary.customers)} customers over {upload.data.summary.n_weeks} weeks.
                {upload.data.job ? ' Training has started; the dashboard fills in when it finishes.' : ''}
                {upload.data.warnings.length > 0 && (
                  <ul className="mt-1.5 list-disc space-y-1 pl-5">{upload.data.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
                )}
              </Notice>
            )}
            {upload.data?.job && status.data?.last_job?.id === upload.data.job.id && status.data.last_job.status === 'failed' && (
              <FailedJobNotice job={status.data.last_job} />
            )}
          </form>
          <div className="mt-5 border-t border-hairline pt-4">
            <div className="text-xs font-semibold text-ink-2">Templates (40 sample customers in the exact upload format)</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {TABLES.map((t) => (
                <Button key={t.name} variant="ghost" onClick={() => download(`/api/data/template/${t.name}`, `${t.name}.csv`)}>
                  <Download className="size-4" aria-hidden /> {t.name}.csv
                </Button>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted">
              Dates can be in any common format. At least 52 weeks of history are needed. Booleans accept true/false, yes/no or 1/0.
              Leave churn_date empty for active customers.
            </p>
          </div>
        </Card>
      </div>

      <Card title="Dataset history" className="mt-4">
        {history.isPending ? <Spinner /> : history.data!.length === 0 ? <p className="text-sm text-ink-2">Nothing loaded yet.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead><tr><Th>Loaded</Th><Th>Source</Th><Th align="right">Customers</Th><Th align="right">Weeks</Th><Th>Warnings</Th></tr></thead>
              <tbody>
                {history.data!.map((d) => (
                  <tr key={d.id}>
                    <Td>{fmt.date(d.created_at)}</Td>
                    <Td>{d.source === 'demo' ? 'Demo' : 'Upload'}</Td>
                    <Td align="right">{fmt.int(Number(d.summary.customers))}</Td>
                    <Td align="right">{d.summary.n_weeks}</Td>
                    <Td className="text-xs text-ink-2">{d.warnings.length ? d.warnings.join('; ') : '–'}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
