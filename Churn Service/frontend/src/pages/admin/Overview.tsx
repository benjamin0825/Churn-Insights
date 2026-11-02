import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartTooltip } from '../../components/charts'
import { Card, ErrorBox, Spinner, Stat } from '../../components/ui'
import { api } from '../../lib/api'
import { fmt, timeAgo } from '../../lib/format'
import { AXIS } from '../../lib/tokens'
import { AdminHeader, type AdminStats } from './shared'

const weekLabel = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

export default function AdminOverview() {
  const query = useQuery({ queryKey: ['admin', 'stats'], queryFn: () => api<AdminStats>('/api/admin/stats'), refetchInterval: 15000 })
  if (query.isPending) return <Spinner />
  if (query.error) return <ErrorBox error={query.error} />
  const s = query.data
  const planTotal = s.by_plan.reduce((sum, p) => sum + p.organizations, 0) || 1

  return (
    <>
      <AdminHeader title="Overview" subtitle="Everything across all workspaces" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Workspaces" value={fmt.int(s.organizations)} note={`${fmt.int(s.new_organizations_30d)} new in 30 days`} emphasis />
        <Stat label="Active in 30 days" value={fmt.int(s.active_organizations_30d)} note={`${fmt.int(s.suspended)} suspended`} emphasis />
        <Stat label="Users" value={fmt.int(s.users)} note={`${fmt.int(s.admins)} admin${s.admins === 1 ? '' : 's'}`} emphasis />
        <Stat label="Jobs running" value={fmt.int(s.jobs.running + s.jobs.queued)}
          note={<span className={s.jobs.failed_7d ? 'text-critical-ink' : undefined}>{fmt.int(s.jobs.failed_7d)} failed in 7 days</span>} emphasis />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card title="New workspaces per week">
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={s.signups_by_week} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="week_start" tickFormatter={weekLabel} {...AXIS} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} {...AXIS} />
                <Tooltip cursor={{ fill: 'var(--surface-2)' }}
                  content={<ChartTooltip title={(l) => `Week of ${weekLabel(String(l))}`} />} />
                <Bar dataKey="organizations" name="New workspaces" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Workspaces by plan" action={<Link to="/admin/plans" className="text-xs font-medium text-accent">Manage plans</Link>}>
          <ul className="space-y-4">
            {s.by_plan.map((p) => (
              <li key={p.plan}>
                <div className="flex justify-between text-sm">
                  <Link to={`/admin/workspaces?plan=${p.plan}`} className="text-ink hover:text-accent">{p.name}</Link>
                  <span className="tabular text-ink-2">{fmt.int(p.organizations)}</span>
                </div>
                <div className="mt-1.5 h-2 rounded-full bg-surface-2">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${(p.organizations / planTotal) * 100}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Recent failed jobs" className="mt-4"
        action={<Link to="/admin/jobs?status=failed" className="text-xs font-medium text-accent">All jobs</Link>}>
        {s.recent_failures.length === 0 ? (
          <p className="text-sm text-ink-2">No failures in the last 7 days.</p>
        ) : (
          <ul className="divide-y divide-hairline">
            {s.recent_failures.map((j) => (
              <li key={j.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                <span>
                  <span className="font-medium text-ink">#{j.id} {j.kind}</span>{' '}
                  <Link to={`/admin/workspaces/${j.organization_id}`} className="text-accent">{j.organization_name ?? `workspace ${j.organization_id}`}</Link>
                </span>
                <span className="max-w-full truncate text-ink-2 sm:max-w-[50%]" title={j.error ?? ''}>{j.error?.split('\n')[0] ?? j.message}</span>
                <span className="text-xs text-muted">{timeAgo(j.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
