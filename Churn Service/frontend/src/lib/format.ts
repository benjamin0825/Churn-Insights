import type { MetricFormat } from './types'

const integer = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const moneyCents = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
const compactMoney = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 })

export const fmt = {
  int: (v: number | null | undefined) => (v == null ? '–' : integer.format(v)),
  money: (v: number | null | undefined) => (v == null ? '–' : money.format(v)),
  cents: (v: number | null | undefined) => (v == null ? '–' : moneyCents.format(v)),
  compactMoney: (v: number | null | undefined) => (v == null ? '–' : compactMoney.format(v)),
  pct: (v: number | null | undefined, digits = 1) => (v == null ? '–' : `${(v * 100).toFixed(digits)}%`),
  /** Axis ticks: whole percents when exact, one decimal otherwise (2.5% must not read as "3%"). */
  pctTick: (v: number) => {
    const p = v * 100
    return `${Number.isInteger(Math.round(p * 10) / 10) ? p.toFixed(0) : p.toFixed(1)}%`
  },
  num: (v: number | null | undefined, digits = 2) => (v == null ? '–' : v.toFixed(digits)),
  date: (iso: string | null | undefined) =>
    iso ? new Date(iso).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' }) : '–',
  weeks: (v: number | null | undefined) => {
    if (v == null) return '–'
    if (v < 8) return `${Math.round(v)} wk`
    const months = v / 4.345
    return months < 24 ? `${Math.round(months)} mo` : `${(months / 12).toFixed(1)} yr`
  },
}

/** "Sarah Mitchell", or "Customer #16220" when there is no name. */
export const customerLabel = (c: { customer_id: number; name?: string | null }) => c.name || `Customer #${c.customer_id}`

export function humanize(feature: string): string {
  return feature
    .replace(/_(\d+)w$/, ' ($1 wk)')
    .replace(/_/g, ' ')
    .replace(/^./, (c) => c.toUpperCase())
}

/** "sessions_mean_4w (+0.71); contract_type (+0.57)" -> "Sessions mean (4 wk) +0.71 · Contract type +0.57" */
export function readableReasons(reasons: string | null | undefined, limit = 2): string {
  if (!reasons) return '–'
  return reasons
    .split(';')
    .slice(0, limit)
    .map((part) => {
      const match = part.trim().match(/^(\w+)\s*\(([+-][\d.]+)\)$/)
      return match ? `${humanize(match[1])} ${match[2]}` : part.trim()
    })
    .join(' · ')
}

export function titleCase(value: string): string {
  return value.replace(/(^|[\s-])\w/g, (c) => c.toUpperCase())
}

export function formatMetric(value: number | null | undefined, format: MetricFormat, compact = false): string {
  if (value == null) return '–'
  switch (format) {
    case 'money':
      return compact ? fmt.compactMoney(value) : fmt.money(value)
    case 'cents':
      return fmt.cents(value)
    case 'pct':
      return fmt.pct(value, 2)
    default:
      return compact && Math.abs(value) >= 10_000 ? new Intl.NumberFormat('en-US', { notation: 'compact' }).format(value) : fmt.int(value)
  }
}


/** "5 min ago", "3 h ago", "12 d ago", then a date. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '–'
  const minutes = (Date.now() - new Date(iso).getTime()) / 60000
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${Math.round(minutes)} min ago`
  if (minutes < 60 * 24) return `${Math.round(minutes / 60)} h ago`
  const days = Math.round(minutes / 60 / 24)
  return days < 45 ? `${days} d ago` : new Date(iso).toLocaleDateString('en-US', { dateStyle: 'medium' })
}
