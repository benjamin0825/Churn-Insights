import { Check } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, type Location } from 'react-router'
import { Brand } from '../components/Logo'
import { Button, ErrorBox, Field, Input } from '../components/ui'
import { useAuth } from '../lib/auth'
import { DARK } from '../lib/motion'

const YEAR = new Date().getFullYear()

export default function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { user, login, register } = useAuth()
  const [values, setValues] = useState({ organization: '', name: '', email: '', password: '' })
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const from = (useLocation().state as { from?: Location } | null)?.from
  if (user) return <Navigate to={from ? from.pathname + from.search : '/app'} replace />

  const set = (key: keyof typeof values) => (e: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [key]: e.target.value }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') await login(values.email, values.password)
      else await register(values)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-full">
      {/* brand panel */}
      <aside className="relative hidden w-[46%] max-w-[680px] flex-col justify-between overflow-hidden p-12 text-white lg:flex" style={{ background: DARK }}>
        <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage: 'linear-gradient(rgb(255 255 255 / 0.06) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.06) 1px, transparent 1px)',
            backgroundSize: '64px 64px',
            maskImage: 'radial-gradient(ellipse 80% 70% at 30% 40%, black 30%, transparent 80%)',
          }} />
        <div aria-hidden className="glow-drift-slow pointer-events-none absolute -top-32 -left-32 h-[480px] w-[480px] rounded-full bg-[#0088ff] opacity-30 blur-[130px]" />
        <Link to="/" className="relative text-white" aria-label="WSL Technologies home"><Brand markClass="h-8 w-12" /></Link>
        <div className="relative">
          <h2 className="pop-in text-[40px] leading-[1.1] font-extrabold tracking-[-0.04em]">
            {mode === 'login' ? <>Welcome back.<br /><span className="text-gradient text-gradient-animated">Let's keep your customers.</span></>
              : <>Know who will cancel<br /><span className="text-gradient text-gradient-animated">before they do.</span></>}
          </h2>
          <ul className="pop-in mt-8 space-y-3.5 text-[16px] text-white/75" style={{ animationDelay: '120ms' }}>
            {['8-week churn forecast for every customer', 'The reasons behind every prediction', 'Retention offers ranked by expected profit'].map((t) => (
              <li key={t} className="flex items-center gap-3">
                <span className="grid size-6 place-items-center rounded-full bg-[#0a6cf0]"><Check className="size-3.5" strokeWidth={3} aria-hidden /></span>{t}
              </li>
            ))}
          </ul>
          <div className="pop-in mt-10 max-w-sm" style={{ animationDelay: '240ms' }}>
            <div className="animate-float rounded-2xl bg-white p-5 text-[#2d3047] shadow-[0_24px_60px_-12px_rgb(0_0_0/0.5)]">
              <div className="text-[12px] font-semibold text-[#5f6485]">Revenue at risk · next 8 weeks</div>
              <div className="tabular mt-1 text-[28px] font-extrabold tracking-tight">$445,607</div>
              <div className="mt-3 flex h-1.5 overflow-hidden rounded-full" aria-hidden>
                <span className="w-[16%] bg-[#e5484d]" /><span className="w-[24%] bg-[#f5a524]" /><span className="flex-1 bg-[#12b76a]" />
              </div>
              <div className="mt-2 text-[12px] text-[#5f6485]">Example from the demo workspace</div>
            </div>
          </div>
        </div>
        <p className="relative text-[13px] text-white/45">© {YEAR} WSL Technologies</p>
      </aside>

      {/* form */}
      <main className="flex flex-1 items-center justify-center px-4 py-12 sm:px-8">
      <div className="pop-in w-full max-w-[400px]">
        <Link to="/" className="mb-10 flex text-ink lg:hidden" aria-label="WSL Technologies home">
          <Brand markClass="h-9 w-14" subtitle="Churn Insights" />
        </Link>
        <form onSubmit={submit} className="space-y-5">
          <div>
            <h1 className="text-[30px] font-extrabold tracking-[-0.03em] text-ink">{mode === 'login' ? 'Sign in' : 'Create your workspace'}</h1>
            <p className="mt-2 text-[15px] text-ink-2">
              {mode === 'login' ? 'Sign in to your Churn Insights workspace.' : 'Free to start. You will be the owner of a new workspace.'}
            </p>
          </div>
          {mode === 'register' && (
            <>
              <Field label="Company name">
                <Input required minLength={2} value={values.organization} onChange={set('organization')} autoComplete="organization" />
              </Field>
              <Field label="Your name">
                <Input required value={values.name} onChange={set('name')} autoComplete="name" />
              </Field>
            </>
          )}
          <Field label="Email">
            <Input required type="email" value={values.email} onChange={set('email')} autoComplete="email" />
          </Field>
          <Field label="Password" hint={mode === 'register' ? 'At least 8 characters' : undefined}>
            <Input required type="password" minLength={mode === 'register' ? 8 : undefined} value={values.password}
              onChange={set('password')} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
          </Field>
          {error != null && <ErrorBox error={error} />}
          <Button type="submit" loading={busy} className="w-full shadow-[0_10px_30px_-10px_rgb(10_108_240/0.7)]">
            {mode === 'login' ? 'Sign in' : 'Create workspace'}
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-ink-2">
          {mode === 'login' ? (
            <>New here? <Link to="/register" className="font-semibold text-accent">Create a workspace</Link></>
          ) : (
            <>Already have an account? <Link to="/login" className="font-semibold text-accent">Sign in</Link></>
          )}
        </p>
        <p className="mt-10 text-center text-[13px]"><Link to="/" className="text-muted hover:text-ink">← Back to the website</Link></p>
      </div>
      </main>
    </div>
  )
}
