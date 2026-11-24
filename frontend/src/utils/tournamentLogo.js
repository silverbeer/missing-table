/**
 * Which tournament logo to draw for the current theme (SB-1770).
 *
 * A tournament has a regular `logo_url` and an optional `logo_dark_url`, drawn
 * for dark grounds — a logo with a black wordmark disappears on one. The dark
 * variant is the exception, so dark mode falls back to the regular logo, and a
 * dark logo is never shown in light mode. No logo at all is `null`.
 */
export function tournamentLogoSrc(tournament, dark) {
  if (!tournament) return null;
  return (dark && tournament.logo_dark_url) || tournament.logo_url || null;
}
