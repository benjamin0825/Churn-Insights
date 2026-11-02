import clsx from 'clsx'
import {
  Activity, Brain, ChevronDown, LayoutGrid, Megaphone, Menu, ShieldAlert, Sparkles, X, type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router'
import { useAuth } from '../lib/auth'
import { btnPrimarySmall } from '../lib/site'
import { Brand } from './Logo'

const YEAR = new Date().getFullYear()

const PRODUCT: { to: string; icon: LucideIcon; hue: string; title: string; text: string }[] = [
  { to: '/#product', icon: LayoutGrid, hue: '#0a6cf0', title: 'Subscription Metrics', text: 'MRR, churn, ARPU and LTV' },
  { to: '/#product', icon: ShieldAlert, hue: '#e5484d', title: 'Churn Forecast', text: 'Revenue at risk, 8 weeks ahead' },
  { to: '/#why', icon: Sparkles, hue: '#f07c22', title: 'Churn Reasons', text: 'Why each customer may leave' },
  { to: '/#campaigns', icon: Megaphone, hue: '#d946ef', title: 'Retention Campaigns', text: 'Offers ranked by profit' },
  { to: '/#features', icon: Brain, hue: '#1597a8', title: 'Models', text: 'Train, compare, roll back' },
  { to: '/#features', icon: Activity, hue: '#d6409f', title: 'Monitoring', text: 'Drift by feature and region' },
]

const NAV = [
  { to: '/#how-it-works', label: 'How It Works' },
  { to: '/pricing', label: 'Plans & Pricing' },
  { to: '/jobs', label: 'Jobs' },
  { to: '/about', label: 'About' },
  { to: '/faq', label: 'FAQ' },
]

const FOOTER = [
  { title: 'Features', links: PRODUCT.map((p) => ({ to: p.to, label: p.title })) },
  { title: 'Plans', links: [{ to: '/pricing', label: 'Pricing' }, { to: '/register', label: 'Start Free' }, { to: '/#how-it-works', label: 'How It Works' }] },
  { title: 'Account', links: [{ to: '/login', label: 'Sign In' }, { to: '/register', label: 'Create a Workspace' }] },
  { title: 'Company', links: [{ to: '/about', label: 'About Us' }, { to: '/jobs', label: 'Jobs' }, { to: '/faq', label: 'FAQ' }, { to: '/api/docs', label: 'API Reference', external: true }] },
]

/** Scrolls to the #hash after client-side navigation, or to the top on a new page. */
function useHashScroll() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    if (hash) {
      // Lazy pages render a frame later, so wait for the target to exist.
      const id = window.setTimeout(() => document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' }), 60)
      return () => window.clearTimeout(id)
    }
    window.scrollTo(0, 0)
  }, [pathname, hash])
}

