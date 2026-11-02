import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ExternalLink, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Button, Card, Empty, ErrorBox, Field, JobBadge, PageHeader, Select, Spinner, Stat, Td, Th } from '../components/ui'
import { api, form, openReport } from '../lib/api'
import { useAuth } from '../lib/auth'
import { fmt } from '../lib/format'
import { useDataStatus } from '../lib/hooks'
import type { Job, ModelDetail, ModelList } from '../lib/types'

const PROFILES: Record<string, string> = {
  quick: 'Quick (≈1 min)',
  standard: 'Standard (≈3 min)',
  thorough: 'Thorough (≈10 min)',
}
const PROFILE_HINTS: Record<string, string> = {
  quick: '3 model families with a few tuning trials. Good for a first look.',
  standard: 'All 5 families including the neural network, with more tuning.',
  thorough: 'Full hyperparameter search on all data. Best accuracy.',
}
const MODEL_NAMES: Record<string, string> = {
  'final model': 'Final model (calibrated ensemble)', logistic_regression: 'Logistic regression', random_forest: 'Random forest',
  lightgbm: 'LightGBM', xgboost: 'XGBoost', tabular_nn: 'Neural net (PyTorch)',
}

function StageBadge({ stage }: { stage: string }) {
  return (
    <span className={clsx('rounded-full border px-2 py-0.5 text-xs font-medium',
      stage === 'production' ? 'border-accent text-accent' : 'border-hairline text-ink-2')}>{stage}</span>
  )
}

