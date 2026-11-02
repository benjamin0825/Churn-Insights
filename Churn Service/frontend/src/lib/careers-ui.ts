// Presentation helpers for the careers pages.

const DEPARTMENT_HUES = ['#0a6cf0', '#7c5cf0', '#12b76a', '#f07c22', '#d6409f', '#1597a8']

/** A stable color per department name. */
export function departmentHue(department: string): string {
  let hash = 0
  for (const ch of department.toLowerCase()) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return DEPARTMENT_HUES[hash % DEPARTMENT_HUES.length]
}

/** "Posted today", "Posted 3 days ago", "Posted 2 weeks ago". */
export function postedLabel(iso: string | null): string {
  if (!iso) return 'New'
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  if (days <= 0) return 'Posted today'
  if (days === 1) return 'Posted yesterday'
  if (days < 14) return `Posted ${days} days ago`
  if (days < 60) return `Posted ${Math.floor(days / 7)} weeks ago`
  return `Posted ${new Date(iso).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}`
}

// The stack the team works with, shown on the careers pages.
export const TECH_STACK = ['Python', 'FastAPI', 'pandas', 'scikit-learn', 'LightGBM', 'XGBoost', 'PyTorch', 'SHAP', 'SQLAlchemy',
  'React', 'TypeScript', 'Tailwind CSS', 'TanStack Query', 'Recharts']

export const HIRING_STEPS = [
  { title: 'Apply', text: 'Send your details and CV. We read every application.' },
  { title: 'Intro call', text: 'A short conversation about you, the role and how we work.' },
  { title: 'Technical interview', text: 'A practical discussion about real problems from our product.' },
  { title: 'Offer', text: 'We meet the team, agree on details and welcome you aboard.' },
]
