import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Database, Sparkles } from 'lucide-react'
import { Link } from 'react-router'
import { Button, Card, ErrorBox, FailedJobNotice, JobBadge, Notice, PageHeader } from '../components/ui'
import { api, form } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useDataStatus } from '../lib/hooks'
import type { Job } from '../lib/types'

/** First-run screen: no scores yet. */
export default function Onboarding() {
  const { user } = useAuth()
  const status = useDataStatus()
  const queryClient = useQueryClient()
  const demo = useMutation({
    mutationFn: () => api<Job>('/api/data/demo', { body: form({ customers: 10000, profile: 'quick' }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['data-status'] }),
  })
  const active = status.data?.active_job
  const isOwner = user?.role === 'owner'

  return (
    <>
      <PageHeader title={`Welcome, ${user?.name.split(' ')[0] ?? ''}`} subtitle="Two steps to your first churn forecast." />
      {!active && status.data?.last_job?.status === 'failed' && (
        <div className="mb-4"><FailedJobNotice job={status.data.last_job} /></div>
      )}
      {active ? (
        <Card title="Getting things ready">
          <div className="flex items-center gap-3"><JobBadge status={active.status} /><span className="text-sm text-ink-2">{active.message}</span></div>
          <p className="mt-3 text-sm text-ink-2">This page updates on its own when the model is ready, usually within a minute or two.</p>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Card title={<span className="flex items-center gap-2"><Sparkles className="size-4 text-accent" />Explore with demo data</span>}>
            <p className="text-sm text-ink-2">
              Generate a realistic subscription business: 10,000 customers with two years of usage, billing and support tickets.
              A model is trained and every customer is scored automatically.
            </p>
            <Button className="mt-4" onClick={() => demo.mutate()} loading={demo.isPending} disabled={!isOwner}>Load demo data</Button>
            {demo.error && <div className="mt-3"><ErrorBox error={demo.error} /></div>}
          </Card>
          <Card title={<span className="flex items-center gap-2"><Database className="size-4 text-accent" />Use your own data</span>}>
            <p className="text-sm text-ink-2">
              Upload four CSV exports (customers, weekly usage, invoices and support tickets). Templates show the exact format.
            </p>
            <Link to="/app/data" className="mt-4 inline-flex rounded-lg border border-hairline px-3.5 py-2 text-sm font-medium hover:bg-surface-2">Go to data upload</Link>
          </Card>
        </div>
      )}
      {!isOwner && <div className="mt-4"><Notice>Only organization owners can load data. Ask your owner to get started.</Notice></div>}
    </>
  )
}
