import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  ArrowLeft, ArrowRight, Check, CheckCircle2, Clock, Copy, Gift, ListChecks, MapPin, Paperclip, Sparkles, Star, Target,
  Wallet, type LucideIcon,
} from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { ErrorBox } from '../../components/ui'
import { api, ApiError } from '../../lib/api'
import { EMPLOYMENT, paragraphs, where, type Posting } from '../../lib/careers'
import { HIRING_STEPS, departmentHue, postedLabel } from '../../lib/careers-ui'
import Reveal from './Reveal'
import { DarkHero } from './ui'

const input = 'w-full rounded-lg border border-hairline bg-surface px-3.5 py-2.5 text-[15px] text-ink placeholder:text-muted transition focus:border-accent focus:ring-4 focus:ring-accent/15 focus:outline-none'

function Section({ icon: Icon, title, items, tone = 'accent' }: { icon: LucideIcon; title: string; items: string[]; tone?: 'accent' | 'good' }) {
  if (!items.length) return null
  return (
    <Reveal>
      <section className="mt-12">
        <h2 className="flex items-center gap-3 text-[22px] font-bold text-ink">
          <span className={clsx('grid size-9 place-items-center rounded-lg', tone === 'good' ? 'bg-good-soft text-good-ink' : 'bg-accent-soft text-accent')}>
            <Icon className="size-[18px]" aria-hidden />
          </span>
          {title}
        </h2>
        <ul className="mt-5 grid gap-3">
          {items.map((item) => (
            <li key={item} className="flex gap-3 rounded-xl bg-page px-4 py-3 text-[16px] leading-relaxed text-ink-2">
              <Check className={clsx('mt-1 size-4 shrink-0', tone === 'good' ? 'text-good-ink' : 'text-accent')} strokeWidth={3} aria-hidden />
              {item}
            </li>
          ))}
        </ul>
      </section>
    </Reveal>
  )
}

function Label({ text, required, children }: { text: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink">{text}{required && <span className="text-critical-ink"> *</span>}</span>
      <div className="mt-1.5">{children}</div>
    </label>
  )
}

function ApplyForm({ posting }: { posting: Posting }) {
  const [fileName, setFileName] = useState('')
  const submit = useMutation({
    mutationFn: (data: FormData) => api<{ ok: boolean }>(`/api/careers/${posting.slug}/apply`, { body: data }),
  })
  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    const resume = data.get('resume')
    if (resume instanceof File && !resume.name) data.delete('resume')
    submit.mutate(data)
  }

  if (submit.isSuccess) {
    return (
      <div className="pop-in rounded-2xl bg-surface p-8 text-center ring-1 ring-hairline">
        <span className="mx-auto grid size-16 place-items-center rounded-full bg-good-soft"><CheckCircle2 className="size-9 text-good-ink" aria-hidden /></span>
        <h2 className="mt-4 text-[22px] font-bold text-ink">Application sent</h2>
        <p className="mt-2 text-ink-2">Thanks for applying for {posting.title}. We read every application and will reply by email.</p>
        <Link to="/jobs" className="mt-6 inline-flex font-semibold text-accent">See other positions</Link>
      </div>
    )
  }
  if (posting.status !== 'open') {
    return (
      <div className="rounded-2xl bg-surface p-7 ring-1 ring-hairline">
        <h2 className="text-lg font-bold text-ink">This position is closed</h2>
        <p className="mt-2 text-ink-2">It's no longer accepting applications.</p>
        <Link to="/jobs" className="mt-4 inline-flex font-semibold text-accent">See open positions</Link>
      </div>
    )
  }
  const tooMany = submit.error instanceof ApiError && submit.error.status === 429
  return (
    <form onSubmit={onSubmit} className="overflow-hidden rounded-2xl bg-surface shadow-[0_24px_60px_-24px_rgb(13_40_90/0.35)] ring-1 ring-hairline">
      <div className="px-6 pt-6 pb-5 text-white" style={{ background: 'linear-gradient(135deg, #0a5bd6, #00a6ff)' }}>
        <h2 className="text-[20px] font-bold">Apply for this role</h2>
        <p className="mt-1 text-[14px] text-white/80">Takes about 3 minutes. Fields marked * are required.</p>
      </div>
      <div className="space-y-4 p-6">
        <Label text="Full name" required><input name="name" required minLength={2} maxLength={200} autoComplete="name" className={input} /></Label>
        <Label text="Email" required><input name="email" type="email" required maxLength={320} autoComplete="email" className={input} /></Label>
        <div className="grid gap-4 sm:grid-cols-2">
          <Label text="Phone"><input name="phone" type="tel" maxLength={50} autoComplete="tel" className={input} /></Label>
          <Label text="Location"><input name="location" maxLength={120} placeholder="City, country" className={input} /></Label>
        </div>
        <Label text="LinkedIn"><input name="linkedin_url" maxLength={500} placeholder="linkedin.com/in/…" className={input} /></Label>
        <Label text="GitHub or portfolio"><input name="portfolio_url" maxLength={500} placeholder="github.com/…" className={input} /></Label>
        <Label text="CV">
          <span className={clsx('relative flex cursor-pointer items-center gap-3 rounded-lg border-2 border-dashed px-3.5 py-4 text-[15px] transition hover:border-accent hover:bg-accent-soft/40',
            fileName ? 'border-accent bg-accent-soft/40 text-ink' : 'border-hairline text-ink-2')}>
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent"><Paperclip className="size-4" aria-hidden /></span>
            <span className="min-w-0">
              <span className="block truncate font-medium">{fileName || 'Attach your CV'}</span>
              <span className="block text-[12px] text-muted">PDF or Word, up to 5 MB</span>
            </span>
            <input name="resume" type="file" accept=".pdf,.doc,.docx" className="sr-only"
              onChange={(e) => setFileName(e.target.files?.[0]?.name ?? '')} />
          </span>
        </Label>
        <Label text="Why this role?"><textarea name="cover_letter" rows={5} maxLength={10000} className={input}
          placeholder="A few lines about you and something you've built that you're proud of." /></Label>
        {/* Honeypot: hidden from people, bots fill it in. */}
        <input name="website" tabIndex={-1} autoComplete="off" aria-hidden className="absolute -left-[9999px] size-px opacity-0" />
        {submit.error && (tooMany
          ? <p className="text-sm text-critical-ink">Too many applications from this connection. Please try again in a few minutes.</p>
          : <ErrorBox error={submit.error} />)}
        <button type="submit" disabled={submit.isPending}
          className="group inline-flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-5 py-3.5 font-semibold text-accent-ink shadow-[0_10px_30px_-10px_rgb(10_108_240/0.7)] transition hover:brightness-110 disabled:opacity-60">
          {submit.isPending ? 'Sending…' : <>Submit application <ArrowRight className="nudge size-4" aria-hidden /></>}
        </button>
        <p className="text-center text-xs text-muted">We only use your details to review your application.</p>
      </div>
    </form>
  )
}

