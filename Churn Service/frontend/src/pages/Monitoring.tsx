import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartTooltip } from '../components/charts'
import { Button, Card, DriftBadge, Empty, ErrorBox, Notice, PageHeader, Spinner, Stat, Td, Th } from '../components/ui'
import { ApiError, api, openReport } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmt, humanize, titleCase } from '../lib/format'
import { AXIS, DRIFT_COLOR } from '../lib/tokens'
import type { DriftReport } from '../lib/types'

const WARNING = 0.1
const ALERT = 0.25

export default function Monitoring() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const drift = useQuery({ queryKey: ['drift'], queryFn: () => api<DriftReport>('/api/monitoring/drift'), retry: false })
  const run = useMutation({ mutationFn: () => api('/api/monitoring/run', { method: 'POST' }), onSuccess: () => queryClient.invalidateQueries() })

  const header = (
    <PageHeader title="Monitoring"
      subtitle="Compares this week's customers with the data the model was trained on. Drift means the model may be seeing a different world."
      actions={<>
        {drift.data && <Button variant="secondary" onClick={() => openReport('/api/monitoring/drift/report')}>Full report <ExternalLink className="size-3.5" aria-hidden /></Button>}
        {user?.role === 'owner' && <Button onClick={() => run.mutate()} loading={run.isPending}>Run drift check</Button>}
      </>} />
  )
  if (drift.isPending) return <>{header}<Spinner /></>
  if (drift.error instanceof ApiError && drift.error.status === 404) return <>{header}<Empty title="No drift report yet">Train a model; a drift check runs automatically afterwards.</Empty></>
  if (drift.error) return <>{header}<ErrorBox error={drift.error} /></>
  const d = drift.data
  const counts = { alert: 0, warning: 0, stable: 0 }
  for (const f of d.features) counts[f.status] += 1
  const top = d.features.slice(0, 12)
  const segments = (d.segments ?? []).filter((s) => s.status !== 'stable').slice(0, 15)

  return (
    <>
      {header}
      {run.error && <div className="mb-4"><ErrorBox error={run.error} /></div>}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Overall status" value={<DriftBadge status={d.status} />} note={`${fmt.int(d.n_current)} current vs ${fmt.int(d.n_reference)} training rows`} />
        <Stat label="Features with alerts" value={fmt.int(counts.alert)} note={`PSI ≥ ${ALERT}`} />
        <Stat label="Features with warnings" value={fmt.int(counts.warning)} note={`PSI ≥ ${WARNING}`} />
        <Stat label="Prediction drift (PSI)" value={d.prediction ? fmt.num(d.prediction.psi, 3) : '–'}
          note={d.prediction ? `mean ${fmt.pct(d.prediction.reference_mean)} → ${fmt.pct(d.prediction.current_mean)}` : undefined} />
      </div>
      {d.status === 'alert' && (
        <div className="mt-4"><Notice tone="warning">Significant drift detected. Review the segments below and consider retraining on recent data.</Notice></div>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card title="Most drifted features (global)" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={top.length * 30 + 40}>
            <BarChart data={top} layout="vertical" margin={{ left: 8, right: 24 }} barCategoryGap={6}>
              <CartesianGrid horizontal={false} />
              <XAxis type="number" {...AXIS} />
              <YAxis type="category" dataKey="feature" width={180} tickFormatter={humanize} {...AXIS} />
              <ReferenceLine x={WARNING} stroke="var(--muted)" strokeDasharray="4 4" />
              <ReferenceLine x={ALERT} stroke="var(--muted)" strokeDasharray="4 4" />
              <Tooltip cursor={{ fill: 'var(--surface-2)' }} content={
                <ChartTooltip format={(v, e) => `${v.toFixed(3)} · ${String(e.payload?.status)}`} title={(l) => humanize(String(l))} />} />
              <Bar dataKey="psi" name="PSI" radius={[0, 4, 4, 0]}>
                {top.map((f) => <Cell key={f.feature} fill={DRIFT_COLOR[f.status]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-xs text-muted">Dashed lines: warning ({WARNING}) and alert ({ALERT}) thresholds. Status is also listed in the table.</p>
        </Card>

        <Card title="Drift within segments" className="lg:col-span-3">
          {segments.length === 0 ? <p className="text-sm text-ink-2">No segment shows meaningful drift.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead><tr><Th>Segment</Th><Th>Feature</Th><Th align="right">PSI</Th><Th align="right">Mean then → now</Th><Th>Status</Th></tr></thead>
                <tbody>
                  {segments.map((s, i) => (
                    <tr key={i}>
                      <Td>{titleCase(s.segment.replace('=', ': '))}</Td>
                      <Td>{s.feature === '__prediction__' ? 'Model prediction' : humanize(s.feature)}</Td>
                      <Td align="right">{fmt.num(s.psi, 3)}</Td>
                      <Td align="right">{fmt.num(s.reference_mean, 2)} → {fmt.num(s.current_mean, 2)}</Td>
                      <Td><DriftBadge status={s.status} /></Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Card title="All features" className="mt-4">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead><tr><Th>Feature</Th><Th>Kind</Th><Th align="right">PSI</Th><Th align="right">KS p-value</Th><Th align="right">Training mean</Th><Th align="right">Current mean</Th><Th>Status</Th></tr></thead>
            <tbody>
              {d.features.map((f) => (
                <tr key={f.feature}>
                  <Td>{humanize(f.feature)}</Td>
                  <Td className="text-ink-2">{f.kind}</Td>
                  <Td align="right">{fmt.num(f.psi, 4)}</Td>
                  <Td align="right">{f.ks_pvalue == null ? '–' : f.ks_pvalue < 0.001 ? '< 0.001' : fmt.num(f.ks_pvalue, 3)}</Td>
                  <Td align="right">{fmt.num(f.reference_mean, 2)}</Td>
                  <Td align="right">{fmt.num(f.current_mean, 2)}</Td>
                  <Td><DriftBadge status={f.status} /></Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
