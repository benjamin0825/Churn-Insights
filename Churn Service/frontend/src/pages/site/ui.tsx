import clsx from 'clsx'
import type { LucideIcon } from 'lucide-react'
import { useEffect, useState, type CSSProperties, type MouseEvent, type ReactNode } from 'react'
import { DARK, reducedMotion, useInView } from '../../lib/motion'

// Building blocks shared by the marketing pages, so every page carries the same WSL look.

export function GradientText({ children, animated }: { children: ReactNode; animated?: boolean }) {
  return <span className={clsx('text-gradient', animated && 'text-gradient-animated')}>{children}</span>
}

export function Eyebrow({ children, icon: Icon, dark }: { children: ReactNode; icon?: LucideIcon; dark?: boolean }) {
  return (
    <span className={clsx('inline-flex items-center gap-2 rounded-full px-3 py-1 text-[13px] font-semibold',
      dark ? 'bg-white/10 text-[#7cc0ff] ring-1 ring-white/10' : 'bg-accent-soft text-accent')}>
      {Icon && <Icon className="size-3.5" aria-hidden />}{children}
    </span>
  )
}

/** Dark section with the brand grid and slowly drifting blue glows. Starts under the fixed header. */
export function DarkHero({ children, className, style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <section className={clsx('relative overflow-hidden pt-[72px] text-white', className)} style={{ background: DARK, ...style }}>
      <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage: 'linear-gradient(rgb(255 255 255 / 0.06) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.06) 1px, transparent 1px)',
          backgroundSize: '64px 64px',
          maskImage: 'radial-gradient(ellipse 70% 60% at 50% 30%, black 30%, transparent 75%)',
        }} />
      <div aria-hidden className="glow-drift pointer-events-none absolute -top-40 left-1/2 h-[560px] w-[900px] -translate-x-1/2 rounded-full bg-[#0088ff] opacity-25 blur-[140px]" />
      <div aria-hidden className="glow-drift-slow pointer-events-none absolute top-[360px] -left-40 h-[380px] w-[380px] rounded-full bg-[#00b4ff] opacity-15 blur-[120px]" />
      <div className="relative">{children}</div>
    </section>
  )
}

/** Counts up from 0 to `to` when it scrolls into view. Prefix/suffix wrap the number ("~", " min"). */
export function CountUp({ to, prefix = '', suffix = '', duration = 1400 }: { to: number; prefix?: string; suffix?: string; duration?: number }) {
  const [ref, inView] = useInView<HTMLSpanElement>()
  const [value, setValue] = useState(0)
  const still = reducedMotion()
  useEffect(() => {
    if (!inView || still) return
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      setValue(Math.round(to * (1 - Math.pow(1 - t, 3))))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    // Background tabs pause animation frames; always land on the final number.
    const done = window.setTimeout(() => setValue(to), duration + 100)
    return () => {
      cancelAnimationFrame(frame)
      window.clearTimeout(done)
    }
  }, [inView, still, to, duration])
  return <span ref={ref} className="tabular">{prefix}{(still ? to : value).toLocaleString()}{suffix}</span>
}

/** An endlessly scrolling row; pauses on hover. Static when reduced motion is on. */
export function Marquee({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx('marquee group relative overflow-hidden', className)}>
      <div className="marquee-track flex w-max gap-12 group-hover:[animation-play-state:paused]">
        <div className="flex shrink-0 items-center gap-12">{children}</div>
        <div className="flex shrink-0 items-center gap-12" aria-hidden>{children}</div>
      </div>
    </div>
  )
}

/** A thin brand-colored bar across the top showing how far down the page you are. */
export function ScrollProgress() {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    let frame = 0
    const update = () => {
      frame = 0
      const max = document.documentElement.scrollHeight - window.innerHeight
      setProgress(max > 0 ? Math.min(1, window.scrollY / max) : 0)
    }
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
    }
  }, [])
  return (
    <div aria-hidden className="pointer-events-none fixed inset-x-0 top-0 z-50 h-[3px]">
      <div className="h-full origin-left" style={{ transform: `scaleX(${progress})`, background: 'linear-gradient(90deg, #0a6cf0, #00c2ff)' }} />
    </div>
  )
}

/** Tilts its content slightly toward the mouse, with a soft light that follows the cursor. */
export function Tilt({ children, className, max = 6 }: { children: ReactNode; className?: string; max?: number }) {
  const [style, setStyle] = useState<CSSProperties>({})
  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    if (reducedMotion()) return
    const r = e.currentTarget.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width
    const y = (e.clientY - r.top) / r.height
    setStyle({
      transform: `perspective(900px) rotateX(${(0.5 - y) * max}deg) rotateY(${(x - 0.5) * max}deg) translateY(-4px)`,
      ['--glow-x' as string]: `${x * 100}%`, ['--glow-y' as string]: `${y * 100}%`,
    })
  }
  return (
    <div className={clsx('tilt h-full', className)} style={style} onMouseMove={onMove} onMouseLeave={() => setStyle({})}>
      {children}
    </div>
  )
}

/** Drifts its content up or down a little as the page scrolls past it. */
export function Parallax({ children, className, strength = 40 }: { children: ReactNode; className?: string; strength?: number }) {
  const [ref, setRef] = useState<HTMLDivElement | null>(null)
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    if (!ref || reducedMotion()) return
    let frame = 0
    const update = () => {
      frame = 0
      const r = ref.getBoundingClientRect()
      const center = (r.top + r.height / 2 - window.innerHeight / 2) / window.innerHeight
      setOffset(Math.max(-1, Math.min(1, center)) * -strength)
    }
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', onScroll)
    }
  }, [ref, strength])
  return <div ref={setRef} className={className} style={{ transform: `translateY(${offset}px)`, willChange: 'transform' }}>{children}</div>
}
