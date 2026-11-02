import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, CircleAlert, Info, Loader2, ShieldAlert, XCircle } from 'lucide-react'
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { JobStatus, RiskTier } from '../lib/types'

export function Card({ title, action, children, className }: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={clsx('rounded-lg bg-surface shadow-card', className)}>
      {(title || action) && (
        <header className="flex min-h-14 items-center justify-between gap-3 border-b border-hairline px-5 py-3">
          <h2 className="text-[17px] font-semibold text-ink">{title}</h2>
          {action}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  const { user } = useAuth()
  const initial = user?.organization.name.trim()[0]?.toUpperCase() ?? '·'
  return (
    <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-4">
        <span aria-hidden className="grid size-12 shrink-0 place-items-center rounded-full bg-surface text-lg font-semibold text-ink shadow-card">
          {initial}
        </span>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight text-ink">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

export function Button({ variant = 'primary', loading, className, children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variant === 'primary' && 'bg-accent text-accent-ink shadow-card hover:brightness-110',
        variant === 'secondary' && 'bg-surface text-ink shadow-card hover:bg-surface-2',
        variant === 'ghost' && 'text-ink-2 hover:bg-surface-2 hover:text-ink',
        variant === 'danger' && 'border border-hairline bg-surface text-critical-ink hover:bg-surface-2',
        className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

export function Stat({ label, value, note, emphasis }: { label: string; value: ReactNode; note?: ReactNode; emphasis?: boolean }) {
  return (
    <div className="rounded-lg bg-surface px-5 py-4 shadow-card">
      <div className="text-sm text-ink-2">{label}</div>
      <div className={clsx('mt-1 font-semibold tracking-tight text-ink', emphasis ? 'text-3xl' : 'text-2xl')}>{value}</div>
      {note && <div className="mt-1 text-xs text-muted">{note}</div>}
    </div>
  )
}

const TIER = {
  high: { label: 'High risk', icon: ShieldAlert, cls: 'text-critical-ink', dot: 'bg-critical' },
  medium: { label: 'Medium risk', icon: AlertTriangle, cls: 'text-warning-ink', dot: 'bg-warning' },
  low: { label: 'Low risk', icon: CheckCircle2, cls: 'text-good-ink', dot: 'bg-good' },
} as const

/** Status color always comes with an icon and a label, never color alone. */
export function RiskBadge({ tier, compact }: { tier: RiskTier; compact?: boolean }) {
  const t = TIER[tier]
  const Icon = t.icon
  return (
    <span className={clsx('inline-flex items-center gap-1.5 text-xs font-medium', t.cls)}>
      <Icon className="size-3.5" aria-hidden />
      {compact ? tier[0].toUpperCase() + tier.slice(1) : t.label}
    </span>
  )
}

const DRIFT = {
  stable: { label: 'Stable', icon: CheckCircle2, cls: 'text-good-ink' },
  warning: { label: 'Warning', icon: AlertTriangle, cls: 'text-warning-ink' },
  alert: { label: 'Alert', icon: CircleAlert, cls: 'text-critical-ink' },
} as const

export function DriftBadge({ status }: { status: 'stable' | 'warning' | 'alert' }) {
  const d = DRIFT[status] ?? DRIFT.warning
  const Icon = d.icon
  return (
    <span className={clsx('inline-flex items-center gap-1.5 text-xs font-medium', d.cls)}>
      <Icon className="size-3.5" aria-hidden />
      {d.label}
    </span>
  )
}

export function JobBadge({ status }: { status: JobStatus }) {
  const map = {
    queued: { label: 'Queued', icon: Loader2, cls: 'text-ink-2', spin: false },
    running: { label: 'Running', icon: Loader2, cls: 'text-accent', spin: true },
    succeeded: { label: 'Succeeded', icon: CheckCircle2, cls: 'text-good-ink', spin: false },
    failed: { label: 'Failed', icon: XCircle, cls: 'text-critical-ink', spin: false },
  }[status]
  const Icon = map.icon
  return (
    <span className={clsx('inline-flex items-center gap-1.5 text-xs font-medium', map.cls)}>
      <Icon className={clsx('size-3.5', map.spin && 'animate-spin')} aria-hidden />
      {map.label}
    </span>
  )
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-ink-2" role="status">
      <Loader2 className="size-4 animate-spin" aria-hidden /> {label}
    </div>
  )
}

export function ErrorBox({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : 'Something went wrong'
  const details = error instanceof ApiError ? error.details : []
  return (
    <div className="rounded-lg border border-hairline bg-surface-2 px-4 py-3 text-sm" role="alert">
      <div className="flex items-center gap-2 font-medium text-critical-ink">
        <XCircle className="size-4" aria-hidden /> {message}
      </div>
      {details.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-6 text-ink-2">
          {details.map((d) => <li key={d}>{d}</li>)}
        </ul>
      )}
    </div>
  )
}

/** The readable part of a job error (the first paragraph; tracebacks follow a blank line). */
function jobErrorText(job: { error: string | null }): string {
  return (job.error ?? 'Something went wrong.').split(/\n\s*\n/)[0]
}

/** Explains a failed background job, so a failure is never silent. */
export function FailedJobNotice({ job }: { job: { kind: string; error: string | null } }) {
  const what = { demo: 'Loading the demo data', train: 'Training the model', score: 'Scoring customers', monitor: 'The drift check' }[job.kind] ?? 'The last job'
  return (
    <div className="flex gap-3 rounded-lg border border-hairline bg-critical-soft px-4 py-3 text-sm" role="alert">
      <XCircle className="mt-0.5 size-4 shrink-0 text-critical-ink" aria-hidden />
      <div>
        <div className="font-medium text-critical-ink">{what} didn't finish</div>
        <div className="mt-0.5 text-ink-2">{jobErrorText(job)}</div>
      </div>
    </div>
  )
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warning' }) {
  const Icon = tone === 'info' ? Info : AlertTriangle
  return (
    <div className="flex gap-2 rounded-lg border border-hairline bg-surface-2 px-4 py-3 text-sm text-ink-2">
      <Icon className={clsx('mt-0.5 size-4 shrink-0', tone === 'warning' ? 'text-warning-ink' : 'text-accent')} aria-hidden />
      <div>{children}</div>
    </div>
  )
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-lg bg-surface px-6 py-14 text-center shadow-card">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      {children && <p className="mt-2 max-w-md text-sm text-ink-2">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-ink-2">{label}</span>
      <div className="mt-1">{children}</div>
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  )
}

const inputCls = 'rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none'
/** Full width unless the caller sets an explicit width class. */
const width = (className?: string) => (/(^|\s)w-/.test(className ?? '') ? '' : 'w-full')

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx(inputCls, width(props.className), props.className)} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={clsx(inputCls, width(props.className), props.className)} />
}

export function Th({ children, align = 'left' }: { children?: ReactNode; align?: 'left' | 'right' }) {
  return (
    <th className={clsx('whitespace-nowrap border-b border-hairline px-3 py-2 text-xs font-medium text-ink-2',
      align === 'right' ? 'text-right' : 'text-left')}>
      {children}
    </th>
  )
}

export function Td({ children, align = 'left', className }: { children?: ReactNode; align?: 'left' | 'right'; className?: string }) {
  return (
    <td className={clsx('whitespace-nowrap border-b border-hairline px-3 py-2.5 text-sm',
      align === 'right' && 'tabular text-right', className)}>
      {children}
    </td>
  )
}
