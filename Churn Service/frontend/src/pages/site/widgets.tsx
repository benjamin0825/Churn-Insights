import clsx from 'clsx'
import { CreditCard, MessageSquareWarning, Sparkles, TrendingDown, UserPlus } from 'lucide-react'
import type { ReactNode } from 'react'
import { FEATURED_CUSTOMER as customer } from '../../lib/sample-customers'

// Illustrative product widgets for the marketing pages. Numbers mirror the demo workspace.

const red = 'var(--critical-ink)'
const green = 'var(--good-ink)'

/** Points of `values` scaled into a w×h box. */
function points(values: number[], w: number, h: number, pad = 4): [number, number][] {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return values.map((v, i) => [pad + (i / (values.length - 1)) * (w - pad * 2), pad + (1 - (v - min) / span) * (h - pad * 2)])
}

/** SVG path through `values`, scaled into a w×h box. */
function linePath(values: number[], w: number, h: number, pad = 4) {
  return points(values, w, h, pad).map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
}

export function WidgetCard({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx('h-full rounded-2xl bg-surface p-7 shadow-[0_12px_48px_-12px_rgb(45_48_71/0.18)]', className)}>
      {children}
    </div>
  )
}

function Centered({ title, value, tone = 'accent' }: { title: string; value: string; tone?: 'accent' | 'good' | 'critical' }) {
  return (
    <div className="text-center">
      <div className="text-[15px] text-ink-2">{title}</div>
      <div className={clsx('tabular mt-1 text-2xl font-bold',
        tone === 'accent' ? 'text-accent' : tone === 'good' ? 'text-good-ink' : 'text-critical-ink')}>{value}</div>
    </div>
  )
}

/* ---------- Metrics ---------- */

export function MrrWidget() {
  const data = [532, 534, 533, 537, 536, 539, 541, 540, 544, 546, 545, 549, 551, 548, 547]
  return (
    <WidgetCard>
      <Centered title="Monthly recurring revenue" value="$547,319" />
      <svg viewBox="0 0 300 150" className="mt-6 w-full" role="img" aria-label="MRR trend, up 1.7%">
        {[0, 1, 2, 3, 4].map((r) => <line key={r} x1="0" x2="300" y1={8 + r * 33} y2={8 + r * 33} stroke="var(--hairline)" />)}
        <path d={`${linePath(data, 300, 150, 8)} L292,150 L8,150 Z`} fill="var(--accent-soft)" className="fade-in-late" />
        <path d={linePath(data, 300, 150, 8)} pathLength={1} className="draw-path" fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinejoin="round" />
      </svg>
      <p className="mt-3 text-center text-xs text-muted">↑ 1.7% over the last 26 weeks</p>
    </WidgetCard>
  )
}

export function ForecastWidget() {
  const tiers = [
    { label: 'High risk', n: 1184, color: 'var(--critical)' },
    { label: 'Medium risk', n: 1798, color: 'var(--warning)' },
    { label: 'Low risk', n: 4584, color: 'var(--good)' },
  ]
  const total = tiers.reduce((s, t) => s + t.n, 0)
  return (
    <WidgetCard>
      <Centered title="Revenue at risk" value="$445,607" tone="critical" />
      <p className="mt-1 text-center text-xs text-muted">≈ 527 customers expected to leave in 8 weeks</p>
      <div className="grow-x mt-7 flex h-3 overflow-hidden rounded-full" aria-hidden>
        {tiers.map((t) => <span key={t.label} style={{ width: `${(t.n / total) * 100}%`, background: t.color }} />)}
      </div>
      <ul className="mt-6 space-y-3">
        {tiers.map((t) => (
          <li key={t.label} className="tabular flex items-center justify-between text-[15px]">
            <span className="flex items-center gap-2 text-ink-2"><span className="size-2.5 rounded-full" style={{ background: t.color }} />{t.label}</span>
            <span className="font-semibold text-ink">{t.n.toLocaleString()}</span>
          </li>
        ))}
      </ul>
    </WidgetCard>
  )
}

/* ---------- Understanding churn ---------- */

