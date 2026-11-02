import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { ChartTooltip } from '../components/charts'
import { Card, DriftBadge, ErrorBox, PageHeader, RiskBadge, Spinner, Stat } from '../components/ui'
import { AXIS, SERIES, TIER_COLOR } from '../lib/tokens'
import { ApiError, api } from '../lib/api'
import { fmt, humanize, titleCase } from '../lib/format'
import type { Dashboard as DashboardData, Segment } from '../lib/types'
import Onboarding from './Onboarding'

function SegmentChart({ data, title }: { data: Segment[]; title: string }) {
  return (
    <Card title={title}>
      <ResponsiveContainer width="100%" height={Math.max(160, data.length * 44)}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 48 }} barCategoryGap={8}>
          <CartesianGrid horizontal={false} />
          <XAxis type="number" tickFormatter={fmt.pctTick} {...AXIS} />
          <YAxis type="category" dataKey="segment" width={110} tickFormatter={titleCase} {...AXIS} />
          <Tooltip cursor={{ fill: 'var(--surface-2)' }} content={
            <ChartTooltip format={(v) => fmt.pct(v)} title={(l) => titleCase(String(l))} />} />
          <Bar dataKey="avg_probability" name="Avg churn probability" fill={SERIES[0]} radius={[0, 4, 4, 0]}
            label={{ position: 'right', formatter: (v: unknown) => fmt.pct(Number(v), 1), fill: 'var(--ink-2)', fontSize: 12 }} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}

export default function Dashboard() {
  const query = useQuery({ queryKey: ['dashboard'], queryFn: () => api<DashboardData>('/api/dashboard'), retry: false })

  if (query.isPending) return <Spinner />
  if (query.error instanceof ApiError && query.error.status === 409) return <Onboarding />
  if (query.error) return <ErrorBox error={query.error} />
  const d = query.data
  const k = d.kpis

  return (
    <>
      <PageHeader
        title="Churn risk"
        subtitle={<>Churn risk for the next 8 weeks · model v{d.model_version} · scored {fmt.date(d.scored_at)}</>}
        actions={<Link to="/app/campaigns" className="inline-flex items-center gap-2 rounded-lg bg-accent px-3.5 py-2 text-sm font-medium text-accent-ink hover:brightness-110">
          Plan a campaign <ArrowRight className="size-4" aria-hidden /></Link>}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Stat label="Active customers" value={fmt.int(k.customers)} note="scored this week" />
        <Stat label="High risk" value={fmt.int(k.high_risk)} note={`${fmt.pct(k.high_risk / k.customers)} of customers`} />
        <Stat label="Expected churners" value={fmt.int(k.expected_churners_8w)} note="next 8 weeks" />
        <Stat label="Revenue at risk" value={fmt.compactMoney(k.revenue_at_risk)} note="probability × customer value" />
        <Stat label="Recommended for offer" value={fmt.int(k.recommended_for_offer)} note="profit-optimal threshold" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="Customers by risk tier">
          <ul className="space-y-4">
            {d.tiers.map((t) => (
              <li key={t.tier}>
                <div className="flex items-center justify-between text-sm">
                  <RiskBadge tier={t.tier} />
                  <span className="tabular text-ink">{fmt.int(t.customers)}</span>
                </div>
                <div className="mt-1.5 h-2 rounded-full bg-surface-2">
                  <div className="h-2 rounded-full" style={{ width: `${(t.customers / k.customers) * 100}%`, background: TIER_COLOR[t.tier] }} />
                </div>
                <div className="mt-1 text-xs text-muted">{fmt.compactMoney(t.revenue_at_risk)} revenue at risk</div>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Observed 8-week churn rate" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={d.churn_trend} margin={{ left: 0, right: 16, top: 8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="week" tickFormatter={(w) => `Wk ${w}`} {...AXIS} />
              <YAxis tickFormatter={fmt.pctTick} width={44} {...AXIS} />
              <Tooltip content={<ChartTooltip format={(v) => fmt.pct(v)} title={(l) => `Snapshot week ${l}`} />} />
              <Line dataKey="churn_rate" name="Churn rate" stroke={SERIES[0]} strokeWidth={2} animationDuration={500} dot={{ r: 3, strokeWidth: 0, fill: SERIES[0] }}
                activeDot={{ r: 5, stroke: 'var(--surface)', strokeWidth: 2 }} />
            </LineChart>
          </ResponsiveContainer>
          <p className="mt-2 text-xs text-muted">Share of active customers who churned within 8 weeks of each historical snapshot.</p>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <SegmentChart data={d.by_region} title="Risk by region" />
        <SegmentChart data={d.by_contract} title="Risk by contract type" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="What drives churn" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={Math.max(200, d.drivers.length * 30)}>
            <BarChart data={d.drivers} layout="vertical" margin={{ left: 8, right: 24 }} barCategoryGap={6}>
              <CartesianGrid horizontal={false} />
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="feature" width={190} tickFormatter={humanize} {...AXIS} />
              <Tooltip cursor={{ fill: 'var(--surface-2)' }} content={
                <ChartTooltip format={(v) => v.toFixed(3)} title={(l) => humanize(String(l))} />} />
              <Bar dataKey="importance" name="Mean |SHAP| impact" fill={SERIES[0]} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Model health" action={<Link to="/app/models" className="text-xs font-medium text-accent">Details</Link>}>
          <dl className="space-y-3 text-sm">
            {[
              ['Ranking quality (ROC AUC)', fmt.num(d.model.roc_auc, 3)],
              ['Lift in top 10%', `${fmt.num(d.model.lift_at_10pct, 1)}×`],
              ['Calibration error', fmt.num(d.model.ece, 4)],
              ['Test campaign profit', fmt.money(d.model.campaign_profit)],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4">
                <dt className="text-ink-2">{label}</dt>
                <dd className="tabular font-medium">{value}</dd>
              </div>
            ))}
            <div className="flex justify-between gap-4 border-t border-hairline pt-3">
              <dt className="text-ink-2">Data drift</dt>
              <dd>{d.drift ? <Link to="/app/monitoring"><DriftBadge status={d.drift.status} /></Link> : '–'}</dd>
            </div>
          </dl>
        </Card>
      </div>
    </>
  )
}
