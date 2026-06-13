import { describe, it, expect, beforeEach, vi } from 'vitest';

function mockMatchMedia(prefersDark) {
  window.matchMedia = vi.fn().mockImplementation(query => ({
    matches: prefersDark,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe('useTheme', () => {
  beforeEach(() => {
    // Composable holds module-level singleton state — reset between cases.
    vi.resetModules();
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('defaults to OS dark when no stored preference', async () => {
    mockMatchMedia(true);
    const { useTheme } = await import('@/composables/useTheme');
    const { isDark } = useTheme();
    expect(isDark.value).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('defaults to OS light when no stored preference', async () => {
    mockMatchMedia(false);
    const { useTheme } = await import('@/composables/useTheme');
    const { isDark } = useTheme();
    expect(isDark.value).toBe(false);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('stored preference overrides OS setting', async () => {
    localStorage.setItem('mt-theme', 'dark');
    mockMatchMedia(false);
    const { useTheme } = await import('@/composables/useTheme');
    const { isDark } = useTheme();
    expect(isDark.value).toBe(true);
  });

  it('toggle flips theme, persists, and updates the html class', async () => {
    mockMatchMedia(false);
    const { useTheme } = await import('@/composables/useTheme');
    const { isDark, toggle } = useTheme();

    expect(isDark.value).toBe(false);
    toggle();
    expect(isDark.value).toBe(true);
    expect(localStorage.getItem('mt-theme')).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);

    toggle();
    expect(isDark.value).toBe(false);
    expect(localStorage.getItem('mt-theme')).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('setTheme sets an explicit theme and persists it', async () => {
    mockMatchMedia(true);
    const { useTheme } = await import('@/composables/useTheme');
    const { isDark, setTheme } = useTheme();
    setTheme('light');
    expect(isDark.value).toBe(false);
    expect(localStorage.getItem('mt-theme')).toBe('light');
  });
});
