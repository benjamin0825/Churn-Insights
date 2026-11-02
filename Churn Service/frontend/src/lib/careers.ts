// Careers: job postings on the public site and applications reviewed in the admin panel.

export type Workplace = 'remote' | 'hybrid' | 'onsite'
export type EmploymentType = 'full_time' | 'part_time' | 'contract' | 'internship'
export type PostingStatus = 'draft' | 'open' | 'closed'
export type ApplicationStatus = 'new' | 'reviewing' | 'interview' | 'offer' | 'hired' | 'rejected'

export interface PostingFields {
  title: string
  department: string
  location: string
  workplace: Workplace
  employment_type: EmploymentType
  salary_range: string
  summary: string
  description: string
  responsibilities: string[]
  requirements: string[]
  nice_to_have: string[]
  benefits: string[]
  status: PostingStatus
}

export interface Posting extends PostingFields {
  id: number
  slug: string
  created_at: string
  updated_at: string
  published_at: string | null
}

export interface AdminPosting extends Posting {
  applications: number
  new_applications: number
}

export interface Application {
  id: number
  posting_id: number
  posting_title: string
  name: string
  email: string
  phone: string
  location: string
  linkedin_url: string
  portfolio_url: string
  cover_letter: string
  has_resume: boolean
  resume_filename: string
  status: ApplicationStatus
  notes: string
  created_at: string
}

export const WORKPLACE: Record<Workplace, string> = { remote: 'Remote', hybrid: 'Hybrid', onsite: 'On-site' }
export const EMPLOYMENT: Record<EmploymentType, string> = {
  full_time: 'Full-time', part_time: 'Part-time', contract: 'Contract', internship: 'Internship',
}
export const APPLICATION_STATUS: Record<ApplicationStatus, string> = {
  new: 'New', reviewing: 'Reviewing', interview: 'Interview', offer: 'Offer', hired: 'Hired', rejected: 'Rejected',
}

/** Blank lines separate paragraphs in a posting's description. */
export const paragraphs = (text: string) => text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean)

/** "Berlin · Hybrid", or just "Remote" when the location already says it. */
export function where(p: Pick<PostingFields, 'location' | 'workplace'>): string {
  const label = WORKPLACE[p.workplace]
  return p.location.toLowerCase().includes(label.toLowerCase()) ? p.location : [p.location, label].filter(Boolean).join(' · ')
}
