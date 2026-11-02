import { useQuery } from '@tanstack/react-query'
import { ExternalLink, Plus } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { ErrorBox, Spinner, Td, Th } from '../../components/ui'
import { api } from '../../lib/api'
import { EMPLOYMENT, WORKPLACE, type AdminPosting } from '../../lib/careers'
import { fmt, timeAgo } from '../../lib/format'
import { AdminHeader, Pill } from './shared'

export function PostingStatusPill({ status }: { status: AdminPosting['status'] }) {
  return status === 'open' ? <Pill tone="good">Open</Pill> : status === 'draft' ? <Pill tone="warn">Draft</Pill> : <Pill>Closed</Pill>
}

export default function Hiring() {
  const navigate = useNavigate()
  const query = useQuery({ queryKey: ['admin', 'postings'], queryFn: () => api<AdminPosting[]>('/api/admin/careers/postings') })

  return (
    <>
      <AdminHeader title="Hiring" subtitle="Job postings on the public Jobs page, and the applications they receive"
        actions={
          <>
            <Link to="/jobs" target="_blank" className="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium text-ink-2 hover:bg-surface-2 hover:text-ink">
              View Jobs page <ExternalLink className="size-3.5" aria-hidden />
            </Link>
            <Link to="/admin/hiring/new" className="inline-flex items-center gap-2 rounded-lg bg-accent px-3.5 py-2 text-sm font-medium text-accent-ink shadow-card hover:brightness-110">
              <Plus className="size-4" aria-hidden /> New posting
            </Link>
          </>
        } />
      {query.error && <ErrorBox error={query.error} />}
      {query.isPending ? <Spinner /> : query.data && (
        query.data.length === 0 ? (
          <div className="rounded-lg bg-surface px-6 py-14 text-center shadow-card">
            <p className="font-semibold text-ink">No postings yet</p>
            <p className="mt-1 text-sm text-ink-2">Create one, save it as a draft, and open it when it's ready to go on the Jobs page.</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg bg-surface shadow-card">
            <table className="w-full">
              <thead><tr><Th>Position</Th><Th>Status</Th><Th>Type</Th><Th align="right">Applications</Th><Th>Published</Th><Th>Updated</Th></tr></thead>
              <tbody>
                {query.data.map((p) => (
                  <tr key={p.id} tabIndex={0} className="cursor-pointer hover:bg-surface-2"
                    onClick={() => navigate(`/admin/hiring/${p.id}`)} onKeyDown={(e) => e.key === 'Enter' && navigate(`/admin/hiring/${p.id}`)}>
                    <Td><div className="font-medium text-ink">{p.title}</div><div className="text-xs text-ink-2">{p.department} · {p.location}</div></Td>
                    <Td><PostingStatusPill status={p.status} /></Td>
                    <Td className="text-ink-2">{EMPLOYMENT[p.employment_type]} · {WORKPLACE[p.workplace]}</Td>
                    <Td align="right">
                      {fmt.int(p.applications)}
                      {p.new_applications > 0 && <span className="ml-2"><Pill tone="accent">{p.new_applications} new</Pill></span>}
                    </Td>
                    <Td className="text-ink-2">{p.published_at ? fmt.date(p.published_at) : '–'}</Td>
                    <Td className="text-ink-2">{timeAgo(p.updated_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </>
  )
}
