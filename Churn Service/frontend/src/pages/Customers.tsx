import { keepPreviousData, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { Card, ErrorBox, Input, PageHeader, RiskBadge, Select, Spinner, Td, Th } from '../components/ui'
import { ApiError, api } from '../lib/api'
import { fmt, titleCase } from '../lib/format'
import type { CustomerPage, RiskTier } from '../lib/types'
import Onboarding from './Onboarding'

const TIERS: RiskTier[] = ['high', 'medium', 'low']
const SORTS = [
  ['probability', 'Churn probability'],
  ['revenue', 'Revenue at risk'],
  ['charge', 'Monthly charge'],
  ['tenure', 'Tenure'],
] as const

export default function Customers() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState(params.get('search') ?? '')

  const tier = params.getAll('tier')
  const region = params.get('region') ?? ''
  const contract = params.get('contract') ?? ''
  const sort = params.get('sort') ?? 'probability'
  const page = Number(params.get('page') ?? 1)

  const update = (changes: Record<string, string | string[] | null>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      next.delete(key)
      if (Array.isArray(value)) value.forEach((v) => next.append(key, v))
      else if (value) next.set(key, value)
    }
    if (!('page' in changes)) next.delete('page')
    setParams(next, { replace: true })
  }

  const query = useQuery({
    queryKey: ['customers', params.toString()],
    queryFn: () => {
      const q = new URLSearchParams(params)
      q.set('page_size', '25')
      return api<CustomerPage>(`/api/customers?${q}`)
    },
    placeholderData: keepPreviousData,
    retry: false,
  })

  if (query.error instanceof ApiError && query.error.status === 409) return <Onboarding />
  const data = query.data
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader
        title="Customers"
        subtitle={data ? `${fmt.int(data.total)} matching customers · as of week ${data.as_of_week} · model v${data.model_version}` : ' '}
      />

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <form className="relative min-w-48 flex-1" onSubmit={(e) => { e.preventDefault(); update({ search: search.trim() || null }) }}>
            <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-muted" aria-hidden />
            <Input aria-label="Search by customer ID" placeholder="Search customer ID" value={search}
              onChange={(e) => setSearch(e.target.value)} className="pl-9" inputMode="numeric" />
          </form>
          <div className="flex gap-1" role="group" aria-label="Risk tier filter">
            {TIERS.map((t) => {
              const on = tier.includes(t)
              return (
                <button key={t} onClick={() => update({ tier: on ? tier.filter((x) => x !== t) : [...tier, t] })}
                  aria-pressed={on}
                  className={clsx('rounded-lg border px-3 py-2', on ? 'border-accent bg-surface-2' : 'border-hairline hover:bg-surface-2')}>
                  <RiskBadge tier={t} compact />
                </button>
              )
            })}
          </div>
          <Select aria-label="Region" value={region} onChange={(e) => update({ region: e.target.value || null })} className="w-36">
            <option value="">All regions</option>
            {data?.facets.region.map((r) => <option key={r} value={r}>{titleCase(r)}</option>)}
          </Select>
          <Select aria-label="Contract" value={contract} onChange={(e) => update({ contract: e.target.value || null })} className="w-44">
            <option value="">All contracts</option>
            {data?.facets.contract_type.map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}
          </Select>
          <Select aria-label="Sort by" value={sort} onChange={(e) => update({ sort: e.target.value })} className="w-48">
            {SORTS.map(([value, label]) => <option key={value} value={value}>Sort: {label}</option>)}
          </Select>
        </div>

        <div className="mt-5 overflow-x-auto">
          {query.isPending ? <Spinner /> : query.error ? <ErrorBox error={query.error} /> : (
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <Th>Customer</Th><Th>Risk</Th><Th align="right">Churn probability</Th><Th align="right">Revenue at risk</Th>
                  <Th>Region</Th><Th>Plan</Th><Th>Contract</Th><Th align="right">Tenure</Th><Th align="right">Monthly</Th><Th>Offer</Th>
                </tr>
              </thead>
              <tbody className={clsx(query.isFetching && 'opacity-60')}>
                {data!.items.map((c) => (
                  <tr key={c.customer_id} tabIndex={0} onClick={() => navigate(`/app/customers/${c.customer_id}`)}
                    onKeyDown={(e) => e.key === 'Enter' && navigate(`/app/customers/${c.customer_id}`)}
                    className="cursor-pointer hover:bg-surface-2 focus:bg-surface-2">
                    <Td className="font-medium">{c.name ? <>{c.name} <span className="tabular text-xs font-normal text-muted">#{c.customer_id}</span></> : <span className="tabular">#{c.customer_id}</span>}</Td>
                    <Td><RiskBadge tier={c.risk_tier} compact /></Td>
                    <Td align="right">{fmt.pct(c.churn_probability)}</Td>
                    <Td align="right">{fmt.money(c.expected_revenue_at_risk)}</Td>
                    <Td>{titleCase(c.region)}</Td>
                    <Td>{titleCase(c.plan)}</Td>
                    <Td>{titleCase(c.contract_type)}</Td>
                    <Td align="right">{fmt.weeks(c.tenure_weeks)}</Td>
                    <Td align="right">{fmt.cents(c.current_charge)}</Td>
                    <Td>{c.target_for_retention ? <span className="text-xs font-medium text-accent">Recommended</span> : <span className="text-xs text-muted">–</span>}</Td>
                  </tr>
                ))}
                {data!.items.length === 0 && (
                  <tr><td colSpan={10} className="py-10 text-center text-sm text-ink-2">No customers match these filters.</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        {data && data.total > 0 && (
          <div className="mt-4 flex items-center justify-between text-sm text-ink-2">
            <span>Page {page} of {pages}</span>
            <div className="flex gap-2">
              <button className="rounded-lg border border-hairline p-2 hover:bg-surface-2 disabled:opacity-40" aria-label="Previous page"
                disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}><ChevronLeft className="size-4" /></button>
              <button className="rounded-lg border border-hairline p-2 hover:bg-surface-2 disabled:opacity-40" aria-label="Next page"
                disabled={page >= pages} onClick={() => update({ page: String(page + 1) })}><ChevronRight className="size-4" /></button>
            </div>
          </div>
        )}
      </Card>
    </>
  )
}
