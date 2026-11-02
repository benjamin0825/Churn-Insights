import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  ArrowRight, Briefcase, Clock, Code2, GraduationCap, Laptop, LineChart, MapPin, Rocket, Search, Sparkles, Target, Users,
  Wallet, X, type LucideIcon,
} from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { api } from '../../lib/api'
import { EMPLOYMENT, WORKPLACE, where, type EmploymentType, type Posting, type Workplace } from '../../lib/careers'
import { HIRING_STEPS, TECH_STACK, departmentHue, postedLabel } from '../../lib/careers-ui'
import { DARK } from '../../lib/motion'
import Reveal from './Reveal'
import { CountUp, DarkHero, Eyebrow, GradientText, Marquee } from './ui'

const PERKS: { icon: LucideIcon; hue: string; title: string; text: string }[] = [
  { icon: Laptop, hue: '#0a6cf0', title: 'Remote-first', text: 'Work from where you do your best work, with flexible hours.' },
  { icon: Rocket, hue: '#7c5cf0', title: 'Real ownership', text: 'Ship features end to end, from the model to the screen a customer uses.' },
  { icon: Target, hue: '#12b76a', title: 'Measurable impact', text: 'Our product keeps customers. You see the effect of your work in real numbers.' },
  { icon: Code2, hue: '#f07c22', title: 'Modern stack', text: 'Python, FastAPI and gradient boosting on the backend; React and TypeScript up front.' },
  { icon: GraduationCap, hue: '#d6409f', title: 'Learning budget', text: 'Books, courses, conferences and the equipment you need.' },
  { icon: Users, hue: '#1597a8', title: 'Small, senior team', text: 'Clear writing, short meetings and room to think.' },
]

/** An icon that fits the role, for the hero card. */
function roleIcon(title: string): LucideIcon {
  const t = title.toLowerCase()
  if (t.includes('machine') || t.includes('ai ') || t.startsWith('ai') || t.includes('data')) return Sparkles
  if (t.includes('python') || t.includes('backend') || t.includes('full stack')) return Code2
  return LineChart
}

function JobCard({ p }: { p: Posting }) {
  const hue = departmentHue(p.department)
  return (
    <Link to={`/jobs/${p.slug}`}
      className="group relative flex h-full flex-col overflow-hidden rounded-2xl bg-surface p-6 ring-1 ring-hairline transition duration-300 hover:-translate-y-1 hover:shadow-[0_24px_60px_-24px_rgb(13_40_90/0.35)] hover:ring-accent/40">
      <div aria-hidden className="absolute -top-20 -right-20 size-48 rounded-full opacity-0 blur-3xl transition duration-500 group-hover:opacity-20" style={{ background: hue }} />
      <div className="relative flex items-center justify-between gap-3">
        <span className="rounded-full px-2.5 py-1 text-[12px] font-semibold" style={{ background: `color-mix(in srgb, ${hue} 12%, var(--surface))`, color: hue }}>
          {p.department}
        </span>
        <span className="text-[12px] text-muted">{postedLabel(p.published_at)}</span>
      </div>
      <h3 className="relative mt-4 text-[22px] leading-tight font-bold tracking-tight text-ink">{p.title}</h3>
      {p.summary && <p className="relative mt-2 line-clamp-2 text-[15px] leading-relaxed text-ink-2">{p.summary}</p>}
      <div className="relative mt-5 flex flex-wrap gap-2 text-[13px]">
        <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-2 px-2.5 py-1.5 text-ink-2"><MapPin className="size-3.5" aria-hidden />{where(p)}</span>
        <span className="inline-flex items-center gap-1.5 rounded-lg bg-surface-2 px-2.5 py-1.5 text-ink-2"><Clock className="size-3.5" aria-hidden />{EMPLOYMENT[p.employment_type]}</span>
        {p.salary_range && <span className="inline-flex items-center gap-1.5 rounded-lg bg-good-soft px-2.5 py-1.5 font-medium text-good-ink"><Wallet className="size-3.5" aria-hidden />{p.salary_range}</span>}
      </div>
      <div className="relative mt-auto flex items-center justify-end pt-6">
        <span className="inline-flex items-center gap-1.5 text-[15px] font-semibold text-accent">
          View &amp; apply <ArrowRight className="nudge size-4" aria-hidden />
        </span>
      </div>
    </Link>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active}
      className={clsx('rounded-full px-4 py-2 text-[14px] font-semibold transition',
        active ? 'bg-ink text-page' : 'bg-surface text-ink-2 ring-1 ring-hairline hover:text-ink')}>
      {children}
    </button>
  )
}

