/**
 * Live Match Composable
 *
 * Provides reactive state and methods for live match functionality.
 * Uses Supabase Realtime for push updates of match state and events.
 */

import { ref, computed, onUnmounted, watch } from 'vue';
import { supabase } from '../config/supabase';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';

export function useLiveMatch(matchId) {
  const authStore = useAuthStore();

  // Reactive state
  const matchState = ref(null);
  const events = ref([]);
  const isLoading = ref(true);
  const error = ref(null);
  const isConnected = ref(false);

  // Supabase channels
  let matchChannel = null;
  let eventsChannel = null;

  // Clock update interval
  let clockInterval = null;
  const currentTime = ref(Date.now());

  // Computed: elapsed time in seconds based on timestamps
  const elapsedSeconds = computed(() => {
    if (!matchState.value) return 0;

    const {
      kickoff_time,
      halftime_start,
      second_half_start,
      match_end_time,
      match_status,
      half_duration = 45, // Default to 45 minutes per half
    } = matchState.value;

    const halfDurationSeconds = half_duration * 60;
    const fullMatchSeconds = half_duration * 2 * 60;

    // Match not started
    if (!kickoff_time) return 0;

    // Match ended - show full match time
    if (match_end_time || match_status === 'completed') {
      return fullMatchSeconds;
    }

    const now = currentTime.value;

    // In second half
    if (second_half_start) {
      const secondHalfElapsed =
        (now - new Date(second_half_start).getTime()) / 1000;
      return halfDurationSeconds + secondHalfElapsed;
    }

    // At halftime
    if (halftime_start && !second_half_start) {
      return halfDurationSeconds;
    }

    // In first half
    const firstHalfElapsed = (now - new Date(kickoff_time).getTime()) / 1000;
    return Math.min(firstHalfElapsed, halfDurationSeconds);
  });

  // Computed: formatted elapsed time (MM:SS)
  const elapsedTimeFormatted = computed(() => {
    const totalSeconds = Math.floor(elapsedSeconds.value);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  });

  // Computed: match period
  const matchPeriod = computed(() => {
    if (!matchState.value) return 'Not Started';

    const {
      kickoff_time,
      halftime_start,
      second_half_start,
      match_end_time,
      match_status,
    } = matchState.value;

    if (match_end_time || match_status === 'completed') return 'Full Time';
    if (second_half_start) return '2nd Half';
    if (halftime_start) return 'Halftime';
    if (kickoff_time) return '1st Half';
    return 'Not Started';
  });

  // Computed: can the current user manage this match?
  const canManage = computed(() => {
    if (!matchState.value) return false;
    if (!authStore.isAuthenticated.value) return false;

    // Admins can manage all
    if (authStore.isAdmin.value) return true;

    // Club managers can manage their club's teams
    if (authStore.isClubManager.value) {
      // This would need club_id check - for now allow
      return true;
    }

    // Team managers can manage their team's matches
    if (authStore.isTeamManager.value) {
      const userTeamId = authStore.userTeamId.value;
      return (
        userTeamId === matchState.value.home_team_id ||
        userTeamId === matchState.value.away_team_id
      );
    }

    return false;
  });

  // Fetch initial match state
  async function fetchMatchState() {
    try {
      isLoading.value = true;
      error.value = null;

      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/live`
      );

      if (response) {
        matchState.value = response;
        events.value = response.recent_events || [];
      }
    } catch (err) {
      console.error('Error fetching match state:', err);
      error.value = err.message || 'Failed to load match';
    } finally {
      isLoading.value = false;
    }
  }

  // Subscribe to Supabase Realtime
  function subscribeToRealtime() {
    // Subscribe to match changes
    matchChannel = supabase
      .channel(`match:${matchId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'matches',
          filter: `id=eq.${matchId}`,
        },
        payload => {
          console.log('Match update received:', payload);
          // Merge updated fields into match state
          if (matchState.value) {
            matchState.value = { ...matchState.value, ...payload.new };
          }
        }
      )
      .subscribe(status => {
        isConnected.value = status === 'SUBSCRIBED';
        console.log('Match channel status:', status);
      });

    // Subscribe to new events
    eventsChannel = supabase
      .channel(`match_events:${matchId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'match_events',
          filter: `match_id=eq.${matchId}`,
        },
        payload => {
          console.log('New event received:', payload);
          // Check if event already exists (avoid duplicates from optimistic updates)
          const exists = events.value.some(e => e.id === payload.new.id);
          if (!exists) {
            events.value = [payload.new, ...events.value].slice(0, 100);
          }
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'match_events',
          filter: `match_id=eq.${matchId}`,
        },
        payload => {
          console.log('Event update received:', payload);
          // Update the event (for soft deletes)
          const index = events.value.findIndex(e => e.id === payload.new.id);
          if (index !== -1) {
            // If deleted, remove from list
            if (payload.new.is_deleted) {
              events.value = events.value.filter(e => e.id !== payload.new.id);
            } else {
              events.value[index] = payload.new;
            }
          }
        }
      )
      .subscribe(status => {
        console.log('Events channel status:', status);
      });
  }

  // Unsubscribe from Realtime
  function unsubscribeFromRealtime() {
    if (matchChannel) {
      supabase.removeChannel(matchChannel);
      matchChannel = null;
    }
    if (eventsChannel) {
      supabase.removeChannel(eventsChannel);
      eventsChannel = null;
    }
    isConnected.value = false;
  }

  // Start clock update interval
  function startClockInterval() {
    if (clockInterval) clearInterval(clockInterval);
    clockInterval = setInterval(() => {
      currentTime.value = Date.now();
    }, 1000);
  }

  // Stop clock update interval
  function stopClockInterval() {
    if (clockInterval) {
      clearInterval(clockInterval);
      clockInterval = null;
    }
  }

  // API Methods

  async function updateClock(actionOrPayload, halfDuration = null) {
    try {
      // Handle both string action and object payload
      let payload;
      if (typeof actionOrPayload === 'object') {
        payload = actionOrPayload;
      } else {
        payload = { action: actionOrPayload };
        if (halfDuration) {
          payload.half_duration = halfDuration;
        }
      }

      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/live/clock`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      );
      if (response) {
        matchState.value = response;
      }
      return { success: true };
    } catch (err) {
      console.error('Error updating clock:', err);
      return { success: false, error: err.message };
    }
  }

  async function postGoal(teamId, playerName, message = null) {
    try {
      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/live/goal`,
        {
          method: 'POST',
          body: JSON.stringify({
            team_id: teamId,
            player_name: playerName,
            message,
          }),
        }
      );
      if (response) {
        matchState.value = response;
        // Refetch events to get the new goal event
        await fetchMatchState();
      }
      return { success: true };
    } catch (err) {
      console.error('Error posting goal:', err);
      return { success: false, error: err.message };
    }
  }

  async function postMessage(message) {
    try {
      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/live/message`,
        {
          method: 'POST',
          body: JSON.stringify({ message }),
        }
      );
      // Add event to local state immediately (don't wait for Realtime)
      if (response && response.id) {
        events.value = [response, ...events.value].slice(0, 100);
      }
      return { success: true, event: response };
    } catch (err) {
      console.error('Error posting message:', err);
      return { success: false, error: err.message };
    }
  }

  async function deleteEvent(eventId) {
    try {
      await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/live/events/${eventId}`,
        { method: 'DELETE' }
      );
      // Remove from local state immediately
      events.value = events.value.filter(e => e.id !== eventId);
      return { success: true };
    } catch (err) {
      console.error('Error deleting event:', err);
      return { success: false, error: err.message };
    }
  }

  async function loadMoreEvents(beforeId) {
    try {
      const response = await authStore.apiRequest(
        `${getApiBaseUrl()}/api/matches/${matchId}/live/events?before_id=${beforeId}&limit=50`
      );
      if (response && Array.isArray(response)) {
        events.value = [...events.value, ...response];
      }
      return { success: true };
    } catch (err) {
      console.error('Error loading more events:', err);
      return { success: false, error: err.message };
    }
  }

  // Initialize on mount
  async function initialize() {
    await fetchMatchState();
    subscribeToRealtime();
    startClockInterval();
  }

  // Cleanup on unmount
  onUnmounted(() => {
    unsubscribeFromRealtime();
    stopClockInterval();
  });

  // Watch for matchId changes (if used dynamically)
  watch(
    () => matchId,
    newId => {
      if (newId) {
        unsubscribeFromRealtime();
        stopClockInterval();
        initialize();
      }
    }
  );

  // Auto-initialize
  initialize();

  return {
    // State
    matchState,
    events,
    isLoading,
    error,
    isConnected,

    // Computed
    elapsedSeconds,
    elapsedTimeFormatted,
    matchPeriod,
    canManage,

    // Methods
    updateClock,
    postGoal,
    postMessage,
    deleteEvent,
    loadMoreEvents,
    fetchMatchState,
  };
}
