import type { ReactNode } from 'react'

interface TooltipEntry {
  name?: string | number
  value?: number | string
  color?: string
  payload?: Record<string, unknown>
}

/** Recharts tooltip in the app's tokens. Text uses ink colors; a small swatch carries series identity. */
export function ChartTooltip({ active, payload, label, format, title }: {
  active?: boolean
  payload?: TooltipEntry[]
  label?: string | number
  format?: (value: number, entry: TooltipEntry) => ReactNode
  title?: (label: string | number | undefined, entry: TooltipEntry | undefined) => ReactNode
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium text-ink">{title ? title(label, payload[0]) : label}</div>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 text-ink-2">
          <span className="size-2 rounded-sm" style={{ background: entry.color }} aria-hidden />
          <span>{entry.name}</span>
          <span className="tabular ml-auto pl-4 font-medium text-ink">
            {format && typeof entry.value === 'number' ? format(entry.value, entry) : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}
