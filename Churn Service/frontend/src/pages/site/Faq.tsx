import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  ArrowRight, BarChart3, Briefcase, Check, CreditCard, Database, HelpCircle, Link2, Megaphone, Plus, Rocket, Search, ShieldCheck, X,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router'
import type { CompanyProfile } from '../../lib/about'
import { api } from '../../lib/api'
import { FAQ_COUNT, FAQ_TOPICS, faqId, type FaqItem } from '../../lib/faq'
import Reveal from './Reveal'
import { DarkHero, Eyebrow, GradientText } from './ui'

const TOPIC_ICONS: Record<string, LucideIcon> = {
  'getting-started': Rocket, data: Database, predictions: BarChart3, campaigns: Megaphone, security: ShieldCheck,
  account: CreditCard, careers: Briefcase,
}

function Question({ item, open: initiallyOpen }: { item: FaqItem; open: boolean }) {
  const id = faqId(item.q)
  const [copied, setCopied] = useState(false)
  const copy = () => void navigator.clipboard?.writeText(`${window.location.origin}/faq#${id}`).then(() => {
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  })
  return (
    <details id={id} open={initiallyOpen} className="group scroll-mt-28 rounded-2xl bg-surface ring-1 ring-hairline transition open:shadow-[0_16px_40px_-24px_rgb(13_40_90/0.35)] open:ring-accent/30">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-5 text-[17px] font-semibold text-ink [&::-webkit-details-marker]:hidden">
        {item.q}
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft text-accent transition duration-300 group-open:rotate-45 group-open:bg-accent group-open:text-accent-ink">
          <Plus className="size-4" strokeWidth={2.6} aria-hidden />
        </span>
      </summary>
      <div className="px-6 pb-6">
        <p className="text-[16px] leading-relaxed text-ink-2">{item.a}</p>
        <button type="button" onClick={copy} className="mt-4 inline-flex items-center gap-1.5 text-[13px] font-medium text-muted transition hover:text-accent">
          {copied ? <Check className="size-3.5" aria-hidden /> : <Link2 className="size-3.5" aria-hidden />} {copied ? 'Link copied' : 'Copy link to this answer'}
        </button>
      </div>
    </details>
  )
}