export function ReasonsWidget() {
  const reasons = [
    { label: 'Sessions fell (4 wk)', w: 100 },
    { label: 'Month-to-month contract', w: 48 },
    { label: 'Customer for 5 weeks', w: 44 },
    { label: 'Pays by electronic check', w: 41 },
    { label: 'Asked about cancelling', w: 37 },
  ]
  return (
    <WidgetCard>
      <div className="flex items-center gap-3">
        <img src={customer.photo} alt="" width={44} height={44} className="size-11 rounded-full object-cover ring-2 ring-surface" />
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold text-ink">{customer.name}</div>
          <div className="text-xs text-ink-2">Churn probability, next 8 weeks</div>
        </div>
        <div className="tabular text-2xl font-bold text-critical-ink">72%</div>
      </div>
      <ul className="mt-6 space-y-3.5">
        {reasons.map((r) => (
          <li key={r.label}>
            <div className="flex justify-between text-[13px]">
              <span className="text-ink">{r.label}</span>
              <span style={{ color: red }}>increases risk</span>
            </div>
            <div className="mt-1.5 h-1.5 rounded-full bg-surface-2">
              <div className="grow-x h-full rounded-full bg-critical" style={{ width: `${r.w}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </WidgetCard>
  )
}

export function TimelineWidget() {
  const events = [
    { icon: MessageSquareWarning, text: 'Asked about cancellation fees', tone: red },
    { icon: TrendingDown, text: 'Usage down 38% in 4 weeks', tone: red },
    { icon: Sparkles, text: 'Retention offer recommended', tone: 'var(--accent)' },
    { icon: CreditCard, text: 'Paid $67.12 on time', tone: green },
    { icon: UserPlus, text: 'Started Standard plan', tone: green },
  ]
  return (
    <WidgetCard>
      <div className="flex items-center gap-3">
        <img src={customer.photo} alt="" width={52} height={52} className="size-13 rounded-full object-cover" />
        <div className="min-w-0">
          <div className="truncate text-xl font-bold tracking-tight text-ink">{customer.name}</div>
          <div className="text-xs text-ink-2">{customer.plan} · month-to-month · West</div>
        </div>
      </div>
      <div className="tabular mt-3 grid grid-cols-2 gap-3 border-b border-hairline pb-4">
        <div><div className="text-xs text-ink-2">MRR</div><div className="text-lg font-semibold text-accent">$67.12</div></div>
        <div><div className="text-xs text-ink-2">Value at risk</div><div className="text-lg font-semibold text-accent">$580</div></div>
      </div>
      <ul className="mt-4 space-y-3">
        {events.map(({ icon: Icon, text, tone }) => (
          <li key={text} className="flex items-center gap-3 text-[13px] text-ink-2">
            <span className="grid size-6 shrink-0 place-items-center rounded-full" style={{ background: `color-mix(in srgb, ${tone} 14%, transparent)`, color: tone }}>
              <Icon className="size-3.5" aria-hidden />
            </span>
            {text}
          </li>
        ))}
      </ul>
    </WidgetCard>
  )
}

/* ---------- Acting on it ---------- */

export function ProfitWidget() {
  const curve = Array.from({ length: 30 }, (_, i) => 100 * (1 - Math.exp(-i / 7)))
  const [dotX, dotY] = points(curve, 300, 140, 8)[3] // 333 of 3,185 candidates targeted
  return (
    <WidgetCard>
      <Centered title="Expected campaign profit" value="$32,905" tone="good" />
      <svg viewBox="0 0 300 140" className="mt-6 w-full" role="img" aria-label="Expected profit rises with customers targeted, then levels off">
        {[0, 1, 2, 3].map((r) => <line key={r} x1="0" x2="300" y1={8 + r * 41} y2={8 + r * 41} stroke="var(--hairline)" />)}
        <path d={linePath(curve, 300, 140, 8)} pathLength={1} className="draw-path" fill="none" stroke="var(--accent)" strokeWidth="2.5" />
        <circle cx={dotX} cy={dotY} r="5" fill="var(--accent)" stroke="var(--surface)" strokeWidth="2" className="fade-in-late" />
      </svg>
      <div className="tabular mt-4 flex justify-between text-[13px] text-ink-2">
        <span><b className="text-ink">333</b> targeted</span>
        <span>cost <b className="text-ink">$4,995</b></span>
        <span>ROI <b className="text-good-ink">659%</b></span>
      </div>
    </WidgetCard>
  )
}

export function DriftWidget() {
  const regions = [
    { r: 'North', psi: 0.04 },
    { r: 'South', psi: 0.06 },
    { r: 'East', psi: 0.08 },
    { r: 'West', psi: 0.27 },
  ]
  return (
    <WidgetCard>
      <Centered title="Drift by region (PSI)" value="1 alert" tone="critical" />
      <ul className="mt-7 space-y-4">
        {regions.map(({ r, psi }) => {
          const bad = psi >= 0.2
          return (
            <li key={r} className="tabular grid grid-cols-[52px_1fr_40px] items-center gap-3 text-[13px]">
              <span className="text-ink-2">{r}</span>
              <span className="h-2.5 rounded-full bg-surface-2">
                <span className="grow-x block h-full rounded-full" style={{ width: `${(psi / 0.3) * 100}%`, background: bad ? 'var(--critical)' : 'var(--good)' }} />
              </span>
              <span className="text-right" style={{ color: bad ? red : 'var(--ink-2)' }}>{psi.toFixed(2)}</span>
            </li>
          )
        })}
      </ul>
      <p className="mt-6 text-center text-xs text-muted">A local shock in the West, hidden in the global numbers.</p>
    </WidgetCard>
  )
}
