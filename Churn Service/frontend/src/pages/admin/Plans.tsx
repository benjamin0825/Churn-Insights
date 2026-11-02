import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ExternalLink, Plus, Star, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { Button, Card, ErrorBox, Field, Input, Notice, Spinner } from '../../components/ui'
import { api } from '../../lib/api'
import { fmt } from '../../lib/format'
import { usePlans } from './hooks'
import { AdminHeader, Dialog, Pill, type Plan } from './shared'

const EMPTY: Plan = { key: '', name: '', monthly_price: 0, blurb: '', limits: [], features: [], popular: false, active: true, sort_order: 0 }

const textarea = 'w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none'
const lines = (text: string) => text.split('\n').map((l) => l.trim()).filter(Boolean)

function PlanForm({ initial, isNew, onDone }: { initial: Plan; isNew: boolean; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [plan, setPlan] = useState(initial)
  const [limits, setLimits] = useState(initial.limits.join('\n'))
  const [features, setFeatures] = useState(initial.features.join('\n'))
  const save = useMutation({
    mutationFn: () => {
      const { organizations: _, ...rest } = plan
      const body = { ...rest, limits: lines(limits), features: lines(features) }
      return isNew ? api<Plan>('/api/admin/plans', { body }) : api<Plan>(`/api/admin/plans/${plan.key}`, { method: 'PUT', body })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin'] })
      void queryClient.invalidateQueries({ queryKey: ['plans'] })
      onDone()
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const set = <K extends keyof Plan>(key: K, value: Plan[K]) => setPlan({ ...plan, [key]: value })

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Name"><Input required value={plan.name} onChange={(e) => set('name', e.target.value)} /></Field>
        <Field label="Key" hint={isNew ? 'Lowercase letters, numbers, dashes' : "Can't be changed"}>
          <Input required disabled={!isNew} pattern="[a-z0-9][a-z0-9\-]*" value={plan.key}
            onChange={(e) => set('key', e.target.value.toLowerCase())} />
        </Field>
        <Field label="Monthly price ($)"><Input required type="number" min={0} step="1" value={plan.monthly_price} onChange={(e) => set('monthly_price', Number(e.target.value))} /></Field>
        <Field label="Order on pricing page"><Input type="number" value={plan.sort_order} onChange={(e) => set('sort_order', Number(e.target.value))} /></Field>
      </div>
      <Field label="Description"><textarea className={textarea} rows={2} maxLength={300} value={plan.blurb} onChange={(e) => set('blurb', e.target.value)} /></Field>
      <Field label="Limits" hint="One per line, e.g. “Up to 1,000 customers”">
        <textarea className={textarea} rows={2} value={limits} onChange={(e) => setLimits(e.target.value)} />
      </Field>
      <Field label="Features" hint="One per line">
        <textarea className={textarea} rows={5} value={features} onChange={(e) => setFeatures(e.target.value)} />
      </Field>
      <div className="flex flex-wrap gap-5 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--accent)]" checked={plan.active} onChange={(e) => set('active', e.target.checked)} /> Show on pricing page</label>
        <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--accent)]" checked={plan.popular} onChange={(e) => set('popular', e.target.checked)} /> Mark as “Popular”</label>
      </div>
      {save.error && <ErrorBox error={save.error} />}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancel</Button>
        <Button type="submit" loading={save.isPending}>{isNew ? 'Create plan' : 'Save changes'}</Button>
      </div>
    </form>
  )
}

export default function Plans() {
  const queryClient = useQueryClient()
  const plans = usePlans()
  const [editing, setEditing] = useState<{ plan: Plan; isNew: boolean } | null>(null)
  const [deleting, setDeleting] = useState<Plan | null>(null)
  const remove = useMutation({
    mutationFn: (key: string) => api<void>(`/api/admin/plans/${key}`, { method: 'DELETE' }),
    onSuccess: () => {
      setDeleting(null)
      void queryClient.invalidateQueries({ queryKey: ['admin'] })
    },
  })

  return (
    <>
      <AdminHeader title="Plans" subtitle="What the public pricing page shows, and which plan each workspace is on"
        actions={
          <>
            <Link to="/pricing" target="_blank" className="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium text-ink-2 hover:bg-surface-2 hover:text-ink">
              View pricing page <ExternalLink className="size-3.5" aria-hidden />
            </Link>
            <Button onClick={() => setEditing({ plan: { ...EMPTY, sort_order: (plans.data?.length ?? 0) + 1 }, isNew: true })}>
              <Plus className="size-4" aria-hidden /> New plan
            </Button>
          </>
        } />
      <div className="mb-4"><Notice>Plans are labels for now: the app doesn't charge cards or enforce limits. Assign a plan to a workspace from its page.</Notice></div>

      {plans.error && <ErrorBox error={plans.error} />}
      {plans.isPending ? <Spinner /> : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {plans.data?.map((p) => (
            <Card key={p.key} title={<span className="flex items-center gap-2">{p.name}{p.popular && <Star className="size-4 fill-warning text-warning" aria-label="Popular" />}</span>}
              action={p.active ? <Pill tone="good">Shown</Pill> : <Pill>Hidden</Pill>}>
              <p className="flex items-baseline gap-1"><span className="tabular text-3xl font-semibold">{fmt.money(p.monthly_price)}</span><span className="text-sm text-ink-2">/ month</span></p>
              <p className="mt-2 text-sm text-ink-2">{p.blurb || '–'}</p>
              <ul className="mt-3 space-y-1 text-sm">
                {p.limits.map((l) => <li key={l} className="text-ink">{l}</li>)}
              </ul>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink-2">
                {p.features.slice(0, 6).map((f) => <li key={f}>{f}</li>)}
                {p.features.length > 6 && <li className="list-none text-muted">+{p.features.length - 6} more</li>}
              </ul>
              <div className="mt-5 flex items-center justify-between border-t border-hairline pt-4">
                <span className="text-sm text-ink-2"><span className="tabular font-semibold text-ink">{fmt.int(p.organizations ?? 0)}</span> workspace(s) · key <code>{p.key}</code></span>
                <span className="flex gap-1">
                  <Button variant="ghost" onClick={() => setEditing({ plan: p, isNew: false })}>Edit</Button>
                  <Button variant="ghost" aria-label={`Delete ${p.name}`} onClick={() => { remove.reset(); setDeleting(p) }}><Trash2 className="size-4" /></Button>
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={editing != null} title={editing?.isNew ? 'New plan' : `Edit ${editing?.plan.name}`} onClose={() => setEditing(null)} wide>
        {editing && <PlanForm key={editing.plan.key || 'new'} initial={editing.plan} isNew={editing.isNew} onDone={() => setEditing(null)} />}
      </Dialog>

      <Dialog open={deleting != null} title={`Delete ${deleting?.name}?`} onClose={() => setDeleting(null)}>
        <p className="text-sm text-ink-2">
          {deleting?.organizations ? `${deleting.organizations} workspace(s) are on this plan. Move them to another plan first, or hide the plan instead.`
            : 'The plan disappears from the pricing page. No workspace uses it.'}
        </p>
        {remove.error && <div className="mt-3"><ErrorBox error={remove.error} /></div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setDeleting(null)}>Cancel</Button>
          <Button variant="danger" loading={remove.isPending} disabled={!!deleting?.organizations} onClick={() => deleting && remove.mutate(deleting.key)}>Delete</Button>
        </div>
      </Dialog>
    </>
  )
}
