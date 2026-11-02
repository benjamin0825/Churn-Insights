import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, TrendingDown, TrendingUp } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartTooltip } from '../components/charts'
import { AXIS, SERIES } from '../lib/tokens'
import { Card, ErrorBox, PageHeader, RiskBadge, Spinner, Stat, Td, Th } from '../components/ui'
import { api } from '../lib/api'
import { customerLabel, fmt, humanize, titleCase } from '../lib/format'
import type { CustomerDetail as Detail } from '../lib/types'

function formatValue(value: number | string | null): string {
  if (value == null) return '–'
  if (typeof value === 'string') return value.length > 60 ? `${value.slice(0, 57)}…` : titleCase(value)
  return Number.isInteger(value) ? fmt.int(value) : fmt.num(value, 2)
}

export default function CustomerDetail() {
  const { id } = useParams()
  const query = useQuery({ queryKey: ['customer', id], queryFn: () => api<Detail>(`/api/customers/${id}`) })
  if (query.isPending) return <Spinner />
  if (query.error) return <ErrorBox error={query.error} />
  const c = query.data
  const maxImpact = Math.max(...c.reasons.map((r) => Math.abs(r.impact)), 0.01)

  return (
    <>
      <Link to="/app/customers" className="mb-4 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Customers
      </Link>
      <PageHeader
        title={customerLabel(c)}
        subtitle={<>{titleCase(String(c.profile.plan))} plan · {titleCase(String(c.profile.contract_type))} · {titleCase(String(c.profile.region))} · customer since {String(c.profile.signup_date)}</>}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Churn probability (8 weeks)" value={fmt.pct(c.score.churn_probability)} note={<RiskBadge tier={c.score.risk_tier} />} emphasis />
        <Stat label="Revenue at risk" value={fmt.money(c.score.expected_revenue_at_risk)} note="probability × customer value" />
        <Stat label="Monthly charge" value={fmt.cents(Number(c.profile.current_charge))} note={`tenure ${fmt.weeks(Number(c.profile.tenure_weeks))}`} />
        <Stat label="Retention offer" value={c.score.target_for_retention ? 'Recommended' : 'Not needed'}
          note={c.score.target_for_retention ? 'expected to pay off' : 'below the profit threshold'} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card title="Why this score" className="lg:col-span-3">
          <ul className="space-y-3">
            {c.reasons.map((r) => {
              const up = r.impact > 0
              return (
                <li key={r.feature}>
                  <div className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="flex items-center gap-2">
                      {up ? <TrendingUp className="size-4 text-critical-ink" aria-hidden /> : <TrendingDown className="size-4 text-good-ink" aria-hidden />}
                      <span className="font-medium">{titleCase(r.description)}</span>
                      <span className="text-xs text-muted">{formatValue(r.value)}</span>
                    </span>
                    <span className={clsx('text-xs font-medium', up ? 'text-critical-ink' : 'text-good-ink')}>{r.direction}</span>
                  </div>
                  <div className="mt-1.5 h-1.5 rounded-full bg-surface-2">
                    <div className="h-1.5 rounded-full" style={{ width: `${(Math.abs(r.impact) / maxImpact) * 100}%`,
                      background: up ? 'var(--critical)' : 'var(--good)' }} />
                  </div>
                </li>
              )
            })}
          </ul>
          <p className="mt-4 text-xs text-muted">Contributions from the model's SHAP explanation (log-odds). Longer bars matter more.</p>
        </Card>

        <Card title="Key signals" className="lg:col-span-2">
          <div className="space-y-4">
            {c.features.map((group) => (
              <div key={group.group}>
                <div className="mb-1 text-xs font-semibold text-ink-2">{group.group}</div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  {group.items.map((item) => (
                    <div key={item.name} className="contents">
                      <dt className="truncate text-ink-2" title={humanize(item.name)}>{humanize(item.name)}</dt>
                      <dd className="tabular text-right">{formatValue(item.value)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="Weekly usage (last 52 weeks)" className="mt-4">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={c.history.usage} margin={{ left: 0, right: 16, top: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="date" minTickGap={40} {...AXIS} />
            <YAxis width={40} {...AXIS} />
            <Tooltip content={<ChartTooltip format={(v) => fmt.int(v)} title={(l) => `Week of ${l}`} />} />
            <Line dataKey="sessions" name="Sessions" stroke={SERIES[0]} strokeWidth={2} dot={false}
              activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }} />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="Recent support tickets">
          {c.history.tickets.length === 0 ? <p className="text-sm text-ink-2">No tickets.</p> : (
            <ul className="divide-y divide-[var(--hairline)]">
              {c.history.tickets.map((t, i) => (
                <li key={i} className="py-2.5 text-sm">
                  <div className="flex justify-between gap-3">
                    <span className="font-medium">{titleCase(t.category)}</span>
                    <span className="text-xs text-muted">{t.date} · CSAT {t.csat}/5 · {fmt.num(t.resolution_hours, 0)} h</span>
                  </div>
                  <p className="mt-0.5 text-ink-2">“{t.text}”</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Recent invoices">
          <table className="w-full border-collapse">
            <thead><tr><Th>Date</Th><Th align="right">Amount</Th><Th align="right">Discount</Th><Th>Payment</Th></tr></thead>
            <tbody>
              {[...c.history.billing].reverse().map((b) => (
                <tr key={b.week}>
                  <Td>{b.date}</Td>
                  <Td align="right">{fmt.cents(b.amount)}</Td>
                  <Td align="right">{b.discount_pct ? fmt.pct(b.discount_pct, 0) : '–'}</Td>
                  <Td>{b.paid_late ? <span className="text-warning-ink">{b.days_late} days late</span> : <span className="text-ink-2">On time</span>}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  )
}
