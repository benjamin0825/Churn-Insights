import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Check, CreditCard, Plus, Rocket, Sprout, TrendingUp, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { btn } from '../../lib/site'
import Reveal from './Reveal'
import { DarkHero, Eyebrow, GradientText } from './ui'

// Plans come from /api/plans and are managed in the admin panel (Admin → Plans).
const ANNUAL_DISCOUNT = 0.2
const ICONS: LucideIcon[] = [Sprout, TrendingUp, Rocket]

interface PublicPlan {
  key: string; name: string; monthly_price: number; blurb: string; limits: string[]; features: string[]; popular: boolean
}

const FAQ = [
  { q: 'Is there a free plan?', a: 'Yes. The Starter plan is free, and you can load demo data to try every screen before uploading your own.' },
  { q: 'Is there a discount for annual billing?', a: `Yes. Paying yearly saves ${ANNUAL_DISCOUNT * 100}% compared with paying month to month.` },
  { q: 'What counts as a customer?', a: 'An active subscriber in your most recent customers upload. Churned customers are kept for training but not counted.' },
  { q: 'Can I change plans later?', a: 'Yes, you can move between plans at any time. Your data, models and campaigns stay where they are.' },
  { q: 'Do I need a data team to use it?', a: 'No. Upload four CSV exports using the templates and the model is trained, calibrated and explained for you.' },
]

