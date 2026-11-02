// Thin fetch wrapper: adds the bearer token, parses JSON, turns errors into ApiError.

const TOKEN_KEY = 'churn-service-token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable: the session lasts until reload */
  }
}

export class ApiError extends Error {
  status: number
  details: string[]

  constructor(status: number, message: string, details: string[] = []) {
    super(message)
    this.status = status
    this.details = details
  }
}

function describe(detail: unknown): { message: string; details: string[] } {
  if (typeof detail === 'string') return { message: detail, details: [] }
  if (detail && typeof detail === 'object' && 'errors' in detail && Array.isArray(detail.errors)) {
    return { message: 'The upload has problems', details: detail.errors.map(String) }
  }
  if (Array.isArray(detail)) {
    // FastAPI validation errors
    const details = detail.map((d) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`)
    return { message: 'Please check the highlighted values', details }
  }
  return { message: 'Something went wrong', details: [] }
}

type Body = Record<string, unknown> | FormData | undefined

export async function api<T>(path: string, options: { method?: string; body?: Body; raw?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (options.body instanceof FormData) body = options.body
  else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  const response = await fetch(path, { method: options.method ?? (body ? 'POST' : 'GET'), headers, body })
  if (response.status === 401 && token) {
    setToken(null)
    window.dispatchEvent(new Event('churn-service:logout'))
  }
  if (!response.ok) {
    let parsed: { detail?: unknown } = {}
    try {
      parsed = await response.json()
    } catch {
      /* not JSON */
    }
    const { message, details } = describe(parsed.detail)
    throw new ApiError(response.status, message, details)
  }
  if (options.raw) return (await response.text()) as T
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function form(values: Record<string, string | number | boolean | Blob>): FormData {
  const data = new FormData()
  for (const [key, value] of Object.entries(values)) data.append(key, value instanceof Blob ? value : String(value))
  return data
}

/** Download an authenticated file (CSV export, templates). */
export async function download(path: string, filename: string): Promise<void> {
  const token = getToken()
  const response = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!response.ok) throw new ApiError(response.status, 'Download failed')
  const url = URL.createObjectURL(await response.blob())
  const link = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** Open an authenticated HTML report in a new tab. */
export async function openReport(path: string): Promise<void> {
  const html = await api<string>(path, { raw: true })
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
  window.open(url, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
