import clsx from 'clsx'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import type { Job } from '../../lib/types'

// ------------------------------------------------------------------ types
export interface Page<T> { total: number; page: number; page_size: number; items: T[] }

export interface AdminOrg {
  id: number
  name: string
  plan: string
  status: 'active' | 'suspended'
  created_at: string
  users: number
  owner_email: string | null
  customers: number | null
  data_source: 'upload' | 'demo' | null
  model_version: number | null
  last_activity: string | null
}

export interface AdminUser {
  id: number
  name: string
  email: string
  role: 'owner' | 'analyst'
  is_admin: boolean
  is_active: boolean
  created_at: string
  organization_id: number
  organization_name: string
}

export interface AdminOrgDetail extends AdminOrg {
  users_list: AdminUser[]
  jobs: Job[]
  datasets: { id: number; source: string; created_at: string; summary: Record<string, number | string> }[]
  campaigns: number
  economics: { offer_cost: number; retention_success_rate: number; months_of_value: number }
}

export type AdminJob = Job & { organization_id: number; organization_name: string | null }

export interface Plan {
  key: string
  name: string
  monthly_price: number
  blurb: string
  limits: string[]
  features: string[]
  popular: boolean
  active: boolean
  sort_order: number
  organizations?: number
}

export interface AdminStats {
  organizations: number
  suspended: number
  users: number
  admins: number
  active_organizations_30d: number
  new_organizations_30d: number
  jobs: { queued: number; running: number; failed_7d: number; total: number }
  signups_by_week: { week_start: string; organizations: number }[]
  by_plan: { plan: string; name: string; organizations: number }[]
  recent_failures: AdminJob[]
}

// ------------------------------------------------------------- components
export function AdminHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

/** A small rounded label. Tone carries meaning, the text always says it too. */
export function Pill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'good' | 'bad' | 'accent' | 'warn' }) {
  return (
    <span className={clsx('inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap',
      tone === 'neutral' && 'bg-surface-2 text-ink-2',
      tone === 'good' && 'bg-good-soft text-good-ink',
      tone === 'bad' && 'bg-critical-soft text-critical-ink',
      tone === 'accent' && 'bg-accent-soft text-accent',
      tone === 'warn' && 'bg-surface-2 text-warning-ink')}>
      {children}
    </span>
  )
}

export function Pager({ page, total, pageSize, onPage }: { page: number; total: number; pageSize: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  return (
    <div className="flex items-center justify-between gap-3 px-5 py-3 text-sm text-ink-2">
      <span className="tabular">{from}–{Math.min(page * pageSize, total)} of {total}</span>
      <div className="flex items-center gap-1">
        <button type="button" onClick={() => onPage(page - 1)} disabled={page <= 1} aria-label="Previous page"
          className="grid size-8 place-items-center rounded-lg hover:bg-surface-2 disabled:opacity-40">
          <ChevronLeft className="size-4" />
        </button>
        <span className="tabular px-2">{page} / {pages}</span>
        <button type="button" onClick={() => onPage(page + 1)} disabled={page >= pages} aria-label="Next page"
          className="grid size-8 place-items-center rounded-lg hover:bg-surface-2 disabled:opacity-40">
          <ChevronRight className="size-4" />
        </button>
      </div>
    </div>
  )
}

/** Modal dialog on the native <dialog> element: focus trapping and Escape come for free. */
export function Dialog({ open, title, onClose, children, wide }: { open: boolean; title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])
  return (
    <dialog ref={ref} onClose={onClose} onCancel={onClose}
      className={clsx('m-auto w-[calc(100%-2rem)] rounded-xl bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/40', wide ? 'max-w-xl' : 'max-w-md')}>
      {open && (
        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <h2 className="text-lg font-semibold">{title}</h2>
            <button type="button" onClick={onClose} aria-label="Close" className="text-ink-2 hover:text-ink"><X className="size-5" /></button>
          </div>
          <div className="mt-4">{children}</div>
        </div>
      )}
    </dialog>
  )
}
