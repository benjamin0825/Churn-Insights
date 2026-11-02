import clsx from 'clsx'
import {
  Activity, ArrowRight, BarChart3, Brain, Check, CircleDollarSign, Database, HeartHandshake, KeyRound, LayoutGrid,
  LifeBuoy, LineChart, Lock, Megaphone, Plus, Receipt, ShieldAlert, ShieldCheck, Sparkles, TrendingDown, Upload, Users,
  type LucideIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import Logo from '../../components/Logo'
import { useAuth } from '../../lib/auth'
import { FAQ_COUNT, FEATURED_FAQ, faqId } from '../../lib/faq'
import { DARK } from '../../lib/motion'
import LiveAlerts from './LiveAlerts'
import Reveal from './Reveal'
import { CountUp, DarkHero, Eyebrow, GradientText, Marquee, Parallax, ScrollProgress, Tilt } from './ui'
import { DriftWidget, ForecastWidget, MrrWidget, ProfitWidget, ReasonsWidget, TimelineWidget } from './widgets'

function useStart() {
  const { user } = useAuth()
  return user ? { to: '/app', label: 'Open dashboard' } : { to: '/register', label: 'Start free' }
}

function SectionTitle({ eyebrow, icon, title, children, center = true }: {
  eyebrow: string; icon?: LucideIcon; title: ReactNode; children?: ReactNode; center?: boolean
}) {
  return (
    <div className={clsx('max-w-2xl', center && 'mx-auto text-center')}>
      <Eyebrow icon={icon}>{eyebrow}</Eyebrow>
      <h2 className="mt-4 text-[32px] leading-[1.12] font-extrabold tracking-[-0.03em] text-ink sm:text-[44px]">{title}</h2>
      {children && <p className="mt-5 text-[18px] leading-relaxed text-ink-2">{children}</p>}
    </div>
  )
}

/** A screenshot in a soft browser frame. All shots are 1440×900 crops. */
function Shot({ src, alt, eager, dark }: { src: string; alt: string; eager?: boolean; dark?: boolean }) {
  return (
    <div className={clsx('overflow-hidden rounded-2xl p-1.5 ring-1',
      dark ? 'bg-white/[0.06] ring-white/15' : 'bg-surface ring-hairline shadow-[0_30px_80px_-30px_rgb(13_40_90/0.35)]')}>
      <div className="flex items-center gap-1.5 px-3 py-2" aria-hidden>
        <span className="size-2.5 rounded-full bg-[#ff5f57]" />
        <span className="size-2.5 rounded-full bg-[#febc2e]" />
        <span className="size-2.5 rounded-full bg-[#28c840]" />
      </div>
      <img src={src} alt={alt} width={1440} height={900} loading={eager ? 'eager' : 'lazy'} className="block h-auto w-full rounded-xl" />
    </div>
  )
}

/* ------------------------------------------------------------------ hero */

function FloatingCard({ className, float = 'animate-float', delay, flush, children }: {
  className: string; float?: string; delay: number; flush?: boolean; children: ReactNode
}) {
  return (
    <div className={clsx('pop-in absolute hidden lg:block', className)} style={{ animationDelay: `${delay}ms` }}>
      <div className={clsx(float, !flush && 'p-4', 'rounded-2xl bg-white text-[#2d3047] shadow-[0_24px_60px_-12px_rgb(0_0_0/0.5)] ring-1 ring-black/5')}>
        {children}
      </div>
    </div>
  )
}

function Hero() {
  const start = useStart()
  return (
    <DarkHero>
      <div className="relative mx-auto max-w-[1200px] px-4 pt-16 text-center sm:px-6 sm:pt-24">
        <Reveal>
          <Link to="/#product" className="pop-in inline-flex items-center gap-2 rounded-full bg-white/[0.07] py-1 pr-3 pl-1 text-[13px] text-white/80 ring-1 ring-white/15 transition hover:bg-white/10">
            <span className="rounded-full bg-[#0a6cf0] px-2 py-0.5 text-[11px] font-bold tracking-wide text-white">NEW</span>
            Churn Insights by WSL Technologies <ArrowRight className="size-3.5" aria-hidden />
          </Link>
          <h1 className="pop-in mx-auto mt-7 max-w-4xl text-[44px] leading-[1.04] font-extrabold tracking-[-0.045em] sm:text-[76px]">
            Know who will cancel<br /><GradientText animated>before they do.</GradientText>
          </h1>
          <p className="pop-in mx-auto mt-7 max-w-2xl text-[18px] leading-relaxed text-white/65 sm:text-[20px]" style={{ animationDelay: '120ms' }}>
            Track your subscription metrics, predict which customers will leave in the next 8 weeks, see exactly why,
            and spend your retention budget where it pays off.
          </p>
          <div className="pop-in mt-10 flex flex-wrap justify-center gap-4" style={{ animationDelay: '240ms' }}>
            <Link to={start.to} className="shine group inline-flex items-center gap-2 rounded-lg bg-[#0a6cf0] px-6 py-3.5 text-[16px] font-semibold text-white shadow-[0_10px_40px_-8px_rgb(10_108_240/0.8)] transition hover:bg-[#1a78f5]">
              {start.label} <ArrowRight className="nudge size-4" aria-hidden />
            </Link>
            <a href="#product" className="inline-flex items-center gap-2 rounded-lg bg-white/[0.06] px-6 py-3.5 text-[16px] font-semibold text-white ring-1 ring-white/20 transition hover:bg-white/10">
              See it in action
            </a>
          </div>
          <ul className="pop-in mt-7 flex flex-wrap justify-center gap-x-6 gap-y-2 text-[14px] text-white/55" style={{ animationDelay: '360ms' }}>
            {['Free plan', 'No credit card', 'Demo data in about a minute'].map((t) => (
              <li key={t} className="flex items-center gap-1.5"><Check className="size-4 text-[#3d9bff]" aria-hidden />{t}</li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={150} className="relative mx-auto mt-16 max-w-[1080px]">
          <div aria-hidden className="absolute inset-x-10 top-10 bottom-0 rounded-[40px] bg-[#0a6cf0] opacity-40 blur-[80px]" />
          <div className="relative">
            <Shot src="/screenshots/overview.webp" alt="Churn Insights overview dashboard with MRR, churn and a churn forecast" eager dark />
          </div>
          <FloatingCard className="top-[22%] -left-14 w-60 text-left" delay={700}>
            <div className="flex items-center gap-2 text-[12px] font-semibold text-[#5f6485]">
              <span className="grid size-6 place-items-center rounded-full bg-[#fdeaea] text-[#cf2f37]"><ShieldAlert className="size-3.5" aria-hidden /></span>
              Revenue at risk · 8 weeks
            </div>
            <div className="tabular mt-2 text-[26px] font-extrabold tracking-tight"><CountUp to={445607} prefix="$" duration={1800} /></div>
            <div className="mt-1 text-[12px] text-[#5f6485]">≈ 527 customers expected to leave</div>
            <div className="mt-3 flex h-1.5 overflow-hidden rounded-full" aria-hidden>
              <span className="w-[16%] bg-[#e5484d]" /><span className="w-[24%] bg-[#f5a524]" /><span className="flex-1 bg-[#12b76a]" />
            </div>
          </FloatingCard>
          <FloatingCard className="-right-14 bottom-[8%]" float="animate-float-slow" delay={950} flush>
            <LiveAlerts />
          </FloatingCard>
          <FloatingCard className="-top-6 right-16" delay={1200}>
            <div className="flex items-center gap-3">
            <span className="grid size-8 place-items-center rounded-full bg-[#e3f7ec] text-[#0b8f50]"><CircleDollarSign className="size-4" aria-hidden /></span>
            <span className="text-left">
              <span className="block text-[11px] font-semibold text-[#5f6485]">Campaign ROI</span>
              <span className="tabular block text-[18px] font-extrabold"><CountUp to={659} suffix="%" duration={1600} /></span>
            </span>
            </div>
          </FloatingCard>
        </Reveal>
      </div>
      <div className="h-20 sm:h-28" />
    </DarkHero>
  )
}

/* -------------------------------------------------------------- sections */

const SOURCES: { icon: LucideIcon; label: string }[] = [
  { icon: Users, label: 'Customers' },
  { icon: Activity, label: 'Weekly usage' },
  { icon: Receipt, label: 'Invoices' },
  { icon: LifeBuoy, label: 'Support tickets' },
  { icon: Database, label: 'Demo data' },
]

// What the platform is built on, shown in the scrolling strip.
const STACK: { icon: LucideIcon; label: string }[] = [
  { icon: Brain, label: 'Calibrated ML ensembles' },
  { icon: Sparkles, label: 'SHAP explanations' },
  { icon: Activity, label: 'Drift monitoring' },
]

const STATS: { to: number; prefix?: string; suffix: string; label: string }[] = [
  { to: 8, suffix: ' weeks', label: 'Forecast horizon for every active customer' },
  { to: 8, suffix: ' reasons', label: 'Explained behind each prediction' },
  { to: 4, suffix: ' CSVs', label: 'Is all the data it needs to start' },
  { to: 1, prefix: '~', suffix: ' min', label: 'From demo data to a full dashboard' },
]

const BENTO: { icon: LucideIcon; hue: string; title: string; text: string; widget: ReactNode; wide?: boolean }[] = [
  { icon: LineChart, hue: '#0a6cf0', title: 'Subscription metrics', text: 'MRR, ARR, churn, ARPU and LTV over any range, with the movements behind every change.', widget: <MrrWidget /> },
  { icon: ShieldAlert, hue: '#e5484d', title: 'Churn forecast', text: 'Expected churners and revenue at risk over the next 8 weeks, split into risk tiers.', widget: <ForecastWidget /> },
  { icon: Sparkles, hue: '#f07c22', title: 'Reasons, not just scores', text: 'The strongest drivers behind every prediction, from usage, billing, support and contract.', widget: <ReasonsWidget /> },
  { icon: LayoutGrid, hue: '#12b76a', title: 'Every customer in context', text: '52 weeks of usage, recent tickets and invoices next to the risk score.', widget: <TimelineWidget /> },
  { icon: Megaphone, hue: '#7c5cf0', title: 'Profit-ranked campaigns', text: 'Offers go where they are worth more than they cost. Export target lists as CSV.', widget: <ProfitWidget /> },
  { icon: Activity, hue: '#d6409f', title: 'Drift monitoring', text: 'PSI and KS tests per feature, on predictions and per region, on every scoring run.', widget: <DriftWidget /> },
]

const STEPS: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Upload, title: 'Upload your data', text: 'Four CSV exports, or one click for realistic demo data.' },
  { icon: Brain, title: 'Train a model', text: 'Features, tuning, calibration and explanations run for you.' },
  { icon: ShieldAlert, title: 'Score every customer', text: 'Risk, revenue at risk and reasons, refreshed on demand.' },
  { icon: CircleDollarSign, title: 'Act on it', text: 'Plan offers that fit your budget and export the targets.' },
]

const TEAMS: { icon: LucideIcon; hue: string; team: string; text: string }[] = [
  { icon: HeartHandshake, hue: '#0a6cf0', team: 'Customer success', text: 'A ranked list of who to call this week, and what to talk about.' },
  { icon: BarChart3, hue: '#12b76a', team: 'Finance', text: 'Revenue at risk and churn trends you can put in the forecast.' },
  { icon: Megaphone, hue: '#f07c22', team: 'Marketing', text: 'Retention campaigns sized by budget, with expected profit and ROI.' },
  { icon: Brain, hue: '#7c5cf0', team: 'Data teams', text: 'Model versions, reports, drift checks and an API you can build on.' },
]

const SECURITY: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Lock, title: 'Isolated workspaces', text: 'Every company is its own workspace. Every query and file is scoped to it.' },
  { icon: KeyRound, title: 'Protected accounts', text: 'Passwords are hashed with bcrypt and sessions use signed, expiring tokens.' },
  { icon: ShieldCheck, title: 'Models you can trust', text: 'A new model replaces the current one only if it performs better, and drift is checked on every run.' },
]

