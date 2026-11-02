import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, Download, ExternalLink, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Button, Card, ErrorBox, Field, Input, Notice, Select, Spinner, Td, Th } from '../../components/ui'
import { api, download } from '../../lib/api'
import {
  APPLICATION_STATUS, EMPLOYMENT, WORKPLACE, type AdminPosting, type Application, type ApplicationStatus, type PostingFields,
} from '../../lib/careers'
import { fmt, timeAgo } from '../../lib/format'
import { PostingStatusPill } from './Hiring'
import { AdminHeader, Dialog, Pill } from './shared'

const EMPTY: PostingFields = {
  title: '', department: 'Engineering', location: 'Remote', workplace: 'remote', employment_type: 'full_time',
  salary_range: '', summary: '', description: '', responsibilities: [], requirements: [], nice_to_have: [], benefits: [],
  status: 'draft',
}
const LIST_FIELDS = [
  ['responsibilities', "What you'll do"],
  ['requirements', "What we're looking for"],
  ['nice_to_have', 'Nice to have'],
  ['benefits', 'What we offer'],
] as const
type ListField = (typeof LIST_FIELDS)[number][0]

const textarea = 'w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none'
const lines = (text: string) => text.split('\n').map((l) => l.trim()).filter(Boolean)

function PostingEditor({ initial, id }: { initial: PostingFields; id: number | null }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [fields, setFields] = useState(initial)
  const [lists, setLists] = useState(() =>
    Object.fromEntries(LIST_FIELDS.map(([key]) => [key, initial[key].join('\n')])) as Record<ListField, string>)
  const set = <K extends keyof PostingFields>(key: K, value: PostingFields[K]) => setFields({ ...fields, [key]: value })

  const save = useMutation({
    mutationFn: (status: PostingFields['status']) => {
      const body = { ...fields, status, ...Object.fromEntries(LIST_FIELDS.map(([key]) => [key, lines(lists[key])])) }
      return id == null
        ? api<AdminPosting>('/api/admin/careers/postings', { body })
        : api<AdminPosting>(`/api/admin/careers/postings/${id}`, { method: 'PUT', body })
    },
    onSuccess: (posting) => {
      setFields((f) => ({ ...f, status: posting.status }))
      queryClient.setQueryData(['admin', 'posting', String(posting.id)], posting)
      void queryClient.invalidateQueries({ queryKey: ['admin', 'postings'] })
      void queryClient.invalidateQueries({ queryKey: ['careers'] })
      if (id == null) navigate(`/admin/hiring/${posting.id}?tab=posting`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(fields.status)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Card title="Basics">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Job title"><Input required minLength={2} maxLength={120} value={fields.title} onChange={(e) => set('title', e.target.value)} placeholder="e.g. AI Engineer" /></Field>
          <Field label="Department"><Input maxLength={80} value={fields.department} onChange={(e) => set('department', e.target.value)} /></Field>
          <Field label="Location"><Input maxLength={120} value={fields.location} onChange={(e) => set('location', e.target.value)} placeholder="e.g. Remote (Europe) or Berlin" /></Field>
          <Field label="Salary range" hint="Optional, shown as written"><Input maxLength={120} value={fields.salary_range} onChange={(e) => set('salary_range', e.target.value)} placeholder="e.g. $120k–$150k + equity" /></Field>
          <Field label="Workplace">
            <Select value={fields.workplace} onChange={(e) => set('workplace', e.target.value as PostingFields['workplace'])}>
              {Object.entries(WORKPLACE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </Field>
          <Field label="Employment type">
            <Select value={fields.employment_type} onChange={(e) => set('employment_type', e.target.value as PostingFields['employment_type'])}>
              {Object.entries(EMPLOYMENT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
          </Field>
        </div>
      </Card>
      <Card title="Description">
        <div className="space-y-4">
          <Field label="One-line summary" hint="Shown in the list of positions">
            <Input maxLength={400} value={fields.summary} onChange={(e) => set('summary', e.target.value)} />
          </Field>
          <Field label="About the role" hint="Leave a blank line between paragraphs">
            <textarea className={textarea} rows={6} maxLength={20000} value={fields.description} onChange={(e) => set('description', e.target.value)} />
          </Field>
          <div className="grid gap-4 lg:grid-cols-2">
            {LIST_FIELDS.map(([key, label]) => (
              <Field key={key} label={label} hint="One item per line">
                <textarea className={textarea} rows={6} value={lists[key]} onChange={(e) => setLists({ ...lists, [key]: e.target.value })} />
              </Field>
            ))}
          </div>
        </div>
      </Card>
      {save.error && <ErrorBox error={save.error} />}
      {save.isSuccess && <Notice>Saved{fields.status === 'open' ? ' and live on the Jobs page' : ''}.</Notice>}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <span className="mr-auto text-sm text-ink-2">Status: <PostingStatusPill status={fields.status} /></span>
        <Button type="submit" variant="secondary" loading={save.isPending && save.variables === fields.status}>Save</Button>
        {fields.status !== 'open'
          ? <Button type="button" loading={save.isPending && save.variables === 'open'} onClick={() => save.mutate('open')}>{fields.status === 'draft' ? 'Publish' : 'Reopen'}</Button>
          : <Button type="button" variant="danger" loading={save.isPending && save.variables === 'closed'} onClick={() => save.mutate('closed')}>Close posting</Button>}
      </div>
    </form>
  )
}

function ApplicationDialog({ app, onClose }: { app: Application; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [notes, setNotes] = useState(app.notes)
  const [status, setStatus] = useState(app.status)
  const update = useMutation({
    mutationFn: (body: { status?: ApplicationStatus; notes?: string }) =>
      api<Application>(`/api/admin/careers/applications/${app.id}`, { method: 'PATCH', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  })
  const cv = useMutation({ mutationFn: () => download(`/api/admin/careers/applications/${app.id}/resume`, app.resume_filename || 'cv') })
  const link = (url: string, label: string) => url && (
    <a href={url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-accent hover:underline">
      {label} <ExternalLink className="size-3" aria-hidden />
    </a>
  )
  return (
    <div className="space-y-4 text-sm">
      <div className="text-ink-2">
        <div><a href={`mailto:${app.email}`} className="text-accent hover:underline">{app.email}</a>{app.phone && ` · ${app.phone}`}</div>
        {app.location && <div>{app.location}</div>}
        <div className="mt-1 flex gap-4">{link(app.linkedin_url, 'LinkedIn')}{link(app.portfolio_url, 'GitHub / portfolio')}</div>
        <div className="mt-1 text-xs text-muted">Applied {fmt.date(app.created_at)} for {app.posting_title}</div>
      </div>
      {app.has_resume && (
        <Button variant="secondary" loading={cv.isPending} onClick={() => cv.mutate()}>
          <Download className="size-4" aria-hidden /> Download CV ({app.resume_filename})
        </Button>
      )}
      {cv.error && <ErrorBox error={cv.error} />}
      {app.cover_letter && <p className="max-h-48 overflow-y-auto rounded-lg bg-surface-2 p-3 whitespace-pre-line text-ink">{app.cover_letter}</p>}
      <Field label="Status">
        <Select value={status} onChange={(e) => {
          const next = e.target.value as ApplicationStatus
          setStatus(next)
          update.mutate({ status: next })
        }}>
          {Object.entries(APPLICATION_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      </Field>
      <Field label="Private notes">
        <textarea className={textarea} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Only admins see these" />
      </Field>
      {update.error && <ErrorBox error={update.error} />}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>Close</Button>
        <Button loading={update.isPending && update.variables?.notes !== undefined} disabled={notes === app.notes}
          onClick={() => update.mutate({ notes })}>Save notes</Button>
      </div>
    </div>
  )
}

const STATUS_TONE: Record<ApplicationStatus, 'accent' | 'neutral' | 'good' | 'bad' | 'warn'> = {
  new: 'accent', reviewing: 'neutral', interview: 'warn', offer: 'good', hired: 'good', rejected: 'bad',
}

function Applications({ postingId }: { postingId: number }) {
  const [open, setOpen] = useState<Application | null>(null)
  const [filter, setFilter] = useState('')
  const query = useQuery({
    queryKey: ['admin', 'applications', postingId, filter],
    queryFn: () => api<Application[]>(`/api/admin/careers/applications?posting_id=${postingId}${filter ? `&status=${filter}` : ''}`),
  })
  return (
    <>
      <div className="mb-4 flex items-center gap-3">
        <Select value={filter} onChange={(e) => setFilter(e.target.value)} className="w-44" aria-label="Filter by status">
          <option value="">All statuses</option>
          {Object.entries(APPLICATION_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
      </div>
      {query.error && <ErrorBox error={query.error} />}
      {query.isPending ? <Spinner /> : query.data && (
        query.data.length === 0 ? <p className="rounded-lg bg-surface px-5 py-10 text-center text-sm text-ink-2 shadow-card">No applications{filter ? ' with this status' : ' yet'}.</p> : (
          <div className="overflow-x-auto rounded-lg bg-surface shadow-card">
            <table className="w-full">
              <thead><tr><Th>Applicant</Th><Th>Status</Th><Th>Links</Th><Th>CV</Th><Th>Applied</Th></tr></thead>
              <tbody>
                {query.data.map((a) => (
                  <tr key={a.id} tabIndex={0} className="cursor-pointer hover:bg-surface-2" onClick={() => setOpen(a)} onKeyDown={(e) => e.key === 'Enter' && setOpen(a)}>
                    <Td><div className="font-medium text-ink">{a.name}</div><div className="text-xs text-ink-2">{a.email}</div></Td>
                    <Td><Pill tone={STATUS_TONE[a.status]}>{APPLICATION_STATUS[a.status]}</Pill></Td>
                    <Td className="text-ink-2">{[a.linkedin_url && 'LinkedIn', a.portfolio_url && 'Portfolio'].filter(Boolean).join(' · ') || '–'}</Td>
                    <Td className="text-ink-2">{a.has_resume ? 'Attached' : '–'}</Td>
                    <Td className="text-ink-2">{timeAgo(a.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
      <Dialog open={open != null} title={open?.name ?? ''} onClose={() => setOpen(null)} wide>
        {open && <ApplicationDialog key={open.id} app={open} onClose={() => setOpen(null)} />}
      </Dialog>
    </>
  )
}

/** Keyed by id so moving from "new" to the saved posting starts fresh. */
export default function HiringPostingRoute() {
  const { id = 'new' } = useParams()
  return <HiringPosting key={id} id={id} />
}

function HiringPosting({ id }: { id: string }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isNew = id === 'new'
  const [tab, setTab] = useState<'applications' | 'posting'>(() =>
    new URLSearchParams(window.location.search).get('tab') === 'posting' ? 'posting' : 'applications')
  const [deleting, setDeleting] = useState(false)
  const query = useQuery({
    queryKey: ['admin', 'posting', id],
    queryFn: () => api<AdminPosting>(`/api/admin/careers/postings/${id}`),
    enabled: !isNew,
  })
  const remove = useMutation({
    mutationFn: () => api<void>(`/api/admin/careers/postings/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      navigate('/admin/hiring', { replace: true })
      void queryClient.invalidateQueries({ queryKey: ['admin', 'postings'] })
      queryClient.removeQueries({ queryKey: ['admin', 'posting', id] })
    },
  })

  const back = (
    <Link to="/admin/hiring" className="mb-4 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
      <ArrowLeft className="size-4" aria-hidden /> Hiring
    </Link>
  )
  if (isNew) {
    return <>{back}<AdminHeader title="New posting" subtitle="Saved as a draft until you publish it" /><PostingEditor initial={EMPTY} id={null} /></>
  }
  if (query.isPending) return <Spinner />
  if (query.error) return <ErrorBox error={query.error} />
  const p = query.data

  return (
    <>
      {back}
      <AdminHeader title={p.title} subtitle={<>{p.department} · {p.location} <PostingStatusPill status={p.status} /></>}
        actions={
          <>
            {p.status !== 'draft' && (
              <Link to={`/jobs/${p.slug}`} target="_blank" className="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium text-ink-2 hover:bg-surface-2 hover:text-ink">
                View on site <ExternalLink className="size-3.5" aria-hidden />
              </Link>
            )}
            <Button variant="danger" onClick={() => setDeleting(true)}><Trash2 className="size-4" aria-hidden /> Delete</Button>
          </>
        } />
      <div className="mb-5 flex gap-1 border-b border-hairline" role="tablist">
        {([['applications', `Applications (${p.applications})`], ['posting', 'Edit posting']] as const).map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
            className={clsx('-mb-px border-b-2 px-4 py-2.5 text-sm font-medium', tab === key ? 'border-accent text-ink' : 'border-transparent text-ink-2 hover:text-ink')}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'applications' ? <Applications postingId={p.id} /> : <PostingEditor key={p.id} initial={p} id={p.id} />}

      <Dialog open={deleting} title="Delete this posting?" onClose={() => setDeleting(false)}>
        <p className="text-sm text-ink-2">
          This removes <b className="text-ink">{p.title}</b> and its {p.applications} application(s), including uploaded CVs.
          To stop new applications but keep the history, close the posting instead.
        </p>
        {remove.error && <div className="mt-3"><ErrorBox error={remove.error} /></div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setDeleting(false)}>Cancel</Button>
          <Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate()}>Delete</Button>
        </div>
      </Dialog>
    </>
  )
}