function VersionDetail({ version }: { version: number }) {
  const query = useQuery({ queryKey: ['model', version], queryFn: () => api<ModelDetail>(`/api/models/${version}`) })
  if (query.isPending) return <Spinner />
  if (query.error) return <ErrorBox error={query.error} />
  const m = query.data
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Test ROC AUC" value={fmt.num(m.test.roc_auc, 3)} note="ranking quality" />
        <Stat label="Lift in top 10%" value={`${fmt.num(m.test.lift_at_10pct, 1)}×`} note="vs random targeting" />
        <Stat label="Calibration error" value={fmt.num(m.test.ece, 4)} note={`Brier ${fmt.num(m.test.brier, 4)}`} />
        <Stat label="Test campaign profit" value={fmt.money(m.test.campaign_profit)} note={`target-all: ${fmt.money(m.test.profit_if_target_all)}`} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead><tr><Th>Model</Th><Th align="right">Blend weight</Th><Th align="right">Validation AUC</Th><Th align="right">Test AUC</Th><Th align="right">Test avg precision</Th><Th align="right">Trials</Th></tr></thead>
          <tbody>
            {[...m.leaderboard].sort((a, b) => (a.model === 'final model' ? -1 : b.model === 'final model' ? 1 : b.test_roc_auc - a.test_roc_auc)).map((row) => (
              <tr key={row.model} className={clsx(row.model === 'final model' && 'font-medium')}>
                <Td>{MODEL_NAMES[row.model] ?? row.model}</Td>
                <Td align="right">{row.weight != null ? fmt.num(row.weight, 2) : '–'}</Td>
                <Td align="right">{fmt.num(row.val_roc_auc, 4)}</Td>
                <Td align="right">{fmt.num(row.test_roc_auc, 4)}</Td>
                <Td align="right">{fmt.num(row.test_average_precision, 4)}</Td>
                <Td align="right">{row.trials ?? '–'}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">
        Trained on {fmt.int(m.rows.train)} rows; validated on weeks {m.split.validation?.join(', ')}; tested out of time on weeks {m.split.test?.join(', ')}.
        {m.promotion.reason && <> Promotion: {m.promotion.reason}.</>}
      </p>
    </div>
  )
}

export default function Models() {
  const { user } = useAuth()
  const isOwner = user?.role === 'owner'
  const queryClient = useQueryClient()
  const status = useDataStatus()
  const [profile, setProfile] = useState('quick')
  const [selected, setSelected] = useState<number | null>(null)
  const models = useQuery({ queryKey: ['models'], queryFn: () => api<ModelList>('/api/models') })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => api<Job[]>('/api/jobs?limit=10'), refetchInterval: 5000 })

  const refresh = () => queryClient.invalidateQueries()
  const train = useMutation({ mutationFn: () => api<Job>('/api/models/train', { body: form({ profile }) }), onSuccess: refresh })
  const promote = useMutation({ mutationFn: (v: number) => api(`/api/models/${v}/promote`, { method: 'POST' }), onSuccess: refresh })
  const rollback = useMutation({ mutationFn: () => api('/api/models/rollback', { method: 'POST' }), onSuccess: refresh })

  if (models.isPending) return <Spinner />
  if (models.error) return <ErrorBox error={models.error} />
  const list = models.data
  const shown = selected ?? list.production ?? list.versions.at(-1)?.version ?? null
  const busy = Boolean(status.data?.active_job)

  return (
    <>
      <PageHeader title="Models" subtitle="Every training run registers a version. A new version only replaces production if it performs at least as well." />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Train a new version">
          <Field label="Training preset" hint={PROFILE_HINTS[profile]}>
            <Select value={profile} onChange={(e) => setProfile(e.target.value)}>
              {list.training_profiles.map((p) => <option key={p} value={p}>{PROFILES[p] ?? p}</option>)}
            </Select>
          </Field>
          <Button className="mt-4 w-full" onClick={() => train.mutate()} loading={train.isPending}
            disabled={!isOwner || busy || !status.data?.has_data}>
            {busy ? 'A job is running…' : 'Start training'}
          </Button>
          {train.error && <div className="mt-3"><ErrorBox error={train.error} /></div>}
          {!status.data?.has_data && <p className="mt-3 text-xs text-muted">Load data first.</p>}
        </Card>

        <Card title="Versions" className="lg:col-span-2"
          action={isOwner && list.versions.length > 1 && (
            <Button variant="ghost" onClick={() => rollback.mutate()} loading={rollback.isPending}>
              <RotateCcw className="size-4" aria-hidden /> Roll back
            </Button>)}>
          {list.versions.length === 0 ? <p className="text-sm text-ink-2">No models yet.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead><tr><Th>Version</Th><Th>Stage</Th><Th>Created</Th><Th align="right">Test AUC</Th><Th align="right">Test profit</Th><Th /></tr></thead>
                <tbody>
                  {[...list.versions].reverse().map((v) => (
                    <tr key={v.version} onClick={() => setSelected(v.version)}
                      className={clsx('cursor-pointer hover:bg-surface-2', shown === v.version && 'bg-surface-2')}>
                      <Td className="font-medium">v{String(v.version).padStart(4, '0')}</Td>
                      <Td><StageBadge stage={v.stage} /></Td>
                      <Td>{fmt.date(v.created_at)}</Td>
                      <Td align="right">{fmt.num(v.test_roc_auc, 4)}</Td>
                      <Td align="right">{fmt.money(v.test_campaign_profit)}</Td>
                      <Td align="right">
                        <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" onClick={() => openReport(`/api/models/${v.version}/report`)}>
                            Report <ExternalLink className="size-3.5" aria-hidden />
                          </Button>
                          {isOwner && v.stage !== 'production' && (
                            <Button variant="secondary" onClick={() => promote.mutate(v.version)} loading={promote.isPending}>Promote</Button>
                          )}
                        </div>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <div className="mt-4">
        {shown != null ? (
          <Card title={`Version v${String(shown).padStart(4, '0')}`}><VersionDetail version={shown} /></Card>
        ) : <Empty title="No model yet">Load data and train to see model quality here.</Empty>}
      </div>

      <Card title="Recent jobs" className="mt-4">
        {jobs.isPending ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead><tr><Th>Job</Th><Th>Status</Th><Th>Started</Th><Th>Details</Th></tr></thead>
              <tbody>
                {jobs.data!.map((j) => (
                  <tr key={j.id}>
                    <Td className="font-medium">#{j.id} {j.kind}</Td>
                    <Td><JobBadge status={j.status} /></Td>
                    <Td>{fmt.date(j.started_at ?? j.created_at)}</Td>
                    <Td className="max-w-md truncate text-xs text-ink-2">
                      {j.status === 'failed' ? j.error?.split('\n')[0] : j.status === 'succeeded' && j.result.version
                        ? `v${j.result.version} · AUC ${j.result.test_roc_auc} · ${j.result.promoted ? 'promoted' : 'not promoted'}` : j.message}
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
