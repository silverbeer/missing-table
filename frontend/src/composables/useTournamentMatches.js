/**
 * Tournament matches composable (SB-1749).
 *
 * Owns how the Tournaments page gets a tournament's matches, and the one
 * decision behind it — the scale switch:
 *
 * - **Small** (up to LARGE_TOURNAMENT_MATCH_THRESHOLD matches): one call to
 *   `GET /api/tournaments/{id}`, every match in the response. Unchanged.
 * - **Large** (more than that — MLS NEXT Fest is ~2,400): one response cannot
 *   hold it, so matches are paged and filtered server-side. An age group is
 *   always selected and a page is never more than TOURNAMENT_PAGE_SIZE rows.
 *
 * Backend endpoints (large mode):
 *   GET /api/tournaments/{id}/matches?age_group_id=&group=&round=&limit=&offset=
 *        → { matches, total, limit, offset }
 *   GET /api/tournaments/{id}/filters?age_group_id=&on_date=
 *        → { facets_available, age_groups: [{ id, name, matches, matches_on_date }],
 *            groups: [{ key, division, label, matches }] | null }
 *
 * The filters are decoration on the list: when that request fails, or the
 * server cannot count (`matches: null`, `groups: null`), the list still loads
 * and the controls show no numbers — unknown is not zero.
 *
 * Not a singleton: each caller gets its own state.
 */

