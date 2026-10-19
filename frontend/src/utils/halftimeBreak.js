/**
 * Half-time break countdown + backdated 2nd-half start (SB-1353).
 *
 * Pure helpers, parity with the Android app: the break is a fixed 10
 * minutes from halftime_start. Once it is overdue the admin can start the
 * 2nd half "at the end of the break" instead of "now".
 */

export const BREAK_MINUTES = 10;
const BREAK_MS = BREAK_MINUTES * 60 * 1000;

function toMs(value) {
  if (value === null || value === undefined || value === '') return null;
  const ms =
    value instanceof Date ? value.getTime() : new Date(value).getTime();
  return Number.isNaN(ms) ? null : ms;
}

/**
 * Whole seconds left in the break; negative once overdue, null when there
 * is no (valid) halftime_start.
 */
export function remainingSeconds(halftimeStart, now = Date.now()) {
  const start = toMs(halftimeStart);
  const nowMs = toMs(now);
  if (start === null || nowMs === null) return null;
  const secs = Math.ceil((start + BREAK_MS - nowMs) / 1000);
  return secs === 0 ? 0 : secs; // normalise -0
}

/** "7:42" while the break runs, "+2:15" once overdue, "" for null. */
export function countdownText(remaining) {
  if (remaining === null || remaining === undefined) return '';
  const abs = Math.abs(remaining);
  const m = Math.floor(abs / 60);
  const s = abs % 60;
  const text = `${m}:${String(s).padStart(2, '0')}`;
  return remaining < 0 ? `+${text}` : text;
}

/** True once the 10-minute break has run out. */
export function isOverdue(remaining) {
  return remaining !== null && remaining !== undefined && remaining < 0;
}

/**
 * When the 2nd half most likely kicked off: the end of the break, but never
 * in the future. Returns a Date, or null when there is no halftime_start.
 */
export function expectedSecondHalfStart(halftimeStart, now = Date.now()) {
  const start = toMs(halftimeStart);
  const nowMs = toMs(now);
  if (start === null || nowMs === null) return null;
  return new Date(Math.min(start + BREAK_MS, nowMs));
}

/**
 * Whether backdating is worth offering: only when the end of the break is
 * at least a minute in the past.
 */
export function shouldOfferBackdate(halftimeStart, now = Date.now()) {
  const remaining = remainingSeconds(halftimeStart, now);
  return remaining !== null && remaining <= -60;
}
