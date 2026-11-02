const THEME_KEY = 'churn-service-theme'
export type Theme = 'system' | 'light' | 'dark'

export function applyTheme(theme: Theme): void {
  if (theme === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', theme)
}

export function storedTheme(): Theme {
  try {
    return (localStorage.getItem(THEME_KEY) as Theme | null) ?? 'system'
  } catch {
    return 'system'
  }
}

export function saveTheme(theme: Theme): void {
  applyTheme(theme)
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    /* not persisted */
  }
}
