import clsx from 'clsx'
import { CircleDollarSign, HeartHandshake, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { reducedMotion } from '../../lib/motion'
import { LIVE_ALERTS, type AlertTone } from '../../lib/sample-customers'

const TONE: Record<AlertTone, { icon: typeof ShieldAlert; badge: string; label: string }> = {
  risk: { icon: ShieldAlert, badge: 'bg-[#fdeaea] text-[#cf2f37]', label: 'At risk' },
  offer: { icon: CircleDollarSign, badge: 'bg-[#eceffe] text-[#0a6cf0]', label: 'Offer' },
  saved: { icon: HeartHandshake, badge: 'bg-[#e3f7ec] text-[#0b8f50]', label: 'Kept' },
}

/** A small "live" feed of churn alerts that cycles through sample customers. */
export default function LiveAlerts({ interval = 2800, visible = 3 }: { interval?: number; visible?: number }) {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (reducedMotion()) return
    const id = window.setInterval(() => setTick((t) => t + 1), interval)
    return () => window.clearInterval(id)
  }, [interval])
  const items = Array.from({ length: visible }, (_, i) => {
    const index = (((tick - i) % LIVE_ALERTS.length) + LIVE_ALERTS.length) % LIVE_ALERTS.length
    return { ...LIVE_ALERTS[index], key: tick - i }
  })

  return (
    <div className="w-72 rounded-2xl bg-white p-3 text-left text-[#2d3047]">
      <div className="flex items-center justify-between px-1 pb-2">
        <span className="flex items-center gap-2 text-[12px] font-semibold text-[#5f6485]">
          <span className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-[#e5484d] opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-[#e5484d]" />
          </span>
          Live churn alerts
        </span>
        <span className="text-[11px] text-[#9095b2]">just now</span>
      </div>
      <ul className="space-y-1.5" aria-live="off">
        {items.map(({ key, customer, tone, title, detail }, i) => {
          const t = TONE[tone]
          const Icon = t.icon
          return (
            <li key={key} className={clsx('flex items-center gap-3 rounded-xl p-2', i === 0 ? 'feed-in bg-[#f5f7fb]' : 'opacity-80')}>
              <img src={customer.photo} alt="" width={40} height={40} className="size-10 shrink-0 rounded-full object-cover" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold">{customer.name}</span>
                <span className="block truncate text-[11px] text-[#5f6485]">{detail}</span>
              </span>
              <span className={clsx('flex shrink-0 items-center gap-1 rounded-full px-2 py-1 text-[11px] font-bold', t.badge)} title={title}>
                <Icon className="size-3" aria-hidden />{tone === 'risk' ? title.split(' ')[0] : t.label}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
