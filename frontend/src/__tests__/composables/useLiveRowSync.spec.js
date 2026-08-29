/**
 * useLiveRowSync tests (SB-909).
 *
 * A view that loads matches once goes stale the moment one of them ends
 * elsewhere. This composable is what keeps the Tournaments tab honest:
 * realtime for the live rows, a refetch when the tab comes back for
 * everything realtime missed.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ref, nextTick } from 'vue';

const { subscribeToMatch, handles } = vi.hoisted(() => {
  const made = [];
  return {
    handles: made,
    subscribeToMatch: vi.fn((id, onUpdate) => {
      const handle = { id, onUpdate, unsubscribe: vi.fn() };
      made.push(handle);
      return handle;
    }),
  };
});

vi.mock('@/composables/useMatchRealtime', () => ({ subscribeToMatch }));

import { useLiveRowSync } from '@/composables/useLiveRowSync';

const match = (id, status) => ({ id, match_status: status });

beforeEach(() => {
  vi.clearAllMocks();
  handles.length = 0;
});

afterEach(() => {
  document.dispatchEvent(new Event('visibilitychange'));
});

describe('useLiveRowSync — subscriptions', () => {
  it('subscribes only to live rows', () => {
    const matches = ref([
      match(1, 'live'),
      match(2, 'scheduled'),
      match(3, 'completed'),
    ]);
    const sync = useLiveRowSync(matches, () => {});

    expect(sync.subscribedIds()).toEqual([1]);
    sync.stop();
  });

  it('subscribes to a match that goes live after load', async () => {
    const matches = ref([match(1, 'scheduled')]);
    const sync = useLiveRowSync(matches, () => {});
    expect(sync.subscribedIds()).toEqual([]);

    matches.value = [match(1, 'live')];
    await nextTick();

    expect(sync.subscribedIds()).toEqual([1]);
    sync.stop();
  });

  it('unsubscribes when a match stops being live', async () => {
    const matches = ref([match(1, 'live')]);
    const sync = useLiveRowSync(matches, () => {});
    const handle = handles[0];

    matches.value = [match(1, 'completed')];
    await nextTick();

    expect(handle.unsubscribe).toHaveBeenCalled();
    expect(sync.subscribedIds()).toEqual([]);
    sync.stop();
  });

  it('does not resubscribe to a row it already watches', async () => {
    const matches = ref([match(1, 'live')]);
    const sync = useLiveRowSync(matches, () => {});

    matches.value = [match(1, 'live'), match(2, 'scheduled')];
    await nextTick();

    expect(subscribeToMatch).toHaveBeenCalledTimes(1);
    sync.stop();
  });

  it('hands realtime payloads to the caller', () => {
    const matches = ref([match(1, 'live')]);
    const applyUpdate = vi.fn();
    const sync = useLiveRowSync(matches, applyUpdate);

    handles[0].onUpdate({ id: 1, home_score: 2, away_score: 3 });

    expect(applyUpdate).toHaveBeenCalledWith({
      id: 1,
      home_score: 2,
      away_score: 3,
    });
    sync.stop();
  });

  it('drops every subscription on stop', () => {
    const matches = ref([match(1, 'live'), match(2, 'live')]);
    const sync = useLiveRowSync(matches, () => {});

    sync.stop();

    expect(handles.every(h => h.unsubscribe.mock.calls.length === 1)).toBe(
      true
    );
    expect(sync.subscribedIds()).toEqual([]);
  });

  it('survives a subscription that throws', () => {
    // Realtime is an enhancement. A misconfigured or unreachable socket must
    // not take the view down — CI caught exactly this as an unhandled error.
    subscribeToMatch.mockImplementationOnce(() => {
      throw new Error('socket unavailable');
    });
    const matches = ref([match(1, 'live')]);

    expect(() => useLiveRowSync(matches, () => {})).not.toThrow();
  });

  it('tolerates an empty or absent list', () => {
    const matches = ref(null);
    const sync = useLiveRowSync(matches, () => {});
    expect(sync.subscribedIds()).toEqual([]);
    sync.stop();
  });
});

describe('useLiveRowSync — refresh on return', () => {
  const setHidden = value =>
    Object.defineProperty(document, 'hidden', {
      value,
      configurable: true,
    });

  it('refetches when the tab becomes visible again', () => {
    const onReturn = vi.fn();
    const sync = useLiveRowSync(ref([]), () => {}, { onReturn });

    setHidden(false);
    document.dispatchEvent(new Event('visibilitychange'));

    expect(onReturn).toHaveBeenCalledTimes(1);
    sync.stop();
  });

  it('does not refetch when the tab is being hidden', () => {
    const onReturn = vi.fn();
    const sync = useLiveRowSync(ref([]), () => {}, { onReturn });

    setHidden(true);
    document.dispatchEvent(new Event('visibilitychange'));

    expect(onReturn).not.toHaveBeenCalled();
    sync.stop();
  });

  it('stops listening after stop', () => {
    const onReturn = vi.fn();
    const sync = useLiveRowSync(ref([]), () => {}, { onReturn });
    sync.stop();

    setHidden(false);
    document.dispatchEvent(new Event('visibilitychange'));

    expect(onReturn).not.toHaveBeenCalled();
  });
});
