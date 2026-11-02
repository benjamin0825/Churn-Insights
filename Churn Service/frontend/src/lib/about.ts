// About page: company profile and team members (managed in Admin → About page).

export type Team = 'leadership' | 'ai' | 'backend' | 'frontend' | 'engineering' | 'product' | 'people' | 'finance' | 'operations'

// Display order on the About page (matches TEAM_ORDER on the server).
export const TEAMS: { key: Team; label: string; heading: string }[] = [
  { key: 'leadership', label: 'Leadership', heading: 'Leadership' },
  { key: 'ai', label: 'AI & Machine Learning', heading: 'AI & Machine Learning' },
  { key: 'backend', label: 'Backend Engineering', heading: 'Backend Engineering' },
  { key: 'frontend', label: 'Frontend Engineering', heading: 'Frontend Engineering' },
  { key: 'engineering', label: 'Engineering (other)', heading: 'Engineering' },
  { key: 'product', label: 'Product & Design', heading: 'Product & Design' },
  { key: 'people', label: 'People & HR', heading: 'People & HR' },
  { key: 'finance', label: 'Finance', heading: 'Finance' },
  { key: 'operations', label: 'Operations', heading: 'Operations' },
]

export interface CompanyValue { title: string; text: string }

export interface CompanyProfile {
  headline: string
  intro: string
  mission: string
  story: string
  founded: string
  headquarters: string
  contact_email: string
  linkedin_url: string
  github_url: string
  values: CompanyValue[]
  updated_at?: string | null
}

export interface TeamMember {
  id: number
  name: string
  title: string
  team: Team
  bio: string
  linkedin_url: string
  github_url: string
  visible: boolean
  photo_url: string | null
  sort_order: number
}

export const initials = (name: string) =>
  name.trim().split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase() || '?'

const AVATAR_GRADIENTS = [
  ['#0a6cf0', '#00b4ff'], ['#7c5cf0', '#b18cff'], ['#12b76a', '#5fe0a5'], ['#f07c22', '#ffb36b'], ['#d6409f', '#ff8ac9'],
]

/** A stable gradient per person, for avatars without a photo. */
export function avatarGradient(name: string): string {
  let hash = 0
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  const [a, b] = AVATAR_GRADIENTS[hash % AVATAR_GRADIENTS.length]
  return `linear-gradient(135deg, ${a}, ${b})`
}