function ShareButton() {
  const [copied, setCopied] = useState(false)
  return (
    <button type="button" onClick={() => void navigator.clipboard?.writeText(window.location.href).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    })}
      className="inline-flex items-center gap-2 rounded-lg bg-white/[0.06] px-5 py-3.5 font-semibold text-white ring-1 ring-white/20 transition hover:bg-white/10">
      {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />} {copied ? 'Link copied' : 'Copy link'}
    </button>
  )
}

function OtherRoles({ current }: { current: string }) {
  const query = useQuery({ queryKey: ['careers'], queryFn: () => api<Posting[]>('/api/careers') })
  const others = (query.data ?? []).filter((p) => p.slug !== current).slice(0, 3)
  if (!others.length) return null
  return (
    <section className="bg-page py-20">
      <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h2 className="text-[28px] font-extrabold tracking-[-0.03em] text-ink sm:text-[34px]">Other open roles</h2>
          <Link to="/jobs#positions" className="group inline-flex items-center gap-1.5 font-semibold text-accent">All positions <ArrowRight className="nudge size-4" aria-hidden /></Link>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {others.map((p, i) => (
            <Reveal key={p.id} delay={i * 90} className="h-full">
              <Link to={`/jobs/${p.slug}`} className="group flex h-full flex-col rounded-2xl bg-surface p-6 ring-1 ring-hairline transition hover:-translate-y-1 hover:shadow-[0_24px_60px_-24px_rgb(13_40_90/0.35)]">
                <span className="text-[12px] font-semibold" style={{ color: departmentHue(p.department) }}>{p.department}</span>
                <span className="mt-2 text-[19px] font-bold text-ink">{p.title}</span>
                <span className="mt-2 text-[14px] text-ink-2">{where(p)} · {EMPLOYMENT[p.employment_type]}</span>
                <span className="mt-auto inline-flex items-center gap-1.5 pt-5 text-[14px] font-semibold text-accent">View role <ArrowRight className="nudge size-4" aria-hidden /></span>
              </Link>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}

export default function JobDetail() {
  const { slug } = useParams()
  const query = useQuery({ queryKey: ['careers', slug], queryFn: () => api<Posting>(`/api/careers/${slug}`), retry: false })

  if (query.isPending) {
    return <DarkHero><div className="mx-auto h-[360px] max-w-[1200px] px-4 sm:px-6"><div className="mt-20 h-12 w-2/3 animate-pulse rounded-xl bg-white/10" /></div></DarkHero>
  }
  if (query.error || !query.data) {
    return (
      <DarkHero>
        <div className="mx-auto max-w-[1200px] px-4 py-28 text-center sm:px-6">
          <h1 className="text-4xl font-extrabold">Position not found</h1>
          <p className="mt-3 text-white/60">It may have been filled or removed.</p>
          <Link to="/jobs" className="mt-8 inline-flex rounded-lg bg-[#0a6cf0] px-6 py-3.5 font-semibold text-white">See open positions</Link>
        </div>
      </DarkHero>
    )
  }
  const p = query.data
  const hue = departmentHue(p.department)
  const open = p.status === 'open'

  return (
    <div className="bg-surface">
      <DarkHero>
        <div className="mx-auto max-w-[1200px] px-4 pt-10 pb-16 sm:px-6 lg:pt-14 lg:pb-20">
          <Link to="/jobs" className="pop-in inline-flex items-center gap-1.5 text-sm text-white/60 transition hover:text-white">
            <ArrowLeft className="size-4" aria-hidden /> All positions
          </Link>
          <div className="pop-in mt-8 flex flex-wrap items-center gap-3" style={{ animationDelay: '60ms' }}>
            <span className="rounded-full px-3 py-1 text-[13px] font-semibold text-white" style={{ background: hue }}>{p.department}</span>
            <span className="text-[13px] text-white/50">{postedLabel(p.published_at)}</span>
            {!open && <span className="rounded-full bg-white/10 px-3 py-1 text-[13px] font-semibold text-white/80">Closed</span>}
          </div>
          <h1 className="pop-in mt-5 max-w-3xl text-[40px] leading-[1.05] font-extrabold tracking-[-0.045em] sm:text-[60px]" style={{ animationDelay: '120ms' }}>
            {p.title}
          </h1>
          {p.summary && <p className="pop-in mt-5 max-w-2xl text-[18px] leading-relaxed text-white/65 sm:text-[20px]" style={{ animationDelay: '180ms' }}>{p.summary}</p>}
          <div className="pop-in mt-7 flex flex-wrap gap-2.5 text-[14px]" style={{ animationDelay: '240ms' }}>
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.07] px-3 py-2 ring-1 ring-white/10"><MapPin className="size-4 text-[#7cc0ff]" aria-hidden />{where(p)}</span>
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.07] px-3 py-2 ring-1 ring-white/10"><Clock className="size-4 text-[#7cc0ff]" aria-hidden />{EMPLOYMENT[p.employment_type]}</span>
            {p.salary_range && <span className="inline-flex items-center gap-1.5 rounded-lg bg-[#3dd68c]/15 px-3 py-2 text-[#7ff0b5] ring-1 ring-[#3dd68c]/30"><Wallet className="size-4" aria-hidden />{p.salary_range}</span>}
          </div>
          <div className="pop-in mt-9 flex flex-wrap gap-3" style={{ animationDelay: '300ms' }}>
            {open && (
              <a href="#apply" className="group inline-flex items-center gap-2 rounded-lg bg-[#0a6cf0] px-6 py-3.5 font-semibold text-white shadow-[0_10px_40px_-8px_rgb(10_108_240/0.8)] transition hover:bg-[#1a78f5]">
                Apply now <ArrowRight className="nudge size-4" aria-hidden />
              </a>
            )}
            <ShareButton />
          </div>
        </div>
      </DarkHero>

      <div className="mx-auto grid max-w-[1200px] gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1fr_420px] lg:py-20">
        <article className="min-w-0">
          {p.description && (
            <Reveal>
              <h2 className="flex items-center gap-3 text-[22px] font-bold text-ink">
                <span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent"><Sparkles className="size-[18px]" aria-hidden /></span>
                About the role
              </h2>
              <div className="mt-5 space-y-4 text-[17px] leading-relaxed text-ink-2">
                {paragraphs(p.description).map((text) => <p key={text} className="whitespace-pre-line">{text}</p>)}
              </div>
            </Reveal>
          )}
          <Section icon={Target} title="What you'll do" items={p.responsibilities} />
          <Section icon={ListChecks} title="What we're looking for" items={p.requirements} />
          <Section icon={Star} title="Nice to have" items={p.nice_to_have} />
          <Section icon={Gift} title="What we offer" items={p.benefits} tone="good" />

          <Reveal>
            <section className="mt-12 rounded-2xl p-7 text-white" style={{ background: '#0b0d12' }}>
              <h2 className="text-[20px] font-bold">How we hire</h2>
              <ol className="mt-5 grid gap-4 sm:grid-cols-2">
                {HIRING_STEPS.map((s, i) => (
                  <li key={s.title} className="flex gap-3">
                    <span className="text-gradient text-[22px] leading-none font-extrabold">0{i + 1}</span>
                    <span>
                      <span className="block font-semibold">{s.title}</span>
                      <span className="block text-[14px] text-white/60">{s.text}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          </Reveal>
        </article>

        <aside id="apply" className="scroll-mt-24 lg:sticky lg:top-24 lg:self-start">
          <ApplyForm posting={p} />
        </aside>
      </div>

      <OtherRoles current={p.slug} />

      {/* phones: keep the apply button in reach */}
      {open && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-hairline bg-surface/95 p-3 backdrop-blur lg:hidden">
          <a href="#apply" className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent py-3 font-semibold text-accent-ink">
            Apply for {p.title} <ArrowRight className="size-4" aria-hidden />
          </a>
        </div>
      )}
      <div className="h-16 lg:hidden" aria-hidden />
    </div>
  )
}