function Spotlight({ id, icon, eyebrow, title, text, points, shot, alt, flip }: {
  id: string; icon: LucideIcon; eyebrow: string; title: ReactNode; text: string; points: string[]; shot: string; alt: string; flip?: boolean
}) {
  return (
    <section id={id} className="scroll-mt-20 overflow-x-clip py-20 sm:py-28">
      <div className="mx-auto grid max-w-[1200px] items-center gap-12 px-4 sm:px-6 lg:grid-cols-2 lg:gap-20">
        <Reveal className={clsx(flip && 'lg:order-2')}>
          <SectionTitle eyebrow={eyebrow} icon={icon} title={title} center={false}>{text}</SectionTitle>
          <ul className="mt-7 space-y-3.5">
            {points.map((p) => (
              <li key={p} className="flex gap-3 text-[16px] text-ink-2">
                <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-accent text-accent-ink"><Check className="size-3" strokeWidth={3} aria-hidden /></span>
                {p}
              </li>
            ))}
          </ul>
        </Reveal>
        <Reveal delay={120} className="relative">
          <div aria-hidden className="absolute -inset-6 rounded-[40px] bg-accent-soft blur-2xl" />
          <Parallax className="relative" strength={36}><Shot src={shot} alt={alt} /></Parallax>
        </Reveal>
      </div>
    </section>
  )
}

