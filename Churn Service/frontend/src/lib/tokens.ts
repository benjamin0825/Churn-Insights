import type { RiskTier } from './types'

/** Categorical series in fixed order; colors follow the entity, never its rank. */
export const SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)']
export const AXIS = { stroke: 'var(--axis)', tickLine: false, axisLine: false } as const

/** Reserved status colors; always paired with an icon and a text label in the UI. */
export const TIER_COLOR: Record<RiskTier, string> = { high: 'var(--critical)', medium: 'var(--warning)', low: 'var(--good)' }
export const DRIFT_COLOR = { stable: 'var(--good)', warning: 'var(--warning)', alert: 'var(--critical)' } as const
