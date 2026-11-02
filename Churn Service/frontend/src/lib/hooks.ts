import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { api } from './api'
import type { DataStatus, Job } from './types'

export function useDataStatus() {
  return useQuery({
    queryKey: ['data-status'],
    queryFn: () => api<DataStatus>('/api/data/status'),
    // Poll while a data load or training job runs, so the banner and pages update themselves.
    refetchInterval: (query) => (query.state.data?.active_job ? 2500 : false),
  })
}

/** Poll one job until it finishes; refresh everything once it succeeds. */
export function useJob(jobId: number | null) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api<Job>(`/api/jobs/${jobId}`),
    enabled: jobId != null,
    refetchInterval: (q) => (q.state.data && ['succeeded', 'failed'].includes(q.state.data.status) ? false : 2000),
  })
  const notified = useRef<number | null>(null)
  useEffect(() => {
    const job = query.data
    if (job && job.status === 'succeeded' && notified.current !== job.id) {
      notified.current = job.id
      void queryClient.invalidateQueries()
    }
  }, [query.data, queryClient])
  return query
}
