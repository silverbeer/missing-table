/**
 * useNotificationPreferences tests (SB-57).
 *
 * Singleton composable. Reset via _resetNotificationPreferencesForTest
 * between cases so module-level state doesn't leak.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

const isAuthenticatedRef = { value: true };
const apiRequestMock = vi.fn();

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    isAuthenticated: isAuthenticatedRef,
    apiRequest: apiRequestMock,
  }),
}));

vi.mock('@/config/api', () => ({
  getApiBaseUrl: () => 'http://test.example',
}));

import {
  useNotificationPreferences,
  _resetNotificationPreferencesForTest,
  DEFAULT_PREFERENCES,
} from '@/composables/useNotificationPreferences';

beforeEach(() => {
  apiRequestMock.mockReset();
  isAuthenticatedRef.value = true;
  _resetNotificationPreferencesForTest();
});

describe('useNotificationPreferences.ensureLoaded', () => {
  it('hits GET once and populates preferences with defaults merged over stored', async () => {
    apiRequestMock.mockResolvedValueOnce({
      preferences: { ...DEFAULT_PREFERENCES, goal: false, yellow_card: true },
    });

    const { ensureLoaded, preferences, loaded } = useNotificationPreferences();
    await ensureLoaded();

    expect(apiRequestMock).toHaveBeenCalledWith(
      'http://test.example/api/users/me/notification-preferences'
    );
    expect(loaded.value).toBe(true);
    expect(preferences.value.goal).toBe(false);
    expect(preferences.value.yellow_card).toBe(true);
    expect(preferences.value.kickoff).toBe(true);
  });

  it('does not refetch when already loaded', async () => {
    apiRequestMock.mockResolvedValueOnce({ preferences: DEFAULT_PREFERENCES });

    const a = useNotificationPreferences();
    await a.ensureLoaded();
    await a.ensureLoaded();

    expect(apiRequestMock).toHaveBeenCalledTimes(1);
  });

  it('coalesces concurrent ensureLoaded calls', async () => {
    apiRequestMock.mockImplementationOnce(
      () =>
        new Promise(resolve =>
          setTimeout(() => resolve({ preferences: DEFAULT_PREFERENCES }), 5)
        )
    );

    const a = useNotificationPreferences();
    await Promise.all([a.ensureLoaded(), a.ensureLoaded(), a.ensureLoaded()]);

    expect(apiRequestMock).toHaveBeenCalledTimes(1);
  });

  it('returns defaults without a network call when unauthenticated', async () => {
    isAuthenticatedRef.value = false;
    const { ensureLoaded, preferences, loaded } = useNotificationPreferences();
    await ensureLoaded();
    expect(apiRequestMock).not.toHaveBeenCalled();
    expect(loaded.value).toBe(true);
    expect(preferences.value).toEqual(DEFAULT_PREFERENCES);
  });
});

describe('useNotificationPreferences.setPreference', () => {
  it('optimistically updates + PUTs the new value, replaces with server echo', async () => {
    apiRequestMock.mockResolvedValueOnce({ preferences: DEFAULT_PREFERENCES }); // initial GET
    apiRequestMock.mockResolvedValueOnce({
      preferences: { ...DEFAULT_PREFERENCES, goal: false },
    }); // PUT

    const { ensureLoaded, setPreference, preferences } =
      useNotificationPreferences();
    await ensureLoaded();

    const result = await setPreference('goal', false);

    expect(result.success).toBe(true);
    expect(preferences.value.goal).toBe(false);
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      'http://test.example/api/users/me/notification-preferences',
      {
        method: 'PUT',
        body: JSON.stringify({ preferences: { goal: false } }),
      }
    );
  });

  it('reverts the optimistic change when the PUT fails', async () => {
    apiRequestMock.mockResolvedValueOnce({ preferences: DEFAULT_PREFERENCES });
    apiRequestMock.mockRejectedValueOnce(new Error('boom'));

    const { ensureLoaded, setPreference, preferences, error } =
      useNotificationPreferences();
    await ensureLoaded();

    const result = await setPreference('goal', false);

    expect(result.success).toBe(false);
    expect(preferences.value.goal).toBe(true); // reverted
    expect(error.value).toBe('boom');
  });

  it('is idempotent — no PUT when the value already matches', async () => {
    apiRequestMock.mockResolvedValueOnce({ preferences: DEFAULT_PREFERENCES });

    const { ensureLoaded, setPreference } = useNotificationPreferences();
    await ensureLoaded();
    expect(apiRequestMock).toHaveBeenCalledTimes(1);

    // goal is already true by default — re-setting to true is a no-op.
    const result = await setPreference('goal', true);
    expect(result.success).toBe(true);
    expect(apiRequestMock).toHaveBeenCalledTimes(1); // still just the initial GET
  });

  it('rejects unknown event types', async () => {
    apiRequestMock.mockResolvedValueOnce({ preferences: DEFAULT_PREFERENCES });
    const { ensureLoaded, setPreference } = useNotificationPreferences();
    await ensureLoaded();

    const result = await setPreference('bogus', true);
    expect(result.success).toBe(false);
    expect(result.error).toMatch(/Unknown event_type/);
    expect(apiRequestMock).toHaveBeenCalledTimes(1); // no PUT fired
  });
});

describe('useNotificationPreferences.setCards', () => {
  it('updates yellow_card + red_card together in a single PUT', async () => {
    apiRequestMock.mockResolvedValueOnce({ preferences: DEFAULT_PREFERENCES });
    apiRequestMock.mockResolvedValueOnce({
      preferences: {
        ...DEFAULT_PREFERENCES,
        yellow_card: true,
        red_card: true,
      },
    });

    const { ensureLoaded, setCards, preferences } =
      useNotificationPreferences();
    await ensureLoaded();

    await setCards(true);

    expect(preferences.value.yellow_card).toBe(true);
    expect(preferences.value.red_card).toBe(true);
    expect(apiRequestMock).toHaveBeenNthCalledWith(
      2,
      expect.any(String),
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({
          preferences: { yellow_card: true, red_card: true },
        }),
      })
    );
  });

  it('cardsEnabled reflects either-yellow-or-red as true', async () => {
    apiRequestMock.mockResolvedValueOnce({
      preferences: {
        ...DEFAULT_PREFERENCES,
        yellow_card: true,
        red_card: false,
      },
    });

    const { ensureLoaded, cardsEnabled } = useNotificationPreferences();
    await ensureLoaded();

    expect(cardsEnabled.value).toBe(true);
  });

  it('reverts both flags when the PUT fails', async () => {
    apiRequestMock.mockResolvedValueOnce({ preferences: DEFAULT_PREFERENCES });
    apiRequestMock.mockRejectedValueOnce(new Error('nope'));

    const { ensureLoaded, setCards, preferences } =
      useNotificationPreferences();
    await ensureLoaded();

    await setCards(true);

    expect(preferences.value.yellow_card).toBe(false);
    expect(preferences.value.red_card).toBe(false);
  });
});

describe('useNotificationPreferences singleton', () => {
  it('shares state across multiple callers', async () => {
    apiRequestMock.mockResolvedValueOnce({
      preferences: { ...DEFAULT_PREFERENCES, goal: false },
    });

    const a = useNotificationPreferences();
    await a.ensureLoaded();

    const b = useNotificationPreferences();
    expect(b.preferences.value.goal).toBe(false);
  });
});
