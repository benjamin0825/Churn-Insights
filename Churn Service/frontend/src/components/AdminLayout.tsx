import clsx from 'clsx'
import { ArrowLeft, Briefcase, Building2, CreditCard, Info, LayoutGrid, ListChecks, LogOut, Shield, Users, type LucideIcon } from 'lucide-react'
import { Link, NavLink, Outlet } from 'react-router'
import { useAuth } from '../lib/auth'
import Logo from './Logo'

const NAV: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: '/admin', label: 'Overview', icon: LayoutGrid, end: true },
  { to: '/admin/workspaces', label: 'Workspaces', icon: Building2 },
  { to: '/admin/users', label: 'Users', icon: Users },
  { to: '/admin/jobs', label: 'Background jobs', icon: ListChecks },
  { to: '/admin/plans', label: 'Plans', icon: CreditCard },
  { to: '/admin/hiring', label: 'Hiring', icon: Briefcase },
  { to: '/admin/about', label: 'About page', icon: Info },
]

function NavItem({ to, label, icon: Icon, end }: (typeof NAV)[number]) {
  return (
    <NavLink to={to} end={end}
      className={({ isActive }) => clsx('flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
        isActive ? 'bg-accent text-accent-ink' : 'text-ink-2 hover:bg-surface-2 hover:text-ink')}>
      <Icon className="size-4" aria-hidden /> {label}
    </NavLink>
  )
}

export default function AdminLayout() {
  const { user, logout } = useAuth()
  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      <aside className="shrink-0 bg-surface shadow-card lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-60 lg:flex-col">
        <div className="flex items-center gap-2.5 px-5 py-4 lg:py-6">
          <Logo className="h-7 w-10 text-ink" />
          <div className="leading-tight">
            <div className="font-semibold text-ink">WSL Technologies</div>
            <div className="flex items-center gap-1 text-xs font-semibold text-critical-ink"><Shield className="size-3" aria-hidden /> Admin</div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-1 lg:flex-col lg:overflow-visible" aria-label="Admin">
          {NAV.map((item) => <NavItem key={item.to} {...item} />)}
        </nav>
        <div className="hidden border-t border-hairline p-3 lg:block">
          <Link to="/app" className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink">
            <ArrowLeft className="size-4" aria-hidden /> Back to app
          </Link>
          <button type="button" onClick={logout} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink">
            <LogOut className="size-4" aria-hidden /> Sign out
          </button>
          <p className="truncate px-3 pt-2 text-xs text-muted" title={user?.email}>{user?.email}</p>
        </div>
      </aside>
      <main className="mx-auto w-full max-w-[1320px] min-w-0 flex-1 px-4 py-8 sm:px-6 lg:px-10 lg:py-10">
        <Outlet />
        <div className="mt-10 flex gap-4 border-t border-hairline pt-4 text-sm lg:hidden">
          <Link to="/app" className="text-ink-2">← Back to app</Link>
          <button type="button" onClick={logout} className="text-ink-2">Sign out</button>
        </div>
      </main>
    </div>
  )
}
