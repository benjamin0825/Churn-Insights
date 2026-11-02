import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowDown, ArrowUp, Camera, ExternalLink, Plus, Trash2, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { Button, Card, ErrorBox, Field, Input, Notice, Select, Spinner } from '../../components/ui'
import { TEAMS, avatarGradient, initials, type CompanyProfile, type CompanyValue, type Team, type TeamMember } from '../../lib/about'
import { api, form } from '../../lib/api'
import { AdminHeader, Dialog, Pill } from './shared'

const textarea = 'w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none'

/* ------------------------------------------------------------- company */

function CompanyForm({ initial }: { initial: CompanyProfile }) {
  const queryClient = useQueryClient()
  const [p, setP] = useState(initial)
  const set = <K extends keyof CompanyProfile>(key: K, value: CompanyProfile[K]) => setP({ ...p, [key]: value })
  const setValue = (i: number, patch: Partial<CompanyValue>) => set('values', p.values.map((v, j) => (j === i ? { ...v, ...patch } : v)))
  const save = useMutation({
    mutationFn: () => api<CompanyProfile>('/api/admin/about/profile', { method: 'PUT', body: { ...p } }),
    onSuccess: (saved) => {
      setP(saved)
      queryClient.setQueryData(['admin', 'about-profile'], saved)
      void queryClient.invalidateQueries({ queryKey: ['about'] })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Card title="Hero">
        <div className="space-y-4">
          <Field label="Headline" hint="The big title at the top of the About page">
            <Input maxLength={160} value={p.headline} onChange={(e) => set('headline', e.target.value)} />
          </Field>
          <Field label="Introduction" hint="One or two sentences under the headline">
            <textarea className={textarea} rows={3} maxLength={600} value={p.intro} onChange={(e) => set('intro', e.target.value)} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Founded" hint="Shown as a fact, e.g. 2024. Leave empty to hide."><Input maxLength={40} value={p.founded} onChange={(e) => set('founded', e.target.value)} /></Field>
            <Field label="Headquarters" hint="e.g. Remote, or a city. Leave empty to hide."><Input maxLength={120} value={p.headquarters} onChange={(e) => set('headquarters', e.target.value)} /></Field>
          </div>
        </div>
      </Card>
      <Card title="Mission and story">
        <div className="space-y-4">
          <Field label="Mission" hint="Shown large, as a quote"><textarea className={textarea} rows={2} maxLength={600} value={p.mission} onChange={(e) => set('mission', e.target.value)} /></Field>
          <Field label="Our story" hint="Leave a blank line between paragraphs"><textarea className={textarea} rows={7} maxLength={8000} value={p.story} onChange={(e) => set('story', e.target.value)} /></Field>
        </div>
      </Card>
      <Card title="Values" action={p.values.length < 8 && (
        <Button type="button" variant="ghost" onClick={() => set('values', [...p.values, { title: '', text: '' }])}><Plus className="size-4" aria-hidden /> Add value</Button>
      )}>
        {p.values.length === 0 && <p className="text-sm text-ink-2">No values yet. The section is hidden until you add one.</p>}
        <ol className="space-y-3">
          {p.values.map((v, i) => (
            <li key={i} className="grid gap-3 rounded-lg bg-surface-2 p-3 sm:grid-cols-[200px_1fr_auto] sm:items-start">
              <Input placeholder="Title" maxLength={80} value={v.title} onChange={(e) => setValue(i, { title: e.target.value })} aria-label={`Value ${i + 1} title`} />
              <Input placeholder="One sentence" maxLength={300} value={v.text} onChange={(e) => setValue(i, { text: e.target.value })} aria-label={`Value ${i + 1} text`} />
              <Button type="button" variant="ghost" aria-label={`Remove value ${i + 1}`} onClick={() => set('values', p.values.filter((_, j) => j !== i))}>
                <Trash2 className="size-4" aria-hidden />
              </Button>
            </li>
          ))}
        </ol>
      </Card>
      <Card title="Contact">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Contact email" hint="Optional, shown publicly"><Input type="email" maxLength={320} value={p.contact_email} onChange={(e) => set('contact_email', e.target.value)} /></Field>
          <Field label="LinkedIn page"><Input maxLength={500} placeholder="linkedin.com/company/…" value={p.linkedin_url} onChange={(e) => set('linkedin_url', e.target.value)} /></Field>
          <Field label="GitHub"><Input maxLength={500} placeholder="github.com/…" value={p.github_url} onChange={(e) => set('github_url', e.target.value)} /></Field>
        </div>
      </Card>
      {save.error && <ErrorBox error={save.error} />}
      {save.isSuccess && <Notice>Saved. The About page is updated.</Notice>}
      <div className="flex justify-end"><Button type="submit" loading={save.isPending}>Save company info</Button></div>
    </form>
  )
}

/* ----------------------------------------------------------------- team */

const EMPTY: Omit<TeamMember, 'id' | 'photo_url' | 'sort_order'> = {
  name: '', title: '', team: 'engineering', bio: '', linkedin_url: '', github_url: '', visible: true,
}

function Avatar({ m, size = 'size-12' }: { m: Pick<TeamMember, 'name' | 'photo_url'>; size?: string }) {
  return m.photo_url
    ? <img src={m.photo_url} alt="" className={clsx(size, 'shrink-0 rounded-full object-cover')} />
    : <span className={clsx(size, 'grid shrink-0 place-items-center rounded-full text-sm font-bold text-white')} style={{ background: avatarGradient(m.name || '?') }}>{initials(m.name)}</span>
}

function MemberForm({ initial, onDone }: { initial: TeamMember | null; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [member, setMember] = useState<TeamMember | null>(initial)
  const [f, setF] = useState(initial ? { ...EMPTY, ...initial } : EMPTY)
  const set = <K extends keyof typeof EMPTY>(key: K, value: (typeof EMPTY)[K]) => setF({ ...f, [key]: value })
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['admin', 'members'] })
    void queryClient.invalidateQueries({ queryKey: ['about'] })
  }
  const save = useMutation({
    mutationFn: () => {
      const body = { name: f.name, title: f.title, team: f.team, bio: f.bio, linkedin_url: f.linkedin_url, github_url: f.github_url, visible: f.visible }
      return member ? api<TeamMember>(`/api/admin/about/members/${member.id}`, { method: 'PUT', body })
        : api<TeamMember>('/api/admin/about/members', { body })
    },
    onSuccess: (saved) => {
      refresh()
      if (member) onDone()
      else setMember(saved) // stay open so a photo can be added
    },
  })
  const upload = useMutation({
    mutationFn: (file: File) => api<TeamMember>(`/api/admin/about/members/${member!.id}/photo`, { body: form({ photo: file }) }),
    onSuccess: (saved) => { setMember(saved); refresh() },
  })
  const removePhoto = useMutation({
    mutationFn: () => api<TeamMember>(`/api/admin/about/members/${member!.id}/photo`, { method: 'DELETE' }),
    onSuccess: (saved) => { setMember(saved); refresh() },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="flex items-center gap-4 rounded-lg bg-surface-2 p-3">
        <Avatar m={{ name: f.name, photo_url: member?.photo_url ?? null }} size="size-16" />
        {member ? (
          <div className="flex flex-wrap gap-2">
            <label className={clsx('inline-flex cursor-pointer items-center gap-2 rounded-lg bg-surface px-3.5 py-2 text-sm font-medium text-ink shadow-card hover:bg-surface-2',
              upload.isPending && 'opacity-50')}>
              <Camera className="size-4" aria-hidden /> {member.photo_url ? 'Change photo' : 'Upload photo'}
              <input type="file" accept=".jpg,.jpeg,.png,.webp" className="sr-only" disabled={upload.isPending}
                onChange={(e) => { const file = e.target.files?.[0]; if (file) upload.mutate(file); e.target.value = '' }} />
            </label>
            {member.photo_url && <Button type="button" variant="ghost" loading={removePhoto.isPending} onClick={() => removePhoto.mutate()}>Remove photo</Button>}
            <span className="w-full text-xs text-muted">JPG, PNG or WebP, up to 3 MB. Square photos look best.</span>
          </div>
        ) : (
          <p className="text-sm text-ink-2">Save the person first, then add a photo.</p>
        )}
      </div>
      {(upload.error || removePhoto.error) && <ErrorBox error={upload.error ?? removePhoto.error} />}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name"><Input required maxLength={120} value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
        <Field label="Job title"><Input required maxLength={120} placeholder="e.g. CEO, CTO, ML Engineer" value={f.title} onChange={(e) => set('title', e.target.value)} /></Field>
        <Field label="Team" hint="Leadership is shown first, in large cards">
          <Select value={f.team} onChange={(e) => set('team', e.target.value as Team)}>
            {TEAMS.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
          </Select>
        </Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm">
          <input type="checkbox" className="size-4 accent-[var(--accent)]" checked={f.visible} onChange={(e) => set('visible', e.target.checked)} />
          Show on the About page
        </label>
      </div>
      <Field label="Short bio" hint="Two or three sentences"><textarea className={textarea} rows={3} maxLength={1000} value={f.bio} onChange={(e) => set('bio', e.target.value)} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="LinkedIn"><Input maxLength={500} placeholder="linkedin.com/in/…" value={f.linkedin_url} onChange={(e) => set('linkedin_url', e.target.value)} /></Field>
        <Field label="GitHub"><Input maxLength={500} placeholder="github.com/…" value={f.github_url} onChange={(e) => set('github_url', e.target.value)} /></Field>
      </div>
      {save.error && <ErrorBox error={save.error} />}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>{member && !initial ? 'Done' : 'Cancel'}</Button>
        <Button type="submit" loading={save.isPending}>{member ? 'Save changes' : 'Add person'}</Button>
      </div>
    </form>
  )
}

function TeamTab() {
  const queryClient = useQueryClient()
  const members = useQuery({ queryKey: ['admin', 'members'], queryFn: () => api<TeamMember[]>('/api/admin/about/members') })
  const [editing, setEditing] = useState<{ member: TeamMember | null } | null>(null)
  const [deleting, setDeleting] = useState<TeamMember | null>(null)
  const refresh = (data?: TeamMember[]) => {
    if (data) queryClient.setQueryData(['admin', 'members'], data)
    void queryClient.invalidateQueries({ queryKey: ['about'] })
  }
  const reorder = useMutation({
    mutationFn: (ids: number[]) => api<TeamMember[]>('/api/admin/about/members/order', { method: 'PUT', body: { ids } }),
    onSuccess: refresh,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api<void>(`/api/admin/about/members/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      setDeleting(null)
      void queryClient.invalidateQueries({ queryKey: ['admin', 'members'] })
      refresh()
    },
  })
  const move = (people: TeamMember[], index: number, by: -1 | 1) => {
    const ids = people.map((m) => m.id)
    ;[ids[index], ids[index + by]] = [ids[index + by], ids[index]]
    reorder.mutate(ids)
  }

  if (members.isPending) return <Spinner />
  if (members.error) return <ErrorBox error={members.error} />
  const all = members.data

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-2">{all.length} {all.length === 1 ? 'person' : 'people'} · {all.filter((m) => m.visible).length} shown on the site</p>
        <Button onClick={() => setEditing({ member: null })}><UserPlus className="size-4" aria-hidden /> Add person</Button>
      </div>
      {all.length === 0 && (
        <div className="rounded-lg bg-surface px-6 py-14 text-center shadow-card">
          <p className="font-semibold text-ink">No team members yet</p>
          <p className="mt-1 text-sm text-ink-2">Add your CEO, CTO and engineers. The team section appears on the About page once someone is added.</p>
        </div>
      )}
      {reorder.error && <div className="mb-4"><ErrorBox error={reorder.error} /></div>}
      <div className="space-y-4">
        {TEAMS.map((t) => {
          const people = all.filter((m) => m.team === t.key)
          if (!people.length) return null
          return (
            <Card key={t.key} title={`${t.label} (${people.length})`}>
              <ul className="-my-2 divide-y divide-hairline">
                {people.map((m, i) => (
                  <li key={m.id} className="flex flex-wrap items-center gap-4 py-3">
                    <Avatar m={m} />
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-ink">{m.name} {!m.visible && <Pill>Hidden</Pill>}</div>
                      <div className="text-sm text-ink-2">{m.title}</div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" aria-label={`Move ${m.name} up`} disabled={i === 0 || reorder.isPending} onClick={() => move(people, i, -1)}><ArrowUp className="size-4" /></Button>
                      <Button variant="ghost" aria-label={`Move ${m.name} down`} disabled={i === people.length - 1 || reorder.isPending} onClick={() => move(people, i, 1)}><ArrowDown className="size-4" /></Button>
                      <Button variant="ghost" onClick={() => setEditing({ member: m })}>Edit</Button>
                      <Button variant="ghost" aria-label={`Remove ${m.name}`} onClick={() => { remove.reset(); setDeleting(m) }}><Trash2 className="size-4" /></Button>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )
        })}
      </div>

      <Dialog open={editing != null} title={editing?.member ? `Edit ${editing.member.name}` : 'Add a person'} onClose={() => setEditing(null)} wide>
        {editing && <MemberForm key={editing.member?.id ?? 'new'} initial={editing.member} onDone={() => setEditing(null)} />}
      </Dialog>
      <Dialog open={deleting != null} title={`Remove ${deleting?.name}?`} onClose={() => setDeleting(null)}>
        <p className="text-sm text-ink-2">They'll be removed from the About page, along with their photo. To keep them for later, untick "Show on the About page" instead.</p>
        {remove.error && <div className="mt-3"><ErrorBox error={remove.error} /></div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setDeleting(null)}>Cancel</Button>
          <Button variant="danger" loading={remove.isPending} onClick={() => deleting && remove.mutate(deleting.id)}>Remove</Button>
        </div>
      </Dialog>
    </>
  )
}

export default function AboutAdmin() {
  const [tab, setTab] = useState<'team' | 'company'>('team')
  const profile = useQuery({ queryKey: ['admin', 'about-profile'], queryFn: () => api<CompanyProfile>('/api/admin/about/profile') })
  return (
    <>
      <AdminHeader title="About page" subtitle="Company information and the team shown on the public About page"
        actions={
          <Link to="/about" target="_blank" className="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium text-ink-2 hover:bg-surface-2 hover:text-ink">
            View About page <ExternalLink className="size-3.5" aria-hidden />
          </Link>
        } />
      <div className="mb-5 flex gap-1 border-b border-hairline" role="tablist">
        {([['team', 'Team'], ['company', 'Company info']] as const).map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
            className={clsx('-mb-px border-b-2 px-4 py-2.5 text-sm font-medium', tab === key ? 'border-accent text-ink' : 'border-transparent text-ink-2 hover:text-ink')}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'team' ? <TeamTab /> : profile.isPending ? <Spinner /> : profile.error ? <ErrorBox error={profile.error} /> : <CompanyForm initial={profile.data} />}
    </>
  )
}
