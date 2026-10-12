/**
 * Live chat safety (SB-1324): the pure half of report / block / chat rules.
 *
 * Mirrors the iOS app's MTKit/Safety.swift so both clients say the same
 * thing. Backend: backend/api/moderation.py, plus the word filter, ban check
 * and rate limit on POST /live/message.
 */

// The `reason` values POST .../report accepts, with the iOS wording.
export const REPORT_REASONS = [
  { value: 'spam', label: 'Spam' },
  { value: 'harassment', label: 'Harassment' },
  { value: 'hate', label: 'Hate Speech' },
  { value: 'sexual', label: 'Sexual Content' },
  { value: 'other', label: 'Something Else' },
];

export const CHAT_RULES_TEXT =
  'Be respectful. No harassment, hate, sexual content or spam. ' +
  'Objectionable content is removed and users who post it lose chat access.';

// Why POST /live/message refused a message, keyed by HTTP status.
const CHAT_POST_ERRORS = {
  422: "That message contains language that isn't allowed.",
  403: 'You can no longer post in chat.',
  429: "You're sending messages too fast.",
};

/**
 * The composer's message for a failed post. Statuses with no chat-specific
 * meaning fall back to whatever the request reported.
 */
export function chatPostErrorMessage(status, fallback) {
  return CHAT_POST_ERRORS[status] || fallback || 'Failed to send message';
}

/**
 * Whether `event` is a chat message written by someone in `blocked`. Only
 * chat is hidden: goals, cards and subs a blocked manager records stay.
 */
export function isChatByBlocked(event, blocked) {
  if (!event || event.event_type !== 'message' || !event.created_by) {
    return false;
  }
  return blocked.has(String(event.created_by));
}

/**
 * `events` without chat from anyone in `blocked`. The server already leaves
 * them out of reads; this covers realtime inserts and the gap between
 * blocking someone and the next fetch.
 */
export function visibleEvents(events, blocked) {
  if (!blocked || blocked.size === 0) return events;
  return events.filter(event => !isChatByBlocked(event, blocked));
}

/** localStorage key recording that `userId` agreed to the chat rules. */
export function chatRulesKey(userId) {
  return `mt_chat_rules_accepted:${userId}`;
}

// ── Admin review (GET/PATCH /api/admin/content-reports) ──

export const REPORT_REASON_LABELS = Object.fromEntries(
  REPORT_REASONS.map(r => [r.value, r.label])
);

/** Pending reports first, then newest first within each group. */
export function sortReportsPendingFirst(reports) {
  return [...reports].sort((a, b) => {
    const pa = a.status === 'pending' ? 0 : 1;
    const pb = b.status === 'pending' ? 0 : 1;
    if (pa !== pb) return pa - pb;
    return String(b.created_at || '').localeCompare(String(a.created_at || ''));
  });
}
