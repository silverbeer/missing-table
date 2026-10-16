/**
 * chatSafety — the pure half of live chat report/block (SB-1324).
 */

import { describe, it, expect } from 'vitest';
import {
  chatPostErrorMessage,
  chatRulesKey,
  isChatByBlocked,
  sortReportsPendingFirst,
  visibleEvents,
} from '@/utils/chatSafety';

const BLOCKED = 'user-blocked';
const OTHER = 'user-other';

const chat = (id, createdBy, message = 'hi') => ({
  id,
  event_type: 'message',
  created_by: createdBy,
  message,
});

describe('visibleEvents', () => {
  const events = [
    chat(1, BLOCKED, 'rude'),
    { id: 2, event_type: 'goal', created_by: BLOCKED, player_name: 'Sam' },
    { id: 3, event_type: 'yellow_card', created_by: BLOCKED },
    chat(4, OTHER, 'nice goal'),
    { id: 5, event_type: 'status_change', created_by: BLOCKED },
  ];

  it("hides a blocked author's chat", () => {
    const shown = visibleEvents(events, new Set([BLOCKED]));
    expect(shown.map(e => e.id)).not.toContain(1);
  });

  it('keeps the goals, cards and status changes a blocked user recorded', () => {
    const shown = visibleEvents(events, new Set([BLOCKED]));
    expect(shown.map(e => e.id)).toEqual([2, 3, 4, 5]);
  });

  it('keeps chat from everyone else', () => {
    const shown = visibleEvents(events, new Set([BLOCKED]));
    expect(shown.find(e => e.id === 4).message).toBe('nice goal');
  });

  it('returns the list untouched when nobody is blocked', () => {
    expect(visibleEvents(events, new Set())).toBe(events);
    expect(visibleEvents(events, null)).toBe(events);
  });

  it('keeps chat with no recorded author', () => {
    const anon = chat(6, null);
    expect(visibleEvents([anon], new Set([BLOCKED]))).toEqual([anon]);
  });

  it('matches numeric and string ids alike', () => {
    expect(isChatByBlocked(chat(7, 42), new Set(['42']))).toBe(true);
  });
});

describe('chatPostErrorMessage', () => {
  it('words a word-filter rejection (422)', () => {
    expect(chatPostErrorMessage(422, 'raw')).toBe(
      "That message contains language that isn't allowed."
    );
  });

  it('words a chat ban (403)', () => {
    expect(chatPostErrorMessage(403, 'raw')).toBe(
      'You can no longer post in chat.'
    );
  });

  it('words the rate limit (429)', () => {
    expect(chatPostErrorMessage(429, 'raw')).toBe(
      "You're sending messages too fast."
    );
  });

  it('a 403 for the club room or full time keeps the API wording (SB-1330)', () => {
    expect(
      chatPostErrorMessage(
        403,
        'Live chat is open to members of the clubs playing'
      )
    ).toBe('Live chat is open to members of the clubs playing');
    expect(chatPostErrorMessage(403, 'Chat has closed for this match')).toBe(
      'Chat has closed for this match'
    );
  });

  it('falls back to the request error for any other status', () => {
    expect(chatPostErrorMessage(500, 'Server exploded')).toBe(
      'Server exploded'
    );
    expect(chatPostErrorMessage(undefined, '')).toBe('Failed to send message');
  });
});

describe('chatRulesKey', () => {
  it('is per user', () => {
    expect(chatRulesKey('a')).not.toBe(chatRulesKey('b'));
  });
});

describe('sortReportsPendingFirst', () => {
  it('puts pending reports first, newest first within each group', () => {
    const sorted = sortReportsPendingFirst([
      { id: 1, status: 'dismissed', created_at: '2026-10-12T10:00:00Z' },
      { id: 2, status: 'pending', created_at: '2026-10-10T10:00:00Z' },
      { id: 3, status: 'actioned', created_at: '2026-10-11T10:00:00Z' },
      { id: 4, status: 'pending', created_at: '2026-10-11T10:00:00Z' },
    ]);
    expect(sorted.map(r => r.id)).toEqual([4, 2, 1, 3]);
  });
});