function Positions({ postings }: { postings: Posting[] }) {
  const [q, setQ] = useState('')
  const [department, setDepartment] = useState('')
  const [workplace, setWorkplace] = useState<Workplace | ''>('')
  const [type, setType] = useState<EmploymentType | ''>('')
  const departments = useMemo(() => [...new Set(postings.map((p) => p.department))].sort(), [postings])
  const needle = q.trim().toLowerCase()
  const shown = postings.filter((p) =>
    (!department || p.department === department) && (!workplace || p.workplace === workplace) && (!type || p.employment_type === type) &&
    (!needle || [p.title, p.summary, p.department, p.location, ...p.requirements].join(' ').toLowerCase().includes(needle)))
  const filtered = Boolean(q || department || workplace || type)
  const clear = () => {
    setQ('')
    setDepartment('')
    setWorkplace('')
    setType('')
  }
  const select = 'rounded-lg bg-surface-2 px-3 py-2.5 text-[14px] text-ink focus:ring-2 focus:ring-accent focus:outline-none'

  return (
    <>
      <div className="mt-10 flex flex-col gap-3 rounded-2xl bg-surface p-3 ring-1 ring-hairline lg:flex-row lg:items-center">
        <label className="relative flex-1">
          <span className="sr-only">Search positions</span>
          <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title, skill or keyword"
            className="w-full rounded-lg bg-surface-2 py-2.5 pr-3 pl-10 text-[15px] text-ink placeholder:text-muted focus:ring-2 focus:ring-accent focus:outline-none" />
        </label>
        <div className="flex flex-wrap gap-3">
          <select value={workplace} onChange={(e) => setWorkplace(e.target.value as Workplace | '')} className={select} aria-label="Workplace">
            <option value="">Any workplace</option>
            {Object.entries(WORKPLACE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={type} onChange={(e) => setType(e.target.value as EmploymentType | '')} className={select} aria-label="Employment type">
            <option value="">Any type</option>
            {Object.entries(EMPLOYMENT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </div>
      {departments.length > 1 && (
        <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label="Team">
          <Chip active={!department} onClick={() => setDepartment('')}>All teams</Chip>
          {departments.map((d) => <Chip key={d} active={department === d} onClick={() => setDepartment(d)}>{d}</Chip>)}
        </div>
      )}
      <div className="mt-6 flex items-center justify-between text-[14px] text-ink-2" aria-live="polite">
        <span><b className="text-ink">{shown.length}</b> of {postings.length} open position{postings.length === 1 ? '' : 's'}</span>
        {filtered && (
          <button type="button" onClick={clear} className="inline-flex items-center gap-1 font-medium text-accent">
            <X className="size-3.5" aria-hidden />Clear filters
          </button>
        )}
      </div>
      {shown.length ? (
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          {shown.map((p, i) => <Reveal key={p.id} delay={(i % 2) * 90} className="h-full"><JobCard p={p} /></Reveal>)}
        </div>
      ) : (
        <div className="mt-5 rounded-2xl bg-surface p-10 text-center ring-1 ring-hairline">
          <p className="font-semibold text-ink">No positions match those filters</p>
          <button type="button" onClick={clear} className="mt-2 font-medium text-accent">Show all positions</button>
        </div>
      )}
    </>
  )
}

export default function Jobs() {
  const query = useQuery({ queryKey: ['careers'], queryFn: () => api<Posting[]>('/api/careers') })
  const postings = query.data ?? []
  const teams = new Set(postings.map((p) => p.department)).size

  return (
    <div className="bg-surface">
      <DarkHero>
        <div className="mx-auto grid max-w-[1200px] items-center gap-14 px-4 pt-16 pb-20 sm:px-6 lg:grid-cols-[1.25fr_1fr] lg:pt-24 lg:pb-28">
          <div>
            <div className="pop-in"><Eyebrow icon={Briefcase} dark>Careers at WSL Technologies</Eyebrow></div>
            <h1 className="pop-in mt-6 text-[42px] leading-[1.05] font-extrabold tracking-[-0.045em] sm:text-[64px]" style={{ animationDelay: '80ms' }}>
              Build what keeps <GradientText animated>customers coming back</GradientText>
            </h1>
            <p className="pop-in mt-6 max-w-xl text-[18px] leading-relaxed text-white/65 sm:text-[20px]" style={{ animationDelay: '160ms' }}>
              We turn machine learning into decisions subscription businesses act on every week. Join a small team that
              ships, and see your work show up in real customer numbers.
            </p>
            <div className="pop-in mt-9 flex flex-wrap gap-4" style={{ animationDelay: '240ms' }}>
              <a href="#positions" className="group inline-flex items-center gap-2 rounded-lg bg-[#0a6cf0] px-6 py-3.5 font-semibold text-white shadow-[0_10px_40px_-8px_rgb(10_108_240/0.8)] transition hover:bg-[#1a78f5]">
                See open roles{postings.length ? ` (${postings.length})` : ''} <ArrowRight className="nudge size-4" aria-hidden />
              </a>
              <a href="#process" className="inline-flex items-center rounded-lg bg-white/[0.06] px-6 py-3.5 font-semibold text-white ring-1 ring-white/20 transition hover:bg-white/10">
                How we hire
              </a>
            </div>
            <dl className="pop-in mt-12 grid max-w-lg grid-cols-3 gap-6 border-t border-white/10 pt-8" style={{ animationDelay: '320ms' }}>
              <div><dt className="text-[32px] leading-none font-extrabold tracking-tight"><CountUp to={postings.length} /></dt><dd className="mt-2 text-[13px] text-white/55">Open roles</dd></div>
              <div><dt className="text-[32px] leading-none font-extrabold tracking-tight"><CountUp to={teams} /></dt><dd className="mt-2 text-[13px] text-white/55">{teams === 1 ? 'Team hiring' : 'Teams hiring'}</dd></div>
              <div><dt className="text-[32px] leading-none font-extrabold tracking-tight">Remote</dt><dd className="mt-2 text-[13px] text-white/55">Friendly by default</dd></div>
            </dl>
          </div>

          {/* live "we're hiring" card */}
          <div className="pop-in relative hidden lg:block" style={{ animationDelay: '400ms' }}>
            <div aria-hidden className="absolute -inset-8 rounded-[40px] bg-[#0a6cf0] opacity-30 blur-[70px]" />
            <div className="animate-float relative rounded-3xl bg-white/[0.06] p-6 ring-1 ring-white/15 backdrop-blur">
              <div className="flex items-center gap-2 text-[13px] font-semibold text-white/80">
                <span className="relative flex size-2.5">
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-[#3dd68c] opacity-75" />
                  <span className="relative inline-flex size-2.5 rounded-full bg-[#3dd68c]" />
                </span>
                We're hiring now
              </div>
              <ul className="mt-5 space-y-3">
                {postings.slice(0, 4).map((p) => {
                  const Icon = roleIcon(p.title)
                  return (
                    <li key={p.id}>
                      <Link to={`/jobs/${p.slug}`} className="group flex items-center gap-3 rounded-2xl bg-white p-3.5 text-[#2d3047] transition hover:-translate-y-0.5">
                        <span className="grid size-10 shrink-0 place-items-center rounded-xl text-white" style={{ background: departmentHue(p.department) }}>
                          <Icon className="size-5" aria-hidden />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-semibold">{p.title}</span>
                          <span className="block truncate text-[12px] text-[#5f6485]">{where(p)} · {EMPLOYMENT[p.employment_type]}</span>
                        </span>
                        <ArrowRight className="nudge size-4 shrink-0 text-[#0a6cf0]" aria-hidden />
                      </Link>
                    </li>
                  )
                })}
                {!postings.length && <li className="rounded-2xl bg-white/5 p-4 text-[14px] text-white/60">New roles are posted here first.</li>}
              </ul>
            </div>
          </div>
        </div>
      </DarkHero>

      {/* stack */}
      <section className="border-b border-hairline py-10">
        <p className="text-center text-[13px] font-semibold tracking-wider text-muted uppercase">What you'll work with</p>
        <Marquee className="mx-auto mt-6 max-w-[1200px]">
          {TECH_STACK.map((t) => (
            <span key={t} className="rounded-full bg-surface-2 px-4 py-2 text-[15px] font-semibold whitespace-nowrap text-ink-2 ring-1 ring-hairline">{t}</span>
          ))}
        </Marquee>
      </section>

      {/* positions */}
      <section id="positions" className="scroll-mt-16 bg-page py-24">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
          <Reveal>
            <Eyebrow icon={Briefcase}>Open positions</Eyebrow>
            <h2 className="mt-4 text-[32px] leading-[1.12] font-extrabold tracking-[-0.03em] text-ink sm:text-[44px]">Find your role</h2>
          </Reveal>
          {query.isPending && (
            <div className="mt-10 grid gap-5 md:grid-cols-2">
              {[0, 1].map((i) => <div key={i} className="h-64 animate-pulse rounded-2xl bg-surface ring-1 ring-hairline" />)}
            </div>
          )}
          {query.error && <p className="mt-10 text-ink-2">Positions couldn't be loaded. Please refresh the page.</p>}
          {query.data && (postings.length ? <Positions postings={postings} /> : (
            <div className="mt-10 rounded-2xl bg-surface p-12 text-center ring-1 ring-hairline">
              <Briefcase className="mx-auto size-9 text-muted" aria-hidden />
              <p className="mt-4 text-lg font-semibold text-ink">No open positions right now</p>
              <p className="mt-1 text-ink-2">Check back soon. New roles are posted here first.</p>
            </div>
          ))}
        </div>
      </section>

      {/* perks */}
      <section className="py-24">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
          <Reveal className="mx-auto max-w-2xl text-center">
            <Eyebrow icon={Sparkles}>Why WSL</Eyebrow>
            <h2 className="mt-4 text-[32px] leading-[1.12] font-extrabold tracking-[-0.03em] text-ink sm:text-[44px]">A place to do your <GradientText>best work</GradientText></h2>
          </Reveal>
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {PERKS.map(({ icon: Icon, hue, title, text }, i) => (
              <Reveal key={title} delay={(i % 3) * 90} className="h-full">
                <div className="group h-full rounded-2xl p-7 ring-1 ring-hairline transition hover:-translate-y-1 hover:shadow-[0_20px_50px_-24px_rgb(13_40_90/0.3)]">
                  <span className="grid size-12 place-items-center rounded-xl text-white transition group-hover:scale-110" style={{ background: hue }}>
                    <Icon className="size-6" aria-hidden />
                  </span>
                  <h3 className="mt-5 text-[19px] font-bold text-ink">{title}</h3>
                  <p className="mt-2 leading-relaxed text-ink-2">{text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* hiring process */}
      <section id="process" className="relative scroll-mt-16 overflow-hidden py-24 text-white" style={{ background: DARK }}>
        <div aria-hidden className="glow-drift pointer-events-none absolute -bottom-40 left-1/2 h-[420px] w-[800px] -translate-x-1/2 rounded-full bg-[#0088ff] opacity-20 blur-[130px]" />
        <div className="relative mx-auto max-w-[1200px] px-4 sm:px-6">
          <Reveal className="max-w-2xl">
            <Eyebrow icon={Clock} dark>How we hire</Eyebrow>
            <h2 className="mt-4 text-[32px] leading-[1.12] font-extrabold tracking-[-0.03em] sm:text-[44px]">Four steps, <GradientText>no surprises</GradientText></h2>
            <p className="mt-4 text-[18px] text-white/60">A clear, respectful process. We keep you updated at every step.</p>
          </Reveal>
          <ol className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {HIRING_STEPS.map((step, i) => (
              <li key={step.title}>
                <Reveal delay={i * 110} className="h-full">
                  <div className="h-full rounded-2xl bg-white/[0.04] p-6 ring-1 ring-white/10 transition hover:bg-white/[0.07]">
                    <span className="text-gradient text-[44px] leading-none font-extrabold">0{i + 1}</span>
                    <h3 className="mt-4 text-[18px] font-bold">{step.title}</h3>
                    <p className="mt-2 text-[14px] leading-relaxed text-white/60">{step.text}</p>
                  </div>
                </Reveal>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* closing */}
      <section className="px-4 py-24 sm:px-6">
        <Reveal className="mx-auto max-w-[1200px] rounded-[32px] bg-accent-soft px-6 py-16 text-center sm:px-12">
          <h2 className="mx-auto max-w-2xl text-[30px] leading-tight font-extrabold tracking-[-0.03em] text-ink sm:text-[40px]">Don't see the perfect role?</h2>
          <p className="mx-auto mt-4 max-w-xl text-[17px] text-ink-2">
            We're always glad to hear from great engineers. Apply to the closest role and tell us what you'd love to work on.
          </p>
          <a href="#positions" className="group mt-8 inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-3.5 font-semibold text-accent-ink shadow-card transition hover:brightness-110">
            Browse open roles <ArrowRight className="nudge size-4" aria-hidden />
          </a>
        </Reveal>
      </section>
    </div>
  )
}
