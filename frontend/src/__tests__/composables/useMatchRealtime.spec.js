/**
 * useMatchRealtime tests (SB-66).
 *
 * The composable is a thin wrapper around Supabase Realtime. Tests mock
 * the supabase client to verify channel setup, callback dispatch, and
 * unsubscribe lifecycle without hitting any network.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// vi.mock is hoisted, so the factory has to construct its own mocks.
// We use vi.hoisted to share the mock instances back to the test scope.
const { mockChannel, supabaseMock } = vi.hoisted(() => {
  const channel = {
    on: vi.fn(),
    subscribe: vi.fn(),
  };
  return {
    mockChannel: channel,
    supabaseMock: {
      channel: vi.fn(() => channel),
      removeChannel: vi.fn(),
    },
  };
});

vi.mock('@/config/supabase', () => ({
  supabase: supabaseMock,
}));

import { subscribeToMatch } from '@/composables/useMatchRealtime';

beforeEach(() => {
  vi.clearAllMocks();
  mockChannel.on.mockReturnValue(mockChannel);
  mockChannel.subscribe.mockReturnValue(mockChannel);
});

describe('subscribeToMatch — channel setup', () => {
  it('creates a channel named match-row:{matchId}', () => {
    subscribeToMatch(42, () => {});
    expect(supabaseMock.channel).toHaveBeenCalledWith('match-row:42');
  });

  it('registers an UPDATE listener on the matches table for that id', () => {
    subscribeToMatch(42, () => {});
    expect(mockChannel.on).toHaveBeenCalledWith(
      'postgres_changes',
      expect.objectContaining({
        event: 'UPDATE',
        schema: 'public',
        table: 'matches',
        filter: 'id=eq.42',
      }),
      expect.any(Function)
    );
  });

  it('subscribes to the channel', () => {
    subscribeToMatch(42, () => {});
    expect(mockChannel.subscribe).toHaveBeenCalled();
  });
});

describe('subscribeToMatch — callback', () => {
  it('fires the user callback with payload.new on UPDATE', () => {
    const onUpdate = vi.fn();
    subscribeToMatch(42, onUpdate);

    // Pull the listener that was passed to .on() and invoke it as Supabase would.
    const listener = mockChannel.on.mock.calls[0][2];
    listener({ new: { id: 42, home_score: 2, away_score: 1 } });

    expect(onUpdate).toHaveBeenCalledWith({
      id: 42,
      home_score: 2,
      away_score: 1,
    });
  });

  it('does nothing on a payload with no `new` field', () => {
    const onUpdate = vi.fn();
    subscribeToMatch(42, onUpdate);

    const listener = mockChannel.on.mock.calls[0][2];
    listener({}); // malformed payload

    expect(onUpdate).not.toHaveBeenCalled();
  });
});

describe('subscribeToMatch — lifecycle', () => {
  it('unsubscribe() removes the channel from supabase', () => {
    const handle = subscribeToMatch(42, () => {});
    handle.unsubscribe();
    expect(supabaseMock.removeChannel).toHaveBeenCalledWith(mockChannel);
  });

  it('isConnected() reflects SUBSCRIBED status', () => {
    const handle = subscribeToMatch(42, () => {});
    // Pull the status callback handed to .subscribe()
    const subscribeStatusCb = mockChannel.subscribe.mock.calls[0][0];

    expect(handle.isConnected()).toBe(false);
    subscribeStatusCb('SUBSCRIBED');
    expect(handle.isConnected()).toBe(true);
    subscribeStatusCb('CLOSED');
    expect(handle.isConnected()).toBe(false);
  });
});

describe('subscribeToMatch — input validation', () => {
  it('throws when matchId is null', () => {
    expect(() => subscribeToMatch(null, () => {})).toThrow(/matchId/);
  });

  it('throws when matchId is undefined', () => {
    expect(() => subscribeToMatch(undefined, () => {})).toThrow(/matchId/);
  });

  it('throws when onUpdate is not a function', () => {
    expect(() => subscribeToMatch(42, null)).toThrow(/onUpdate/);
  });
});
