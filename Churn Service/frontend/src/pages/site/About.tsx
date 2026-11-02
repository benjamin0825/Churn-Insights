import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowRight, Building2, Calendar, Heart, Mail, MapPin, Quote, Users } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { GithubIcon as Github, LinkedinIcon as Linkedin } from '../../components/BrandIcons'
import Logo from '../../components/Logo'
import { TEAMS, avatarGradient, initials, type CompanyProfile, type TeamMember } from '../../lib/about'
import { api } from '../../lib/api'
import { paragraphs, type Posting } from '../../lib/careers'
import { DARK } from '../../lib/motion'
import Reveal from './Reveal'
import { CountUp, DarkHero, Eyebrow, GradientText } from './ui'

function Avatar({ m, className }: { m: TeamMember; className: string }) {
  return m.photo_url ? (
    <img src={m.photo_url} alt={`${m.name}, ${m.title}`} loading="lazy" className={clsx('object-cover', className)} />
  ) : (
    <div className={clsx('grid place-items-center font-extrabold text-white', className)} style={{ background: avatarGradient(m.name) }} aria-hidden>
      {initials(m.name)}
    </div>
  )
}

function Links({ m, dark }: { m: TeamMember; dark?: boolean }) {
  if (!m.linkedin_url && !m.github_url) return null
  const cls = clsx('grid size-9 place-items-center rounded-lg transition',
    dark ? 'bg-white/10 text-white hover:bg-white/20' : 'bg-surface-2 text-ink-2 hover:bg-accent hover:text-accent-ink')
  return (
    <div className="flex gap-2">
      {m.linkedin_url && <a href={m.linkedin_url} target="_blank" rel="noopener noreferrer" className={cls} aria-label={`${m.name} on LinkedIn`}><Linkedin /></a>}
      {m.github_url && <a href={m.github_url} target="_blank" rel="noopener noreferrer" className={cls} aria-label={`${m.name} on GitHub`}><Github /></a>}
    </div>
  )
}

/** Large card for leadership. */
function LeaderCard({ m }: { m: TeamMember }) {
  return (
    <article className="group relative flex h-full flex-col overflow-hidden rounded-3xl bg-surface ring-1 ring-hairline transition duration-300 hover:-translate-y-1 hover:shadow-[0_30px_70px_-30px_rgb(13_40_90/0.45)] sm:flex-row">
      <div className="relative aspect-square shrink-0 overflow-hidden sm:aspect-auto sm:w-[44%]">
        <Avatar m={m} className="size-full text-[64px] transition duration-700 group-hover:scale-105" />
        <div aria-hidden className="absolute inset-x-0 bottom-0 h-1.5" style={{ background: 'linear-gradient(90deg, #0a6cf0, #00b4ff)' }} />
      </div>
      <div className="flex flex-1 flex-col p-7">
        <span className="w-fit rounded-full bg-accent-soft px-3 py-1 text-[12px] font-bold tracking-wide text-accent uppercase">{m.title}</span>
        <h3 className="mt-4 text-[26px] leading-tight font-extrabold tracking-tight text-ink">{m.name}</h3>
        {m.bio && <p className="mt-3 flex-1 leading-relaxed text-ink-2">{m.bio}</p>}
        <div className="mt-6"><Links m={m} /></div>
      </div>
    </article>
  )
}

/** Compact card for everyone else. */
function MemberCard({ m }: { m: TeamMember }) {
  return (
    <article className="group h-full rounded-2xl bg-surface p-5 ring-1 ring-hairline transition duration-300 hover:-translate-y-1 hover:shadow-[0_24px_60px_-28px_rgb(13_40_90/0.4)]">
      <div className="relative overflow-hidden rounded-xl">
        <Avatar m={m} className="aspect-square w-full text-[44px] transition duration-700 group-hover:scale-105" />
      </div>
      <h3 className="mt-5 text-[18px] font-bold text-ink">{m.name}</h3>
      <p className="text-[14px] font-medium text-accent">{m.title}</p>
      {m.bio && <p className="mt-2 line-clamp-3 text-[14px] leading-relaxed text-ink-2">{m.bio}</p>}
      <div className="mt-4"><Links m={m} /></div>
    </article>
  )
}