export default function Faq() {
  const { hash } = useLocation()
  const [q, setQ] = useState('')
  const about = useQuery({ queryKey: ['about'], queryFn: () => api<{ profile: CompanyProfile }>('/api/about') })
  const email = about.data?.profile.contact_email
  const target = hash.slice(1)

  // Opening a link to one answer: scroll it into view once the page has rendered.
  useEffect(() => {
    if (!target) return
    const id = window.setTimeout(() => document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150)
    return () => window.clearTimeout(id)
  }, [target])

  const needle = q.trim().toLowerCase()
  const topics = FAQ_TOPICS.map((t) => ({
    ...t, items: needle ? t.items.filter((i) => `${i.q} ${i.a}`.toLowerCase().includes(needle)) : t.items,
  })).filter((t) => t.items.length)
  const matches = topics.reduce((n, t) => n + t.items.length, 0)

  return (
    <div className="bg-surface">
      <DarkHero>
        <div className="mx-auto max-w-[900px] px-4 pt-16 pb-24 text-center sm:px-6 lg:pt-24">
          <div className="pop-in"><Eyebrow icon={HelpCircle} dark>Help center</Eyebrow></div>
          <h1 className="pop-in mt-6 text-[40px] leading-[1.05] font-extrabold tracking-[-0.045em] sm:text-[60px]" style={{ animationDelay: '80ms' }}>
            Frequently asked <GradientText animated>questions</GradientText>
          </h1>
          <p className="pop-in mx-auto mt-5 max-w-xl text-[18px] text-white/65" style={{ animationDelay: '160ms' }}>
            {FAQ_COUNT} answers about Churn Insights: your data, predictions, campaigns, security and your account.
          </p>
          <label className="pop-in relative mx-auto mt-9 block max-w-xl" style={{ animationDelay: '240ms' }}>
            <span className="sr-only">Search the FAQ</span>
            <Search className="pointer-events-none absolute top-1/2 left-4 z-10 size-5 -translate-y-1/2 text-white/60" aria-hidden />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search questions, e.g. data, budget, password"
              className="w-full rounded-xl bg-white/[0.08] py-4 pr-12 pl-12 text-[16px] text-white ring-1 ring-white/15 placeholder:text-white/40 focus:bg-white/[0.12] focus:ring-2 focus:ring-[#3d9bff] focus:outline-none" />
            {q && (
              <button type="button" onClick={() => setQ('')} aria-label="Clear search" className="absolute top-1/2 right-3 grid size-8 -translate-y-1/2 place-items-center rounded-lg text-white/60 hover:bg-white/10 hover:text-white">
                <X className="size-4" />
              </button>
            )}
          </label>
          <div className="pop-in mt-7 flex flex-wrap justify-center gap-2" style={{ animationDelay: '320ms' }}>
            {FAQ_TOPICS.map((t) => {
              const Icon = TOPIC_ICONS[t.id] ?? HelpCircle
              return (
                <a key={t.id} href={`#${t.id}`} onClick={() => setQ('')}
                  className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.06] px-3.5 py-1.5 text-[13px] font-medium text-white/75 ring-1 ring-white/10 transition hover:bg-white/10 hover:text-white">
                  <Icon className="size-3.5 text-[#7cc0ff]" aria-hidden />{t.title}
                </a>
              )
            })}
          </div>
        </div>
      </DarkHero>

      <div className="mx-auto grid max-w-[1200px] gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[240px_1fr] lg:py-20">
        {/* topic list */}
        <nav aria-label="FAQ topics" className="hidden lg:block">
          <div className="sticky top-28">
            <p className="text-[12px] font-semibold tracking-wider text-muted uppercase">Topics</p>
            <ul className="mt-4 space-y-1">
              {FAQ_TOPICS.map((t) => {
                const Icon = TOPIC_ICONS[t.id] ?? HelpCircle
                const count = topics.find((x) => x.id === t.id)?.items.length ?? 0
                return (
                  <li key={t.id}>
                    <a href={`#${t.id}`} className={clsx('flex items-center gap-3 rounded-lg px-3 py-2 text-[14px] font-medium transition hover:bg-surface-2',
                      count ? 'text-ink-2 hover:text-ink' : 'pointer-events-none text-muted/50')}>
                      <Icon className="size-4" aria-hidden /><span className="flex-1">{t.title}</span>
                      <span className="tabular text-[12px] text-muted">{count}</span>
                    </a>
                  </li>
                )
              })}
            </ul>
          </div>
        </nav>

        <div className="min-w-0">
          {needle && (
            <p className="mb-6 text-[15px] text-ink-2" aria-live="polite">
              <b className="text-ink">{matches}</b> answer{matches === 1 ? '' : 's'} for “{q.trim()}”
            </p>
          )}
          {topics.length === 0 && (
            <div className="rounded-2xl bg-page p-10 text-center ring-1 ring-hairline">
              <p className="font-semibold text-ink">No answers match “{q.trim()}”</p>
              <p className="mt-1 text-ink-2">Try a different word, or get in touch below.</p>
              <button type="button" onClick={() => setQ('')} className="mt-3 font-semibold text-accent">Show all questions</button>
            </div>
          )}
          <div className="space-y-14">
            {topics.map((t) => {
              const Icon = TOPIC_ICONS[t.id] ?? HelpCircle
              return (
                <section key={t.id} id={t.id} className="scroll-mt-28">
                  <Reveal className="flex items-center gap-3">
                    <span className="grid size-10 place-items-center rounded-xl text-white" style={{ background: 'linear-gradient(135deg, #0a6cf0, #00b4ff)' }}>
                      <Icon className="size-5" aria-hidden />
                    </span>
                    <h2 className="text-[24px] font-extrabold tracking-tight text-ink">{t.title}</h2>
                  </Reveal>
                  <div className="mt-6 space-y-3">
                    {t.items.map((item) => (
                      <Question key={item.q} item={item} open={Boolean(needle) || faqId(item.q) === target} />
                    ))}
                  </div>
                </section>
              )
            })}
          </div>
        </div>
      </div>

      {/* still have questions */}
      <section className="px-4 pb-24 sm:px-6">
        <Reveal className="relative mx-auto max-w-[1200px] overflow-hidden rounded-[32px] px-6 py-14 text-center text-white sm:px-12">
          <div aria-hidden className="absolute inset-0" style={{ background: 'radial-gradient(ellipse 80% 120% at 50% 0%, #0a5bd6 0%, #0b0d12 70%)' }} />
          <div className="relative">
            <h2 className="text-[30px] leading-tight font-extrabold tracking-[-0.03em] sm:text-[40px]">Still have questions?</h2>
            <p className="mx-auto mt-4 max-w-xl text-[17px] text-white/70">
              The fastest way to understand Churn Insights is to try it with demo data.{email ? ' Or write to us and we’ll get back to you.' : ''}
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <Link to="/register" className="group inline-flex items-center gap-2 rounded-lg bg-white px-6 py-3.5 font-semibold text-[#0b0d12] transition hover:bg-white/90">
                Try it free <ArrowRight className="nudge size-4" aria-hidden />
              </Link>
              {email && (
                <a href={`mailto:${email}`} className="inline-flex items-center rounded-lg px-6 py-3.5 font-semibold text-white ring-1 ring-white/30 transition hover:bg-white/10">
                  Email {email}
                </a>
              )}
            </div>
          </div>
        </Reveal>
      </section>
    </div>
  )
}
