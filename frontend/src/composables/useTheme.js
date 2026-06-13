import { ref } from 'vue';

// Shared singleton (matches the auth-store pattern): one source of truth for
// the active theme across every component that calls useTheme().
const STORAGE_KEY = 'mt-theme';
const THEME_COLOR = { light: '#1e40af', dark: '#0a0e1a' };

const isDark = ref(false);
let initialized = false;

function systemPrefersDark() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );
}

function apply(dark) {
  isDark.value = dark;
  if (typeof document === 'undefined') return;
  document.documentElement.classList.toggle('dark', dark);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta)
    meta.setAttribute('content', dark ? THEME_COLOR.dark : THEME_COLOR.light);
}

function init() {
  if (initialized || typeof window === 'undefined') return;
  initialized = true;

  const stored = localStorage.getItem(STORAGE_KEY);
  apply(stored ? stored === 'dark' : systemPrefersDark());

  // Follow OS changes only while the user hasn't set an explicit preference.
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', e => {
      if (!localStorage.getItem(STORAGE_KEY)) apply(e.matches);
    });
}

export function useTheme() {
  init();

  function setTheme(theme) {
    localStorage.setItem(STORAGE_KEY, theme);
    apply(theme === 'dark');
  }

  function toggle() {
    setTheme(isDark.value ? 'light' : 'dark');
  }

  return { isDark, toggle, setTheme };
}
