import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Download, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartTooltip } from '../components/charts'
import { AXIS, SERIES } from '../lib/tokens'
import { Button, Card, ErrorBox, Field, Input, PageHeader, RiskBadge, Spinner, Stat, Td, Th } from '../components/ui'
import { ApiError, api, download } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmt, readableReasons, titleCase } from '../lib/format'
import type { Campaign, CampaignParams, CampaignPreview, RiskTier } from '../lib/types'
import Onboarding from './Onboarding'

const TIERS: RiskTier[] = ['high', 'medium', 'low']

function useDebounced<T>(value: T, ms = 350): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

function numberOrNull(value: string): number | null {
  return value.trim() === '' ? null : Number(value)
}

export default function Campaigns() {
  const { user } = useAuth()
  const org = user!.organization
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [params, setParams] = useState<CampaignParams>({
    offer_cost: org.offer_cost,
    retention_success_rate: org.retention_success_rate,
    months_of_value: org.months_of_value,
    budget: null,
    max_customers: null,
    risk_tiers: ['high', 'medium', 'low'],
    min_probability: 0,
  })
  const debounced = useDebounced(params)
  const valid = debounced.offer_cost >= 0 && debounced.retention_success_rate >= 0 && debounced.retention_success_rate <= 1
    && debounced.months_of_value > 0 && debounced.risk_tiers.length > 0

  const preview = useQuery({
    queryKey: ['campaign-preview', debounced],
    queryFn: () => api<CampaignPreview>('/api/campaigns/preview', { body: { ...debounced } }),
    enabled: valid,
    placeholderData: keepPreviousData,
    retry: false,
  })
  const saved = useQuery({ queryKey: ['campaigns'], queryFn: () => api<Campaign[]>('/api/campaigns') })
  const create = useMutation({
    mutationFn: () => api<Campaign>('/api/campaigns', { body: { ...params, name: name.trim() } }),
    onSuccess: () => {
      setName('')
      void queryClient.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })
  const remove = useMutation({
    mutationFn: (id: number) => api<void>(`/api/campaigns/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['campaigns'] }),
  })

  if (preview.error instanceof ApiError && preview.error.status === 409) return <Onboarding />
  const set = <K extends keyof CampaignParams>(key: K, value: CampaignParams[K]) => setParams((p) => ({ ...p, [key]: value }))
  const s = preview.data?.summary
  const chosen = s ? preview.data!.curve.reduce((best, point) =>
    Math.abs(point.customers - s.targeted_customers) < Math.abs(best.customers - s.targeted_customers) ? point : best,
  preview.data!.curve[0]) : null

  return (
    <>
      <PageHeader title="Retention campaigns"
        subtitle="Choose who gets an offer. Customers are ranked by expected profit: churn probability × success rate × customer value − offer cost." />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Campaign settings">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Offer cost ($)">
                <Input type="number" min={0} step="0.5" value={params.offer_cost} onChange={(e) => set('offer_cost', Number(e.target.value))} />
              </Field>
              <Field label="Success rate (%)" hint="share of churners the offer saves">
                <Input type="number" min={0} max={100} step="1" value={Math.round(params.retention_success_rate * 100)}
                  onChange={(e) => set('retention_success_rate', Number(e.target.value) / 100)} />
              </Field>
              <Field label="Months of value">
                <Input type="number" min={1} max={120} value={params.months_of_value} onChange={(e) => set('months_of_value', Number(e.target.value))} />
              </Field>
              <Field label="Min. probability (%)">
                <Input type="number" min={0} max={100} value={Math.round(params.min_probability * 100)}
                  onChange={(e) => set('min_probability', Number(e.target.value) / 100)} />
              </Field>
              <Field label="Budget ($)" hint="optional">
                <Input type="number" min={0} placeholder="No limit" value={params.budget ?? ''} onChange={(e) => set('budget', numberOrNull(e.target.value))} />
              </Field>
              <Field label="Max customers" hint="optional">
                <Input type="number" min={1} placeholder="No limit" value={params.max_customers ?? ''} onChange={(e) => set('max_customers', numberOrNull(e.target.value))} />
              </Field>
            </div>
            <fieldset>
              <legend className="text-xs font-medium text-ink-2">Risk tiers</legend>
              <div className="mt-1 flex gap-1">
                {TIERS.map((t) => {
                  const on = params.risk_tiers.includes(t)
                  return (
                    <button key={t} type="button" aria-pressed={on}
                      onClick={() => set('risk_tiers', on ? params.risk_tiers.filter((x) => x !== t) : [...params.risk_tiers, t])}
                      className={clsx('rounded-lg border px-3 py-2', on ? 'border-accent bg-surface-2' : 'border-hairline hover:bg-surface-2')}>
                      <RiskBadge tier={t} compact />
                    </button>
                  )
                })}
              </div>
            </fieldset>
            <form className="flex gap-2 border-t border-hairline pt-4" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
              <Input aria-label="Campaign name" required placeholder="Campaign name" value={name} onChange={(e) => setName(e.target.value)} />
              <Button type="submit" loading={create.isPending} disabled={!s || s.targeted_customers === 0}>Save</Button>
            </form>
            {create.error && <ErrorBox error={create.error} />}
          </div>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          {preview.error && <ErrorBox error={preview.error} />}
          {!s ? <Spinner label="Calculating…" /> : (
            <>
              <div className={clsx('grid grid-cols-2 gap-4 xl:grid-cols-4', preview.isFetching && 'opacity-70')}>
                <Stat label="Customers targeted" value={fmt.int(s.targeted_customers)} note={`of ${fmt.int(s.eligible_customers)} worth an offer`} />
                <Stat label="Campaign cost" value={fmt.money(s.campaign_cost)} />
                <Stat label="Expected revenue saved" value={fmt.money(s.expected_revenue_saved)}
                  note={`≈ ${fmt.int(s.expected_customers_retained)} customers retained`} />
                <Stat label="Expected profit" value={fmt.money(s.expected_profit)} note={s.roi != null ? `ROI ${fmt.pct(s.roi, 0)}` : undefined} />
              </div>
              <Card title="Expected profit by number of customers targeted">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={preview.data!.curve} margin={{ left: 8, right: 16, top: 8 }}>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="customers" type="number" domain={[0, 'dataMax']} tickFormatter={(v) => fmt.int(v)} {...AXIS} />
                    <YAxis tickFormatter={(v) => fmt.compactMoney(v)} width={60} {...AXIS} />
                    <Tooltip content={<ChartTooltip format={(v) => fmt.money(v)} title={(l) => `Top ${fmt.int(Number(l))} customers`} />} />
                    <Line dataKey="expected_profit" name="Expected profit" stroke={SERIES[0]} strokeWidth={2} dot={false}
                      activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }} />
                    {chosen && <ReferenceDot x={chosen.customers} y={chosen.expected_profit} r={6} fill={SERIES[0]} stroke="var(--surface)" strokeWidth={2} />}
                  </LineChart>
                </ResponsiveContainer>
                <p className="mt-2 text-xs text-muted">
                  The dot marks this campaign. Without a budget it stops where adding customers no longer adds profit.
                  Reaches {fmt.pct(s.share_of_expected_churners_reached)} of expected churners.
                </p>
              </Card>
              <Card title="Top targets">
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse">
                    <thead><tr><Th>Customer</Th><Th>Risk</Th><Th align="right">Probability</Th><Th align="right">Expected value</Th><Th>Contract</Th><Th>Main reasons</Th></tr></thead>
                    <tbody>
                      {preview.data!.top_targets.map((t) => (
                        <tr key={t.customer_id}>
                          <Td className="font-medium">{t.name ?? <span className="tabular">#{t.customer_id}</span>}</Td>
                          <Td><RiskBadge tier={t.risk_tier} compact /></Td>
                          <Td align="right">{fmt.pct(t.churn_probability)}</Td>
                          <Td align="right">{fmt.cents(t.expected_value)}</Td>
                          <Td>{titleCase(t.contract_type)}</Td>
                          <Td className="max-w-80 truncate text-xs text-ink-2">{readableReasons(t.top_reasons)}</Td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}
        </div>
      </div>

      <Card title="Saved campaigns" className="mt-4">
        {saved.isPending ? <Spinner /> : saved.data!.length === 0 ? (
          <p className="text-sm text-ink-2">No saved campaigns yet. Adjust the settings above and save one to export its target list.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead><tr><Th>Name</Th><Th>Created</Th><Th align="right">Customers</Th><Th align="right">Cost</Th><Th align="right">Expected profit</Th><Th>Model</Th><Th /></tr></thead>
              <tbody>
                {saved.data!.map((c) => (
                  <tr key={c.id}>
                    <Td className="font-medium">{c.name}</Td>
                    <Td>{fmt.date(c.created_at)}</Td>
                    <Td align="right">{fmt.int(c.summary.targeted_customers)}</Td>
                    <Td align="right">{fmt.money(c.summary.campaign_cost)}</Td>
                    <Td align="right">{fmt.money(c.summary.expected_profit)}</Td>
                    <Td>v{c.model_version} · wk {c.as_of_week}</Td>
                    <Td align="right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" onClick={() => download(`/api/campaigns/${c.id}/export`, `${c.name}.csv`)}>
                          <Download className="size-4" aria-hidden /> CSV
                        </Button>
                        <Button variant="ghost" aria-label={`Delete ${c.name}`} onClick={() => remove.mutate(c.id)}>
                          <Trash2 className="size-4" aria-hidden />
                        </Button>
                      </div>
                    </Td>
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
