import { keepPreviousData, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { CalendarDays, ChevronRight } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import MetricCard from '../components/MetricCard'
import { ErrorBox, FailedJobNotice, PageHeader, Select, Spinner } from '../components/ui'
import { ApiError, api } from '../lib/api'
import { fmt, titleCase } from '../lib/format'
import { useDataStatus } from '../lib/hooks'
import type { ActivityEvent, Overview as OverviewData } from '../lib/types'
import Onboarding from './Onboarding'

const PERIODS = [
  ['12w', 'Last 12 weeks'],
  ['26w', 'Last 26 weeks'],
  ['52w', 'Last 52 weeks'],
  ['all', 'All time'],
] as const

const longDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg bg-surface shadow-card">
      <header className="flex min-h-[62px] items-center justify-between gap-3 border-b border-hairline px-5">
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        {action}
      </header>
      {children}
    </section>
  )
}

function Row({ count, label, amount, tone, to }: {
  count?: number | string
  label: string
  amount?: string
  tone?: 'good' | 'bad' | 'neutral'
  to?: string
}) {
  const navigate = useNavigate()
  const body = (
    <>
      <span className="flex min-w-0 items-baseline gap-2.5">
        {count != null && <span className={clsx('tabular font-semibold', count === 0 ? 'text-muted' : 'text-accent')}>{count}</span>}
        <span className={clsx('truncate', count === 0 ? 'text-muted' : 'text-ink-2')}>{label}</span>
      </span>
      {amount && (
        <span className={clsx('tabular shrink-0 font-semibold',
          tone === 'good' ? 'text-good-ink' : tone === 'bad' ? 'text-critical-ink' : 'text-muted')}>{amount}</span>
      )}
    </>
  )
  const cls = 'flex items-center justify-between gap-3 border-b border-hairline px-5 py-3 text-[15px] last:border-b-0'
  return to ? (
    <button type="button" onClick={() => navigate(to)} className={clsx(cls, 'w-full text-left hover:bg-surface-2')}>{body}</button>
  ) : <div className={cls}>{body}</div>
}

const signedMoney = (v: number) => (Math.abs(v) < 0.005 ? '—' : `${v > 0 ? '+' : '−'} ${fmt.cents(Math.abs(v))}`)

function ActivityItem({ e }: { e: ActivityEvent }) {
  const who = e.name ?? `#${e.customer_id}`
  const when = e.weeks_ago === 0 ? 'this week' : e.weeks_ago === 1 ? 'last week' : `${e.weeks_ago} weeks ago`
  const text = {
    cancelled: e.amount != null
      ? <><span className="font-semibold text-critical-ink">−{fmt.cents(Math.abs(e.amount))}/mo</span> cancelled by <b>{who}</b></>
      : <><b>{who}</b> cancelled their {titleCase(e.detail)}</>,
    subscribed: e.amount != null
      ? <><span className="font-semibold text-good-ink">+{fmt.cents(e.amount)}/mo</span> new {titleCase(e.detail)} · <b>{who}</b></>
      : <><b>{who}</b> started a {titleCase(e.detail)} <span className="text-muted">(first invoice pending)</span></>,
    cancel_request: <><b>{who}</b> asked about cancelling</>,
    paid_late: <><b>{who}</b> paid {fmt.cents(e.amount ?? 0)} {e.detail}</>,
  }[e.kind]
  const dot = { cancelled: 'bg-critical', subscribed: 'bg-good', cancel_request: 'bg-warning', paid_late: 'bg-warning' }[e.kind]
  return (
    <Link to={`/app/customers/${e.customer_id}`} className="flex items-center justify-between gap-3 border-b border-hairline px-5 py-3 text-sm last:border-b-0 hover:bg-surface-2">
      <span className="flex min-w-0 items-center gap-2 text-ink-2">
        <span className={clsx('size-2 shrink-0 rounded-full', dot)} aria-hidden />
        <span className="truncate">{text}</span>
      </span>
      <span className="shrink-0 text-xs text-muted">{when}</span>
    </Link>
  )
}