import { ref, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { getApiBaseUrl } from '../config/api';
import { localDateKey } from '../utils/tournamentStatus';

// The scale switch. A tournament with more matches than this is "large".
export const LARGE_TOURNAMENT_MATCH_THRESHOLD = 300;

// Rows per request in large mode. The API caps a page at 500. Must equal the
// API's default page size (DEFAULT_LIMIT in backend/dao/tournament_filters.py):
// only pages of that size, at a multiple of it, are cached by the server.
export const TOURNAMENT_PAGE_SIZE = 200;

// A group is a group-stage pool, and the Group control's counts are counts of
// group-stage matches. The API treats `group` and `round` as independent, so
// a Group filter is sent with this round to make the list what was counted.
export const GROUP_FILTER_ROUND = 'group_stage';

/** True when the tournament's exact `match_count` puts it past the switch. */
export function isLargeTournament(tournament) {
  return Number(tournament?.match_count) > LARGE_TOURNAMENT_MATCH_THRESHOLD;
}

/**
 * The age group a large tournament opens on: the first one playing today,
 * else the first with any matches, else the first listed. `matches: null`
 * (not counted) is not "no matches", so it does not rule an age group out.
 */
export function pickDefaultAgeGroupId(ageGroups) {
  const list = ageGroups || [];
  const today = list.find(ag => ag.matches_on_date > 0);
  if (today) return today.id;
  const withMatches = list.find(ag => ag.matches == null || ag.matches > 0);
  return (withMatches ?? list[0])?.id ?? null;
}

export function useTournamentMatches() {
  const authStore = useAuthStore();

  // The tournament with its loaded matches: the whole list in small mode, the
  // pages loaded so far in large mode. Null until the first load.
  const tournament = ref(null);
  const isLarge = ref(false);

  // ── large mode only ──
  const ageGroups = ref([]);
  // null = unknown (do not offer the control); [] = this age has no groups.
  const groups = ref(null);
  const selectedAgeGroupId = ref(null);
  const selectedGroup = ref(null);
  // Exact number of matches the current filters select; null until known.
  const total = ref(null);
  const pageLoading = ref(false);
  const loadingMore = ref(false);
  const pageError = ref(null);

  // Bumped on every tournament load and every filter change, so an answer
  // that arrives for something the visitor has already left is dropped.
  let loadSeq = 0;
  let pageSeq = 0;
  // Loads that have not settled, and the tournament the latest one asked for.
  // While either disagrees with what is on screen, `tournament` is not the
  // tournament the visitor selected and must not be refreshed.
  let loadsInFlight = 0;
  let wantedId = null;

  const get = url => authStore.apiRequest(url, { method: 'GET' });

  const loadedCount = computed(() => tournament.value?.matches?.length ?? 0);
  const hasMore = computed(
    () =>
      isLarge.value && total.value != null && loadedCount.value < total.value
  );

  const fetchPage = (id, offset) => {
    const params = new URLSearchParams();
    if (selectedAgeGroupId.value != null) {
      params.set('age_group_id', selectedAgeGroupId.value);
    }
    if (selectedGroup.value != null) {
      params.set('group', selectedGroup.value);
      params.set('round', GROUP_FILTER_ROUND);
    }
    params.set('limit', TOURNAMENT_PAGE_SIZE);
    params.set('offset', offset);
    return get(`${getApiBaseUrl()}/api/tournaments/${id}/matches?${params}`);
  };

  // Never throws: a failed filters request resolves to null.
  const fetchFilters = async (id, ageGroupId) => {
    const params = new URLSearchParams();
    if (ageGroupId != null) params.set('age_group_id', ageGroupId);
    params.set('on_date', localDateKey());
    try {
      return await get(
        `${getApiBaseUrl()}/api/tournaments/${id}/filters?${params}`
      );
    } catch (err) {
      console.error('Error fetching tournament filters:', err);
      return null;
    }
  };

  // `keepGroups`: an answer without groups (failed, or not counted) leaves
  // the groups already known in place instead of making them unknown.
  const applyFilters = (
    data,
    { fallbackAgeGroups = null, keepGroups = false } = {}
  ) => {
    if (Array.isArray(data?.age_groups) && data.age_groups.length > 0) {
      ageGroups.value = data.age_groups;
    } else if (fallbackAgeGroups) {
      // No counts: `matches` stays null, never 0.
      ageGroups.value = fallbackAgeGroups.map(ag => ({
        id: ag.id,
        name: ag.name,
        matches: null,
        matches_on_date: null,
      }));
    }
    if (Array.isArray(data?.groups)) groups.value = data.groups;
    else if (!keepGroups) groups.value = null;
  };

  const setMatches = matches => {
    tournament.value = { ...tournament.value, matches };
  };

  /**
   * Load a tournament. `summary` is its row from `GET /api/tournaments` —
   * `match_count` decides the mode, and in large mode it is also the header
   * (name, dates, age groups), since the detail endpoint is never called.
   * Throws when the matches cannot be loaded.
   */
  const load = async summary => {
    wantedId = summary.id;
    loadsInFlight += 1;
    try {
      await loadTournament(summary);
    } finally {
      loadsInFlight -= 1;
    }
  };

  const loadTournament = async summary => {
    const seq = ++loadSeq;
    pageSeq += 1;
    const id = summary.id;
    const large = isLargeTournament(summary);

    if (!large) {
      const data = await get(`${getApiBaseUrl()}/api/tournaments/${id}`);
      if (seq !== loadSeq) return;
      isLarge.value = false;
      ageGroups.value = [];
      groups.value = null;
      selectedAgeGroupId.value = null;
      selectedGroup.value = null;
      total.value = null;
      pageError.value = null;
      pageLoading.value = false;
      tournament.value = data;
      return;
    }

    const all = await fetchFilters(id, null);
    if (seq !== loadSeq) return;
    selectedGroup.value = null;
    // Filters failed or came back empty: the tournament's own age groups
    // still make the Age Group control possible.
    applyFilters(all, { fallbackAgeGroups: summary.age_groups || [] });
    selectedAgeGroupId.value = pickDefaultAgeGroupId(ageGroups.value);
    // That answer's groups span every age; the scoped one below replaces it.
    groups.value = null;

    const [scoped, page] = await Promise.all([
      fetchFilters(id, selectedAgeGroupId.value),
      fetchPage(id, 0),
    ]);
    if (seq !== loadSeq) return;
    applyFilters(scoped);
    isLarge.value = true;
    pageError.value = null;
    pageLoading.value = false;
    total.value = page?.total ?? null;
    tournament.value = { ...summary, matches: page?.matches ?? [] };
  };

  // First page for the current filters, replacing what is on screen.
  const reloadPage = async () => {
    const id = tournament.value?.id;
    if (id == null) return;
    const seq = ++pageSeq;
    pageLoading.value = true;
    pageError.value = null;
    total.value = null;
    // The rows on screen belong to the previous filter.
    setMatches([]);
    try {
      const page = await fetchPage(id, 0);
      if (seq !== pageSeq) return;
      total.value = page?.total ?? null;
      setMatches(page?.matches ?? []);
    } catch (err) {
      if (seq !== pageSeq) return;
      console.error('Error fetching tournament matches:', err);
      pageError.value = 'Could not load these matches.';
    } finally {
      if (seq === pageSeq) pageLoading.value = false;
    }
  };

  // Groups already known survive an answer that has none to give: after an
  // age-group change they were cleared and stay unknown, and on a refresh the
  // Group control stays on screen — a group may be selected, and hiding the
  // control would leave the list narrowed with nothing to clear it.
  const reloadFilters = async () => {
    const id = tournament.value?.id;
    if (id == null) return;
    const seq = pageSeq;
    const ageGroupId = selectedAgeGroupId.value;
    const data = await fetchFilters(id, ageGroupId);
    if (seq !== pageSeq || ageGroupId !== selectedAgeGroupId.value) return;
    if (tournament.value?.id !== id) return;
    applyFilters(data, { keepGroups: true });
  };

  const setAgeGroup = async ageGroupId => {
    if (!isLarge.value || ageGroupId === selectedAgeGroupId.value) return;
    selectedAgeGroupId.value = ageGroupId;
    selectedGroup.value = null;
    // The old age's groups are not this age's; unknown until they arrive.
    groups.value = null;
    const page = reloadPage();
    await Promise.all([page, reloadFilters()]);
  };

  const setGroup = async groupKey => {
    const next = groupKey || null;
    if (!isLarge.value || next === selectedGroup.value) return;
    selectedGroup.value = next;
    await reloadPage();
  };

  const loadMore = async () => {
    const id = tournament.value?.id;
    if (id == null || !hasMore.value || loadingMore.value) return;
    const seq = pageSeq;
    loadingMore.value = true;
    pageError.value = null;
    try {
      const page = await fetchPage(id, loadedCount.value);
      if (seq !== pageSeq) return;
      const seen = new Set(tournament.value.matches.map(m => m.id));
      total.value = page?.total ?? total.value;
      setMatches([
        ...tournament.value.matches,
        ...(page?.matches ?? []).filter(m => !seen.has(m.id)),
      ]);
    } catch (err) {
      if (seq !== pageSeq) return;
      console.error('Error fetching more tournament matches:', err);
      pageError.value = 'Could not load more matches.';
    } finally {
      loadingMore.value = false;
    }
  };

  /**
   * Refetch what is on screen without disturbing it: the detail in small
   * mode, the pages already loaded in large mode. Throws on failure and
   * leaves the current rows in place.
   *
   * Does nothing while a tournament is loading, or when the last one asked
   * for is not the one on screen: `tournament` is then the previous
   * selection, and refetching it would put it back under the new one.
   */
  const refresh = async () => {
    const id = tournament.value?.id;
    if (id == null || loadsInFlight > 0 || id !== wantedId) return;
    const seq = loadSeq;
    // Still the tournament that was fetched, with no load started since.
    const current = () =>
      seq === loadSeq &&
      loadsInFlight === 0 &&
      wantedId === id &&
      tournament.value?.id === id;
    if (!isLarge.value) {
      const data = await get(`${getApiBaseUrl()}/api/tournaments/${id}`);
      if (current()) tournament.value = data;
      return;
    }
    const pSeq = pageSeq;
    const wanted = Math.max(loadedCount.value, 1);
    const rows = [];
    let newTotal = total.value;
    for (let offset = 0; offset < wanted; offset += TOURNAMENT_PAGE_SIZE) {
      const page = await fetchPage(id, offset);
      if (!current() || pSeq !== pageSeq) return;
      newTotal = page?.total ?? newTotal;
      rows.push(...(page?.matches ?? []));
      if (rows.length >= (newTotal ?? 0)) break;
    }
    total.value = newTotal;
    setMatches(rows);
    reloadFilters();
  };

  return {
    tournament,
    isLarge,
    ageGroups,
    groups,
    selectedAgeGroupId,
    selectedGroup,
    total,
    loadedCount,
    hasMore,
    pageLoading,
    loadingMore,
    pageError,
    load,
    refresh,
    reloadPage,
    setAgeGroup,
    setGroup,
    loadMore,
  };
}