export default function Pricing() {
  const { user } = useAuth()
  const [annual, setAnnual] = useState(true)
  const plans = useQuery({ queryKey: ['plans'], queryFn: () => api<PublicPlan[]>('/api/plans'), staleTime: 60_000 })
  const startTo = user ? '/app' : '/register'
  return (
    <div className="bg-surface">
      <DarkHero>
        <div className="mx-auto max-w-[1180px] px-4 pt-16 pb-44 text-center sm:px-6 sm:pt-24">
          <div className="pop-in"><Eyebrow icon={CreditCard} dark>Plans &amp; pricing</Eyebrow></div>
          <h1 className="pop-in mx-auto mt-6 max-w-3xl text-[38px] leading-[1.08] font-extrabold tracking-[-0.04em] sm:text-[56px]" style={{ animationDelay: '80ms' }}>
            Simple pricing for every <GradientText animated>stage of growth</GradientText>
          </h1>
          <p className="pop-in mx-auto mt-5 max-w-xl text-[18px] text-white/65" style={{ animationDelay: '160ms' }}>
            Start free with demo data. Upgrade when retention campaigns become part of how you work.
          </p>
          <div className="pop-in mt-8 inline-flex items-center gap-3 rounded-full bg-white/[0.07] p-1.5 pr-4 ring-1 ring-white/15" style={{ animationDelay: '240ms' }}>
            <button type="button" role="switch" aria-checked={annual} aria-label="Annual billing" onClick={() => setAnnual(!annual)}
              className={clsx('relative h-7 w-12 rounded-full transition', annual ? 'bg-[#0a6cf0]' : 'bg-white/20')}>
              <span className={clsx('absolute top-1 size-5 rounded-full bg-white shadow transition-all', annual ? 'left-6' : 'left-1')} />
            </button>
            <span className="text-[14px] font-medium text-white/85">
              Pay yearly <span className="ml-1 rounded-full bg-[#3dd68c]/15 px-2 py-0.5 text-[12px] font-bold text-[#7ff0b5]">Save {ANNUAL_DISCOUNT * 100}%</span>
            </span>
          </div>
        </div>
      </DarkHero>
      <section className="relative mx-auto -mt-32 max-w-[1180px] px-4 pb-20 sm:px-6">

        {plans.isPending && <div className="grid gap-5 lg:grid-cols-3">{[0, 1, 2].map((i) => <div key={i} className="h-[560px] animate-pulse rounded-3xl bg-surface ring-1 ring-hairline" />)}</div>}
        {plans.error && <p className="mt-14 text-center text-ink-2">Plans couldn't be loaded. Please refresh the page.</p>}
        <div className={clsx('grid gap-5', (plans.data?.length ?? 3) >= 3 ? 'lg:grid-cols-3' : 'lg:grid-cols-2')}>
          {plans.data?.map((p, i, all) => {
            const Icon = ICONS[Math.min(i, ICONS.length - 1)]
            const price = annual ? Math.round(p.monthly_price * (1 - ANNUAL_DISCOUNT)) : p.monthly_price
            return (
              <Reveal key={p.name} delay={i * 100} className="h-full">
              <div
                className={clsx('relative flex h-full flex-col rounded-3xl bg-surface p-7 transition duration-300 hover:-translate-y-1',
                  p.popular ? 'shadow-[0_30px_80px_-30px_rgb(10_108_240/0.55)] ring-2 ring-accent' : 'shadow-[0_24px_60px_-30px_rgb(13_40_90/0.35)] ring-1 ring-hairline')}>
                {p.popular && (
                  <span className="absolute -top-3.5 left-7 rounded-full px-3 py-1 text-[12px] font-bold tracking-wider text-white"
                    style={{ background: 'linear-gradient(90deg, #0a6cf0, #00b4ff)' }}>MOST POPULAR</span>
                )}
                <span className="grid size-14 place-items-center rounded-2xl bg-accent-soft text-accent">
                  <Icon className="size-7" aria-hidden />
                </span>
                <h2 className="mt-6 text-[26px] font-bold tracking-tight text-ink">{p.name}</h2>
                <p className="mt-2 min-h-[60px] text-[14px] leading-relaxed text-ink-2">{p.blurb}</p>
                <p className="mt-6 text-[12px] tracking-wider text-ink-2 uppercase">Starts at:</p>
                <p className="mt-1 flex items-baseline gap-1 text-ink">
                  <span className="text-[38px]">$</span>
                  <span className="tabular text-[52px] leading-none font-extrabold tracking-tight">{price}</span>
                  <span className="text-[18px] text-ink-2">/ mo</span>
                </p>
                <Link to={startTo} className={clsx(btn, 'mt-6 w-full bg-accent text-accent-ink hover:brightness-110')}>
                  {p.monthly_price === 0 ? 'Start free' : 'Start now'}
                </Link>
                <div className="mt-8 min-h-10 text-[14px] text-ink-2">
                  {p.limits.map((l, j) => (
                    <p key={l} className={j === 0 ? 'text-ink underline decoration-dotted underline-offset-4' : 'mt-1'}>{l}</p>
                  ))}
                </div>
                <p className="mt-8 text-[14px] font-medium text-ink-2">{i === 0 ? `Included in ${p.name}:` : `All in ${all[i - 1].name}, plus:`}</p>
                <ul className="mt-5 space-y-3.5">
                  {p.features.map((f) => (
                    <li key={f} className="flex gap-3 text-[14px] text-ink-2">
                      <Check className="size-4 shrink-0 translate-y-0.5 text-good-ink" aria-hidden />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
              </Reveal>
            )
          })}
        </div>

        <Reveal className="relative mt-12 overflow-hidden rounded-3xl px-7 py-9 text-white sm:flex sm:items-center sm:justify-between sm:gap-8">
          <div aria-hidden className="absolute inset-0" style={{ background: 'radial-gradient(ellipse 80% 140% at 0% 0%, #0a5bd6 0%, #0b0d12 70%)' }} />
          <div className="relative">
            <h2 className="text-[24px] font-bold tracking-tight">Try every feature first</h2>
            <p className="mt-2 max-w-md text-[14px] font-medium leading-relaxed">
              Create a free workspace, load the demo data and explore the dashboard, forecasts and campaign planner before
              you choose a plan.
            </p>
          </div>
          <Link to={startTo} className={clsx(btn, 'relative mt-6 w-full bg-white font-semibold text-[#0b0d12] hover:bg-white/90 sm:mt-0 sm:w-[280px]')}>
            Load demo data
          </Link>
        </Reveal>
      </section>

      <section className="mx-auto max-w-[1220px] px-4 pt-10 pb-28 sm:px-6">
        <h2 className="text-[34px] font-extrabold tracking-[-0.03em] text-ink sm:text-[40px]">Frequently asked questions</h2>
        <div className="mt-10 border-t border-hairline">
          {FAQ.map((f) => (
            <details key={f.q} className="group border-b border-hairline">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 text-[18px] font-medium text-ink [&::-webkit-details-marker]:hidden">
                {f.q}
                <Plus className="size-5 shrink-0 text-accent transition group-open:rotate-45" strokeWidth={3} aria-hidden />
              </summary>
              <p className="max-w-3xl pb-6 text-[16px] leading-relaxed text-ink-2">{f.a}</p>
            </details>
          ))}
        </div>
        <p className="mt-6 text-[16px] text-ink">
          More questions? <Link to="/faq" className="font-semibold text-accent">Read the full FAQ.</Link>
        </p>
      </section>
    </div>
  )
}