export default function Overview() {
  const [period, setPeriod] = useState<string>('26w')
  const status = useDataStatus()
  const lastJob = status.data?.active_job ? null : status.data?.last_job
  const query = useQuery({
    queryKey: ['overview', period],
    queryFn: () => api<OverviewData>(`/api/overview?period=${period}`),
    placeholderData: keepPreviousData,
    retry: false,
  })

  if (query.isPending) return <Spinner />
  if (query.error instanceof ApiError && query.error.status === 409) return <Onboarding />
  if (query.error) return <ErrorBox error={query.error} />
  const d = query.data
  const b = d.breakdown
  const f = d.forecast

  return (
    <>
      <PageHeader
        title="Overview"
        actions={<>
          <Select aria-label="Period" value={period} onChange={(e) => setPeriod(e.target.value)} className="w-44 border-0 shadow-card">
            {PERIODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
          <span className="inline-flex items-center gap-2 rounded-lg bg-surface px-3.5 py-2 text-sm text-ink shadow-card">
            <CalendarDays className="size-4 text-muted" aria-hidden />
            {longDate(d.period.start)} <span className="text-muted">–</span> {longDate(d.as_of)}
          </span>
        </>}
      />
      {lastJob?.status === 'failed' && <div className="mb-6"><FailedJobNotice job={lastJob} /></div>}

      {/* minmax(0,1fr): let single-column grids shrink below their content's natural width on phones */}
      <div className={clsx('grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-3', query.isFetching && 'opacity-70 transition-opacity')}>
        <div className="grid grid-cols-[minmax(0,1fr)] content-start gap-6 md:grid-cols-2 xl:col-span-2">
          {d.cards.map((card) => <MetricCard key={card.key} card={card} periodWeeks={d.period.weeks} />)}
        </div>

        <div className="flex flex-col gap-6">
          <Panel title="Churn forecast" action={<span className="text-xs text-muted">next 8 weeks{f ? ` · model v${f.model_version}` : ''}</span>}>
            {f ? (
              <>
                <div className="border-b border-hairline px-5 py-4">
                  <div className="text-sm text-ink-2">Revenue at risk</div>
                  <div className="mt-1 text-[26px] font-semibold tracking-tight text-ink tabular">{fmt.money(f.revenue_at_risk)}</div>
                  <div className="text-sm text-muted">≈ {fmt.int(f.expected_churners)} customers expected to leave</div>
                </div>
                <Row count={fmt.int(f.high_risk)} label="High-risk customers" to="/app/customers?tier=high" />
                <Row count={fmt.int(f.medium_risk)} label="Medium-risk customers" to="/app/customers?tier=medium" />
                <Row count={fmt.int(f.recommended_for_offer)} label="Worth a retention offer" to="/app/campaigns" />
                <Link to="/app/risk" className="flex items-center justify-between px-5 py-3 text-sm font-medium text-accent hover:bg-surface-2">
                  See what drives churn <ChevronRight className="size-4" aria-hidden />
                </Link>
              </>
            ) : <p className="px-5 py-4 text-sm text-ink-2">Train a model to forecast churn. <Link to="/app/data" className="font-medium text-accent">Go to Data</Link></p>}
          </Panel>

          <Panel title="Breakdown" action={<span className="text-xs text-muted">MRR · last {b.weeks} weeks</span>}>
            <Row count={b.new_customers} label="New customers" amount={signedMoney(b.new_mrr)} tone="good" />
            <Row count={b.expansions} label="Expansions" amount={signedMoney(b.expansion_mrr)} tone="good" />
            <Row count={b.contractions} label="Contractions" amount={signedMoney(b.contraction_mrr)} tone="bad" />
            <Row count={b.cancellations} label="Cancellations" amount={signedMoney(b.churned_mrr)} tone="bad" />
            <div className="flex items-center justify-between gap-3 bg-surface-2/60 px-5 py-3.5 text-[15px]">
              <span className="text-ink-2">Net MRR change</span>
              <span className={clsx('tabular font-semibold', b.net_mrr_change >= 0 ? 'text-good-ink' : 'text-critical-ink')}>
                {signedMoney(b.net_mrr_change)}
              </span>
            </div>
          </Panel>

          <Panel title="Recent activity">
            {d.activity.length === 0 ? <p className="px-5 py-4 text-sm text-ink-2">No recent events.</p>
              : d.activity.map((e, i) => <ActivityItem key={`${e.kind}-${e.customer_id}-${i}`} e={e} />)}
          </Panel>
        </div>
      </div>
    </>
  )
}
