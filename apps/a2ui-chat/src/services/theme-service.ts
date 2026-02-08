/**
 * Theme Service
 *
 * Manages dark/light theme. Persists to localStorage.
 * Respects system preference on first visit.
 */

export type Theme = 'dark' | 'light';

const STORAGE_KEY = 'a2ui_theme';

/** Apply theme to the document root. */
function apply(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

/** Read saved preference, fall back to system preference. */
export function getTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY) as Theme | null;
  if (saved === 'dark' || saved === 'light') return saved;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

/** Set and persist theme. */
export function setTheme(theme: Theme) {
  localStorage.setItem(STORAGE_KEY, theme);
  apply(theme);
}

/** Toggle between dark and light. Returns the new theme. */
export function toggleTheme(): Theme {
  const next = getTheme() === 'dark' ? 'light' : 'dark';
  setTheme(next);
  return next;
}

/** Initialize on app load. */
export function initTheme() {
  apply(getTheme());
}