export default function Home() {
  const start = useStart()
  return (
    <div className="bg-surface">
      <ScrollProgress />
      <Hero />

      {/* Data sources */}
      <section className="border-b border-hairline py-12">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
          <p className="text-center text-[13px] font-semibold tracking-wider text-muted uppercase">Works from the data you already export · built on modern ML</p>
          <Marquee className="mt-7">
            {[...SOURCES, ...STACK].map(({ icon: Icon, label }) => (
              <span key={label} className="flex items-center gap-2.5 text-[20px] font-bold tracking-tight whitespace-nowrap text-ink-2/70">
                <Icon className="size-5" strokeWidth={2.4} aria-hidden /> {label}
              </span>
            ))}
          </Marquee>
        </div>
      </section>

      {/* Stats */}
      <section className="py-20">
        <Reveal className="mx-auto max-w-[1200px] px-4 sm:px-6">
          <dl className="grid overflow-hidden rounded-2xl border border-hairline sm:grid-cols-2 lg:grid-cols-4">
            {STATS.map((s, i) => (
              <div key={s.label} className={clsx('p-8', i > 0 && 'border-t border-hairline sm:border-t-0', i % 2 === 1 && 'sm:border-l',
                i >= 2 && 'sm:border-t lg:border-t-0', i > 0 && 'lg:border-l')}>
                <dt className="text-[44px] leading-none font-extrabold tracking-[-0.04em]"><GradientText><CountUp to={s.to} prefix={s.prefix} suffix={s.suffix} /></GradientText></dt>
                <dd className="mt-3 text-[15px] text-ink-2">{s.label}</dd>
              </div>
            ))}
          </dl>
        </Reveal>
      </section>

      {/* Platform bento */}
      <section id="product" className="scroll-mt-20 bg-page py-24 sm:py-28">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
          <Reveal>
            <SectionTitle eyebrow="The platform" icon={LayoutGrid} title={<>From metrics to the <GradientText>people behind them</GradientText></>}>
              Start with the numbers your board asks about, then drill down to the customers who move them, and decide what to do.
            </SectionTitle>
          </Reveal>
          <div id="features" className="mt-16 grid scroll-mt-24 gap-5 md:grid-cols-2 lg:grid-cols-3">
            {BENTO.map(({ icon: Icon, hue, title, text, widget }, i) => (
              <Reveal key={title} delay={(i % 3) * 100} className="h-full">
                <Tilt className="rounded-3xl">
                <article className="flex h-full flex-col rounded-3xl bg-surface p-6 ring-1 ring-hairline transition hover:shadow-[0_24px_60px_-24px_rgb(13_40_90/0.3)]">
                  <div className="flex items-center gap-3">
                    <span className="grid size-10 place-items-center rounded-xl" style={{ background: `color-mix(in srgb, ${hue} 14%, var(--surface))`, color: hue }}>
                      <Icon className="size-5" strokeWidth={2.2} aria-hidden />
                    </span>
                    <h3 className="text-[18px] font-bold text-ink">{title}</h3>
                  </div>
                  <p className="mt-3 text-[15px] leading-relaxed text-ink-2">{text}</p>
                  <div className="mt-6 flex-1 [&>div]:bg-page [&>div]:shadow-none">{widget}</div>
                </article>
                </Tilt>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <Spotlight id="why" icon={TrendingDown} eyebrow="Churn reasons" title={<>Learn why your customers <GradientText>cancel</GradientText></>}
        text="Every prediction comes with the factors that pushed it up or down, so your team knows what to say before they pick up the phone."
        points={['The eight strongest reasons per customer, from SHAP explanations', 'Usage, billing and support signals side by side', '52 weeks of usage history, recent tickets and invoices']}
        shot="/screenshots/customer-detail.webp" alt="Customer detail page with churn probability and the reasons behind it" />

      <Spotlight id="campaigns" icon={Megaphone} eyebrow="Retention campaigns" flip title={<>Spend your budget <GradientText>where it pays</GradientText></>}
        text="Tell it what an offer costs and how often it works. It picks the customers worth an offer and shows the expected return as you adjust."
        points={['Targets ranked by expected profit, not just risk', 'Live cost, revenue saved, profit and ROI', 'Save campaigns and export target lists as CSV']}
        shot="/screenshots/campaigns.webp" alt="Campaign planner with offer settings and an expected profit curve" />

      {/* How it works */}
      <section id="how-it-works" className="scroll-mt-20 bg-page py-24 sm:py-28">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
          <Reveal><SectionTitle eyebrow="How it works" icon={Upload} title="Up and running in four steps" /></Reveal>
          <div className="relative mt-16 grid gap-8 md:grid-cols-2 lg:grid-cols-4">
            <Reveal className="absolute top-7 right-[12%] left-[12%] hidden lg:block">
              <div aria-hidden className="h-px border-t-2 border-dashed border-accent/30" />
              <div aria-hidden className="grow-x absolute inset-x-0 -top-px h-[3px] rounded-full [animation-duration:2.4s]"
                style={{ background: 'linear-gradient(90deg, #0a6cf0, #00b4ff)' }} />
            </Reveal>
            {STEPS.map(({ icon: Icon, title, text }, i) => (
              <Reveal key={title} delay={i * 100}>
                <div className="relative text-center">
                  <span className="step-glow relative mx-auto grid size-14 place-items-center rounded-2xl text-white"
                    style={{ background: 'linear-gradient(135deg, #0a6cf0, #00b4ff)', animationDelay: `${i * 1.2}s` }}>
                    <Icon className="size-6" aria-hidden />
                    <span className="absolute -top-2 -right-2 grid size-6 place-items-center rounded-full bg-surface text-[12px] font-bold text-accent ring-2 ring-accent">{i + 1}</span>
                  </span>
                  <h3 className="mt-6 text-[18px] font-bold text-ink">{title}</h3>
                  <p className="mx-auto mt-2 max-w-[240px] text-[15px] leading-relaxed text-ink-2">{text}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <Reveal className="mt-14 text-center">
            <Link to={start.to} className="shine group inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-3.5 font-semibold text-accent-ink shadow-card transition hover:brightness-110">
              Try it with demo data <ArrowRight className="nudge size-4" aria-hidden />
            </Link>
          </Reveal>
        </div>
      </section>

      {/* Teams */}
      <section className="py-24 sm:py-28">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
          <Reveal><SectionTitle eyebrow="Built for every team" icon={Users} title="One source of truth for retention" /></Reveal>
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {TEAMS.map(({ icon: Icon, hue, team, text }, i) => (
              <Reveal key={team} delay={i * 80} className="h-full">
                <div className="group relative h-full overflow-hidden rounded-2xl p-6 ring-1 ring-hairline transition hover:ring-accent/40">
                  <div aria-hidden className="absolute -top-16 -right-16 size-40 rounded-full opacity-0 blur-2xl transition group-hover:opacity-25" style={{ background: hue }} />
                  <span className="relative grid size-11 place-items-center rounded-xl text-white" style={{ background: hue }}><Icon className="size-5" aria-hidden /></span>
                  <h3 className="relative mt-5 text-[18px] font-bold text-ink">{team}</h3>
                  <p className="relative mt-2 text-[15px] leading-relaxed text-ink-2">{text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Security (dark) */}
      <section className="relative overflow-hidden py-24 text-white" style={{ background: DARK }}>
        <div aria-hidden className="pointer-events-none absolute -right-40 -bottom-40 h-[420px] w-[420px] rounded-full bg-[#0088ff] opacity-20 blur-[120px]" />
        <div className="relative mx-auto grid max-w-[1200px] gap-12 px-4 sm:px-6">
          <Reveal className="max-w-2xl">
            <Eyebrow icon={ShieldCheck} dark>Security</Eyebrow>
            <h2 className="mt-4 text-[32px] leading-[1.12] font-extrabold tracking-[-0.03em] sm:text-[44px]">Your data stays <GradientText>yours</GradientText></h2>
            <p className="mt-5 text-[18px] leading-relaxed text-white/60">Built so each company's customer data, models and campaigns stay private to that company.</p>
          </Reveal>
          <div className="grid gap-5 md:grid-cols-3">
            {SECURITY.map(({ icon: Icon, title, text }, i) => (
              <Reveal key={title} delay={i * 100} className="h-full">
                <div className="h-full rounded-2xl bg-white/[0.04] p-7 ring-1 ring-white/10">
                  <Icon className="size-6 text-[#3d9bff]" aria-hidden />
                  <h3 className="mt-4 text-[17px] font-bold">{title}</h3>
                  <p className="mt-2 text-[14px] leading-relaxed text-white/60">{text}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-20 py-24 sm:py-28">
        <div className="mx-auto grid max-w-[1200px] gap-12 px-4 sm:px-6 lg:grid-cols-[1fr_1.6fr] lg:gap-20">
          <Reveal>
            <SectionTitle eyebrow="FAQ" title="Questions, answered" center={false}>
              The questions we hear most. Browse all {FAQ_COUNT} answers about data, predictions, campaigns, security and your account.
            </SectionTitle>
            <Link to="/faq" className="group mt-8 inline-flex items-center gap-2 rounded-lg bg-accent px-5 py-3 font-semibold text-accent-ink shadow-card transition hover:brightness-110">
              See all {FAQ_COUNT} questions <ArrowRight className="nudge size-4" aria-hidden />
            </Link>
          </Reveal>
          <Reveal delay={100}>
            <div className="divide-y divide-hairline rounded-2xl ring-1 ring-hairline">
              {FEATURED_FAQ.map((f) => (
                <details key={f.q} id={`home-${faqId(f.q)}`} className="group px-6">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 text-[17px] font-semibold text-ink [&::-webkit-details-marker]:hidden">
                    {f.q}
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent transition group-open:rotate-45">
                      <Plus className="size-4" strokeWidth={2.6} aria-hidden />
                    </span>
                  </summary>
                  <p className="pb-6 text-[15px] leading-relaxed text-ink-2">{f.a}</p>
                </details>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {/* Closing CTA */}
      <section className="px-4 pb-24 sm:px-6">
        <Reveal className="relative mx-auto max-w-[1200px] overflow-hidden rounded-[32px] px-6 py-20 text-center text-white sm:px-12">
          <div aria-hidden className="absolute inset-0" style={{ background: `radial-gradient(ellipse 80% 90% at 50% 0%, #0a5bd6 0%, ${DARK} 70%)` }} />
          <Logo className="pointer-events-none absolute -right-16 -bottom-16 h-72 w-96 text-white opacity-[0.06]" />
          <div className="relative">
            <h2 className="mx-auto max-w-2xl text-[34px] leading-[1.1] font-extrabold tracking-[-0.035em] sm:text-[52px]">
              Find out who is about to leave
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-[18px] text-white/70">
              Create a workspace, load the demo data and see your first churn forecast in about a minute.
            </p>
            <div className="mt-9 flex flex-wrap justify-center gap-4">
              <Link to={start.to} className="group inline-flex items-center gap-2 rounded-lg bg-white px-6 py-3.5 font-semibold text-[#0b0d12] transition hover:bg-white/90">
                {start.label} <ArrowRight className="nudge size-4" aria-hidden />
              </Link>
              <Link to="/pricing" className="inline-flex items-center rounded-lg px-6 py-3.5 font-semibold text-white ring-1 ring-white/30 transition hover:bg-white/10">
                See pricing
              </Link>
            </div>
          </div>
        </Reveal>
      </section>
    </div>
  )
}