function ProductMenu({ dark }: { dark: boolean }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])
  return (
    <div ref={ref} className="relative" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="true"
        className={clsx('flex items-center gap-1 px-2 py-2 text-[15px] transition', dark ? 'text-white/75 hover:text-white' : 'text-ink-2 hover:text-ink')}>
        Product <ChevronDown className={clsx('size-3.5 transition', open && 'rotate-180')} aria-hidden />
      </button>
      {open && (
        <div className="absolute top-full left-1/2 z-50 w-[560px] -translate-x-1/2 pt-2">
          <ul className="grid grid-cols-2 gap-1 rounded-xl bg-surface p-3 shadow-[0_20px_50px_-12px_rgb(45_48_71/0.25)] ring-1 ring-hairline">
            {PRODUCT.map(({ to, icon: Icon, hue, title, text }) => (
              <li key={title}>
                <Link to={to} onClick={() => setOpen(false)} className="flex items-start gap-3 rounded-lg p-3 hover:bg-surface-2">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full" style={{ background: `color-mix(in srgb, ${hue} 14%, var(--surface))`, color: hue }}>
                    <Icon className="size-4" strokeWidth={2.4} aria-hidden />
                  </span>
                  <span>
                    <span className="block text-[15px] font-medium text-ink">{title}</span>
                    <span className="block text-[13px] text-ink-2">{text}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/** True once the page has scrolled past the top few pixels. */
function useScrolled(offset = 12) {
  const [scrolled, setScrolled] = useState(() => typeof window !== 'undefined' && window.scrollY > offset)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > offset)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [offset])
  return scrolled
}

export default function SiteLayout() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const scrolled = useScrolled()
  useHashScroll()
  // These pages start with a dark hero; the header sits on it transparently until you scroll.
  const darkHero = pathname === '/' || pathname === '/pricing' || pathname === '/about' || pathname === '/faq' || pathname.startsWith('/jobs')
  // On those pages the header stays dark: clear at the top, dark glass once you scroll.
  const dark = darkHero
  const link = dark ? 'text-white/75 hover:text-white' : 'text-ink-2 hover:text-ink'

  const account = user ? (
    <Link to="/app" className={btnPrimarySmall}>Open Dashboard</Link>
  ) : (
    <>
      <Link to="/login" className={clsx('px-2 py-2 text-[15px] transition', link)}>Sign In</Link>
      <Link to="/register" className={btnPrimarySmall}>Get Started</Link>
    </>
  )

  return (
    <div className="flex min-h-full flex-col bg-surface">
      <header className={clsx('fixed inset-x-0 top-0 z-40 border-b transition-[background-color,border-color,box-shadow] duration-300',
        !dark ? 'border-hairline bg-surface/90 backdrop-blur-md'
          : scrolled || open ? 'border-white/10 bg-[#0b0d12]/95 shadow-[0_10px_30px_-12px_rgb(0_0_0/0.6)] backdrop-blur-xl'
            : 'border-transparent bg-transparent')}>
        <div className="mx-auto flex h-[72px] max-w-[1200px] items-center gap-10 px-4 sm:px-6">
          <Link to="/" className={clsx('shrink-0', dark ? 'text-white' : 'text-ink')} aria-label="WSL Technologies home">
            <Brand markClass="h-7 w-11" />
          </Link>
          <nav className="hidden flex-1 items-center justify-center gap-2 lg:flex" aria-label="Site">
            <ProductMenu dark={dark} />
            {NAV.map((n) => (
              <Link key={n.to} to={n.to} className={clsx('px-2 py-2 text-[15px] transition', link)}>{n.label}</Link>
            ))}
          </nav>
          <div className="ml-auto hidden items-center gap-4 lg:flex">{account}</div>
          <button onClick={() => setOpen(!open)} className={clsx('ml-auto lg:hidden', dark ? 'text-white' : 'text-ink-2')}
            aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open}>
            {open ? <X className="size-6" /> : <Menu className="size-6" />}
          </button>
        </div>
        {open && (
          <div className="absolute inset-x-0 top-full max-h-[calc(100vh-72px)] overflow-y-auto border-t border-hairline bg-surface px-4 pb-6 shadow-[0_20px_40px_-20px_rgb(45_48_71/0.3)] lg:hidden">
            <p className="pt-4 text-xs font-semibold tracking-wider text-muted uppercase">Product</p>
            <ul className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
              {PRODUCT.map(({ to, icon: Icon, hue, title }) => (
                <li key={title}>
                  <Link to={to} onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-lg py-2">
                    <Icon className="size-4" style={{ color: hue }} aria-hidden />
                    <span className="text-ink">{title}</span>
                  </Link>
                </li>
              ))}
            </ul>
            <nav className="mt-3 flex flex-col border-t border-hairline pt-3" aria-label="Site">
              {NAV.map((n) => (
                <Link key={n.to} to={n.to} onClick={() => setOpen(false)} className="py-2.5 font-medium text-ink">{n.label}</Link>
              ))}
            </nav>
            <div className="mt-3 flex items-center gap-4 border-t border-hairline pt-4" onClick={() => setOpen(false)}>{account}</div>
          </div>
        )}
      </header>

      <main className={clsx('flex-1', !darkHero && 'pt-[72px]')}>
        <Outlet />
      </main>

      <footer className="bg-[#0b0d12] text-white">
        <div className="mx-auto grid max-w-[1200px] gap-12 px-4 pt-20 pb-14 sm:px-6 lg:grid-cols-[1.2fr_3fr]">
          <div>
            <Link to="/" className="inline-block text-white" aria-label="WSL Technologies home"><Brand markClass="h-8 w-12" /></Link>
            <p className="mt-5 max-w-xs text-[15px] leading-relaxed text-white/60">
              WSL Technologies builds Churn Insights: churn prediction and retention planning for subscription businesses.
            </p>
            <Link to="/register" className="mt-6 inline-flex items-center rounded-md bg-white px-4 py-2.5 text-sm font-semibold text-[#0b0d12] transition hover:bg-white/90">
              Start free
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-10 md:grid-cols-4">
            {FOOTER.map((group) => (
              <div key={group.title}>
                <h3 className="text-[12px] font-semibold tracking-wider text-[#4aa8ff] uppercase">{group.title}</h3>
                <ul className="mt-5 space-y-3">
                  {group.links.map((l) => (
                    <li key={l.label}>
                      {'external' in l
                        ? <a href={l.to} className="text-[14px] text-white/70 transition hover:text-white">{l.label}</a>
                        : <Link to={l.to} className="text-[14px] text-white/70 transition hover:text-white">{l.label}</Link>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="border-t border-white/10">
          <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-4 py-6 text-[13px] text-white/50 sm:px-6">
            <p>© {YEAR} WSL Technologies. All rights reserved.</p>
            <p>Churn Insights · Churn prediction for subscription businesses</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
