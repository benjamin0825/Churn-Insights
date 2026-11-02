import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import {
  Activity, Brain, Database, LayoutGrid, Loader2, LogOut, Megaphone, Menu, Settings, Shield, ShieldAlert, Users, X,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { useAuth } from '../lib/auth'
import { useDataStatus } from '../lib/hooks'
import Logo from './Logo'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** each section keeps its own hue; the soft tile tint is mixed from it per theme */
  hue: string
  end?: boolean
}

const NAV: NavItem[] = [
  { to: '/app', label: 'Overview', icon: LayoutGrid, hue: '#0a6cf0', end: true },
  { to: '/app/risk', label: 'Churn risk', icon: ShieldAlert, hue: '#e5484d' },
  { to: '/app/customers', label: 'Customers', icon: Users, hue: '#d6409f' },
  { to: '/app/campaigns', label: 'Campaigns', icon: Megaphone, hue: '#f07c22' },
  { to: '/app/models', label: 'Models', icon: Brain, hue: '#7c5cf0' },
  { to: '/app/monitoring', label: 'Monitoring', icon: Activity, hue: '#1597a8' },
  { to: '/app/data', label: 'Data', icon: Database, hue: '#c99400' },
  { to: '/app/settings', label: 'Settings', icon: Settings, hue: '#6b7190' },
]

const ADMIN_ITEM: NavItem = { to: '/admin', label: 'Admin', icon: Shield, hue: '#2d3047' }

const JOB_LABEL: Record<string, string> = {
  demo: 'Loading demo data and training',
  train: 'Training a new model',
  score: 'Scoring customers',
  monitor: 'Checking drift',
}

function ActiveJobBanner() {
  const { data } = useDataStatus()
  const queryClient = useQueryClient()
  const wasRunning = useRef(false)
  const job = data?.active_job
  useEffect(() => {
    if (job) wasRunning.current = true
    else if (wasRunning.current) {
      wasRunning.current = false
      void queryClient.invalidateQueries() // job finished: refresh every page's data
    }
  }, [job, queryClient])
  if (!job) return null
  return (
    <div className="mx-4 mt-4 flex items-center gap-3 rounded-lg bg-accent px-5 py-3 text-sm text-accent-ink shadow-card sm:mx-6 lg:mx-10" role="status">
      <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden />
      <span className="font-semibold">{JOB_LABEL[job.kind] ?? job.kind}</span>
      <span className="truncate opacity-85">{job.message}</span>
    </div>
  )
}

function RailLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const Icon = item.icon
  return (
    <NavLink to={item.to} end={item.end} onClick={onNavigate}
      className="group flex flex-col items-center gap-1 rounded-lg px-1 py-1.5 text-center focus-visible:outline-offset-0">
      {({ isActive }) => (
        <>
          <span className={clsx('grid size-10 place-items-center rounded-lg transition', !isActive && 'group-hover:scale-105')}
            style={{ background: isActive ? item.hue : `color-mix(in srgb, ${item.hue} 14%, var(--surface))`, color: isActive ? '#fff' : item.hue }}>
            <Icon className="size-[19px]" strokeWidth={2.2} aria-hidden />
          </span>
          <span className={clsx('text-[11px] leading-tight', isActive ? 'font-semibold text-ink' : 'text-ink-2')}>{item.label}</span>
        </>
      )}
    </NavLink>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const initials = (user?.name ?? '?').split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase()

  const rail = (onNavigate?: () => void) => (
    <div className="flex h-full flex-col items-center py-6">
      <NavLink to="/app" onClick={onNavigate} aria-label="Churn Insights home" className="text-ink"><Logo className="h-8 w-12" /></NavLink>
      <nav className="mt-9 flex w-full flex-1 flex-col gap-2.5 px-2" aria-label="Main">
        {NAV.map((item) => <RailLink key={item.to} item={item} onNavigate={onNavigate} />)}
        {user?.is_admin && <RailLink item={ADMIN_ITEM} onNavigate={onNavigate} />}
      </nav>
      <div className="flex flex-col items-center gap-2">
        <span title={`${user?.name} · ${user?.organization.name}`}
          className="grid size-10 place-items-center rounded-full bg-surface-2 text-xs font-semibold text-ink-2">{initials}</span>
        <button onClick={logout} className="flex flex-col items-center gap-0.5 text-[11px] text-ink-2 hover:text-ink" aria-label="Sign out">
          <LogOut className="size-4" aria-hidden /> Sign out
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 hidden h-screen w-[88px] shrink-0 overflow-y-auto bg-surface shadow-card lg:block">{rail()}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-[96px] overflow-y-auto bg-surface">{rail(() => setOpen(false))}</aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-3 bg-surface px-4 py-3 shadow-card lg:hidden">
          <button onClick={() => setOpen(!open)} aria-label={open ? 'Close menu' : 'Open menu'} className="text-ink-2">
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
          <Logo className="h-6 w-9 text-ink" />
          <span className="font-semibold">Churn Insights</span>
        </div>
        <ActiveJobBanner />
        <main className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-8 sm:px-6 lg:px-10 lg:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
