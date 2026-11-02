import clsx from 'clsx'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmt, formatMetric } from '../lib/format'
import { AXIS, SERIES } from '../lib/tokens'
import type { MetricCardData } from '../lib/types'
import { ChartTooltip } from './charts'

const shortDate = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

/** Up/down pill. Color says good or bad (churn rising is bad); the arrow and sign say direction. */
export function ChangePill({ change, goodWhen }: { change: number | null; goodWhen: 'up' | 'down' }) {
  if (change == null || !Number.isFinite(change)) return <span className="text-sm text-muted">–</span>
  const up = change >= 0
  const good = Math.abs(change) < 0.0005 ? null : up === (goodWhen === 'up')
  const Arrow = up ? ArrowUp : ArrowDown
  return (
    <span className={clsx('inline-flex items-center gap-1.5 text-[15px] font-semibold tabular',
      good === null ? 'text-ink-2' : good ? 'text-good-ink' : 'text-critical-ink')}>
      <span className={clsx('grid size-6 place-items-center rounded-full',
        good === null ? 'bg-surface-2' : good ? 'bg-good-soft' : 'bg-critical-soft')}>
        <Arrow className="size-3.5" strokeWidth={2.6} aria-hidden />
      </span>
      <span>{up ? '' : '−'}{fmt.pct(Math.abs(change), 1)}</span>
      <span className="sr-only">{good === null ? 'unchanged' : good ? 'improvement' : 'worse'}</span>
    </span>
  )
}

export default function MetricCard({ card, periodWeeks }: { card: MetricCardData; periodWeeks: number }) {
  const fromLabel = card.flow ? `vs ${formatMetric(card.from, card.format)} prior ${periodWeeks} wk` : `from ${formatMetric(card.from, card.format)}`
  return (
    <section className="rounded-lg bg-surface px-5 pt-5 pb-3 shadow-card">
      <h3 className="text-[15px] text-ink-2">{card.label}{card.flow && <span className="text-muted"> · {periodWeeks} wk total</span>}</h3>
      <div className="mt-2 flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-2">
          <span className="text-[26px] font-semibold leading-tight tracking-tight text-ink tabular">{formatMetric(card.value, card.format)}</span>
          <span className="truncate text-sm text-muted">{fromLabel}</span>
        </div>
        <ChangePill change={card.change} goodWhen={card.good_when} />
      </div>
      <div className="mt-3 h-[150px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={card.series} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
            <XAxis dataKey="date" tickFormatter={shortDate} minTickGap={28} {...AXIS} />
            <YAxis width={card.format === 'pct' ? 48 : 52} domain={['auto', 'auto']} tickCount={4}
              tickFormatter={(v: number) => formatMetric(v, card.format, true)} {...AXIS} />
            <Tooltip content={<ChartTooltip format={(v) => formatMetric(v, card.format)} title={(l) => `Week of ${shortDate(String(l))}`} />}
              cursor={{ stroke: 'var(--axis)' }} />
            <Line dataKey="value" name={card.label} stroke={SERIES[0]} strokeWidth={2} dot={false} animationDuration={500}
              activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