export default function About() {
  const query = useQuery({ queryKey: ['about'], queryFn: () => api<{ profile: CompanyProfile; members: TeamMember[] }>('/api/about') })
  const jobs = useQuery({ queryKey: ['careers'], queryFn: () => api<Posting[]>('/api/careers') })
  const profile = query.data?.profile
  const members = query.data?.members ?? []
  const leaders = members.filter((m) => m.team === 'leadership')
  const groups = TEAMS.filter((t) => t.key !== 'leadership').map((t) => ({ ...t, people: members.filter((m) => m.team === t.key) }))
    .filter((g) => g.people.length)
  const openRoles = jobs.data?.length ?? 0

  const facts = [
    profile?.founded && { icon: Calendar, label: 'Founded', value: profile.founded },
    profile?.headquarters && { icon: MapPin, label: 'Headquarters', value: profile.headquarters },
    members.length > 0 && { icon: Users, label: 'Team members', value: <CountUp to={members.length} /> },
    { icon: Building2, label: 'Open roles', value: <CountUp to={openRoles} /> },
  ].filter(Boolean) as { icon: typeof Calendar; label: string; value: ReactNode }[]

  return (
    <div className="bg-surface">
      <DarkHero>
        <div className="mx-auto max-w-[1200px] px-4 pt-16 pb-20 sm:px-6 lg:pt-24 lg:pb-24">
          <div className="pop-in"><Eyebrow icon={Heart} dark>About WSL Technologies</Eyebrow></div>
          {query.isPending ? (
            <div className="mt-8 h-32 max-w-3xl animate-pulse rounded-2xl bg-white/10" />
          ) : (
            <>
              <h1 className="pop-in mt-6 max-w-4xl text-[40px] leading-[1.05] font-extrabold tracking-[-0.045em] sm:text-[64px]" style={{ animationDelay: '80ms' }}>
                <GradientText animated>{profile?.headline || 'About us'}</GradientText>
              </h1>
              {profile?.intro && (
                <p className="pop-in mt-6 max-w-2xl text-[18px] leading-relaxed text-white/65 sm:text-[20px]" style={{ animationDelay: '160ms' }}>{profile.intro}</p>
              )}
            </>
          )}
          <dl className="pop-in mt-12 grid max-w-3xl grid-cols-2 gap-6 border-t border-white/10 pt-8 sm:grid-cols-4" style={{ animationDelay: '240ms' }}>
            {facts.map(({ icon: Icon, label, value }) => (
              <div key={label}>
                <dt className="flex items-center gap-1.5 text-[13px] text-white/55"><Icon className="size-3.5 text-[#7cc0ff]" aria-hidden />{label}</dt>
                <dd className="mt-2 text-[24px] leading-none font-extrabold tracking-tight">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </DarkHero>

      {/* mission */}
      {profile?.mission && (
        <section className="relative overflow-hidden border-b border-hairline py-24">
          <Logo className="pointer-events-none absolute -right-24 top-1/2 h-80 w-[420px] -translate-y-1/2 text-ink opacity-[0.04]" />
          <Reveal className="relative mx-auto max-w-4xl px-4 text-center sm:px-6">
            <Quote className="mx-auto size-10 text-accent" aria-hidden />
            <p className="mt-6 text-[26px] leading-[1.35] font-bold tracking-[-0.02em] text-ink sm:text-[36px]">{profile.mission}</p>
            <p className="mt-6 text-[13px] font-semibold tracking-wider text-muted uppercase">Our mission</p>
          </Reveal>
        </section>
      )}

      {/* story */}
      {profile?.story && (
        <section className="py-24">
          <div className="mx-auto grid max-w-[1200px] gap-12 px-4 sm:px-6 lg:grid-cols-[1fr_1.5fr] lg:gap-20">
            <Reveal>
              <Eyebrow>Our story</Eyebrow>
              <h2 className="mt-4 text-[32px] leading-[1.12] font-extrabold tracking-[-0.03em] text-ink sm:text-[44px]">Why we <GradientText>built this</GradientText></h2>
            </Reveal>
            <Reveal delay={100} className="space-y-5 text-[18px] leading-relaxed text-ink-2">
              {paragraphs(profile.story).map((p) => <p key={p}>{p}</p>)}
            </Reveal>
          </div>
        </section>
      )}

      {/* values */}
      {profile && profile.values.length > 0 && (
        <section className="bg-page py-24">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
            <Reveal className="mx-auto max-w-2xl text-center">
              <Eyebrow>What we value</Eyebrow>
              <h2 className="mt-4 text-[32px] leading-[1.12] font-extrabold tracking-[-0.03em] text-ink sm:text-[44px]">How we <GradientText>work</GradientText></h2>
            </Reveal>
            <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {profile.values.map((v, i) => (
                <Reveal key={v.title} delay={i * 90} className="h-full">
                  <div className="h-full rounded-2xl bg-surface p-7 ring-1 ring-hairline transition hover:-translate-y-1 hover:shadow-[0_20px_50px_-24px_rgb(13_40_90/0.3)]">
                    <span className="text-gradient text-[40px] leading-none font-extrabold">0{i + 1}</span>
                    <h3 className="mt-4 text-[19px] font-bold text-ink">{v.title}</h3>
                    {v.text && <p className="mt-2 leading-relaxed text-ink-2">{v.text}</p>}
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* team */}
      {members.length > 0 && (
        <section id="team" className="scroll-mt-20 py-24">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
            <Reveal className="mx-auto max-w-2xl text-center">
              <Eyebrow icon={Users}>Our team</Eyebrow>
              <h2 className="mt-4 text-[32px] leading-[1.12] font-extrabold tracking-[-0.03em] text-ink sm:text-[44px]">Meet the <GradientText>people</GradientText> behind it</h2>
            </Reveal>
            {leaders.length > 0 && (
              <div className={clsx('mt-14 grid gap-6', leaders.length > 1 && 'lg:grid-cols-2')}>
                {leaders.map((m, i) => <Reveal key={m.id} delay={i * 100} className="h-full"><LeaderCard m={m} /></Reveal>)}
              </div>
            )}
            {groups.map((g) => (
              <div key={g.key} className="mt-16">
                <Reveal className="flex items-center gap-4">
                  <h3 className="text-[22px] font-bold text-ink">{g.heading}</h3>
                  <span className="h-px flex-1 bg-hairline" />
                  <span className="text-[14px] text-muted">{g.people.length} {g.people.length === 1 ? 'person' : 'people'}</span>
                </Reveal>
                <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                  {g.people.map((m, i) => <Reveal key={m.id} delay={(i % 4) * 80} className="h-full"><MemberCard m={m} /></Reveal>)}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* join + contact */}
      <section className="px-4 pb-24 sm:px-6">
        <Reveal className="relative mx-auto max-w-[1200px] overflow-hidden rounded-[32px] px-6 py-16 text-white sm:px-12">
          <div aria-hidden className="absolute inset-0" style={{ background: `radial-gradient(ellipse 80% 120% at 0% 0%, #0a5bd6 0%, ${DARK} 70%)` }} />
          <Logo className="pointer-events-none absolute -right-16 -bottom-16 h-72 w-96 text-white opacity-[0.06]" />
          <div className="relative grid gap-10 lg:grid-cols-[1.4fr_1fr] lg:items-center">
            <div>
              <h2 className="text-[32px] leading-tight font-extrabold tracking-[-0.03em] sm:text-[44px]">Want to build this with us?</h2>
              <p className="mt-4 max-w-xl text-[18px] text-white/70">
                {openRoles > 0 ? `We have ${openRoles} open role${openRoles === 1 ? '' : 's'} right now.` : 'New roles are posted on our Jobs page first.'}
              </p>
              <Link to="/jobs" className="group mt-8 inline-flex items-center gap-2 rounded-lg bg-white px-6 py-3.5 font-semibold text-[#0b0d12] transition hover:bg-white/90">
                See open roles <ArrowRight className="nudge size-4" aria-hidden />
              </Link>
            </div>
            {(profile?.contact_email || profile?.linkedin_url || profile?.github_url) && (
              <div className="rounded-2xl bg-white/[0.06] p-6 ring-1 ring-white/15">
                <h3 className="font-bold">Get in touch</h3>
                <ul className="mt-4 space-y-3 text-[15px]">
                  {profile.contact_email && <li><a href={`mailto:${profile.contact_email}`} className="flex items-center gap-3 text-white/80 hover:text-white"><Mail className="size-4 text-[#7cc0ff]" aria-hidden />{profile.contact_email}</a></li>}
                  {profile.linkedin_url && <li><a href={profile.linkedin_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 text-white/80 hover:text-white"><Linkedin className="size-4 text-[#7cc0ff]" />LinkedIn</a></li>}
                  {profile.github_url && <li><a href={profile.github_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 text-white/80 hover:text-white"><Github className="size-4 text-[#7cc0ff]" />GitHub</a></li>}
                </ul>
              </div>
            )}
          </div>
        </Reveal>
      </section>
    </div>
  )
}
