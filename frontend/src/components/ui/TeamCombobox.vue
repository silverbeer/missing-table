<template>
  <div>
    <SearchSelect
      ref="searchSelectRef"
      :model-value="modelValue"
      :options="options"
      :get-option-id="getOptionId"
      :get-option-label="getOptionLabel"
      :get-option-test-id="getOptionTestId"
      :resolve-label="resolveLabel"
      :resolve-option="resolveOption"
      :placeholder="placeholder"
      :required="required && !createName"
      testid-prefix="team-combobox"
      @update:model-value="onSelect"
      @update:query="query = $event"
    >
      <template #selected="{ option }">
        {{ teamLabel(option.team)
        }}{{
          !labelFormatter && badgeFor(option.team)
            ? ` · ${badgeFor(option.team)}`
            : ''
        }}
      </template>

      <template #option="{ option }">
        <template v-if="option.kind === 'create'">
          <span class="text-sm text-fg"
            >＋ Create new team “{{ query.trim() }}”</span
          >
        </template>
        <template v-else>
          <span class="text-sm text-fg truncate">{{
            teamLabel(option.team)
          }}</span>
          <span
            v-if="!labelFormatter && badgeFor(option.team)"
            class="text-xs px-1.5 py-0.5 rounded shrink-0"
            :class="
              badgeFor(option.team) === 'tournament'
                ? 'bg-line/60 text-fg-muted'
                : 'bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300'
            "
          >
            {{ badgeFor(option.team) }}
          </span>
        </template>
      </template>
    </SearchSelect>

    <p
      v-if="createName"
      class="text-xs text-amber-600 dark:text-amber-400 mt-1"
      data-testid="team-combobox-create-pending"
    >
      ＋ Will create new team “{{ createName }}”
    </p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import SearchSelect from './SearchSelect.vue';

/**
 * Team picker with type-ahead (SB-817), now a thin wrapper over the generic
 * SearchSelect shell (SB-964) — the shell owns the query text, open state
 * and keyboard handling; this component keeps its own team/create-row rules.
 *
 * Replaces free-text opponent entry. Selecting an existing team emits its id;
 * a team MT has never seen still gets created, but only via an explicit
 * "Create new team" row, so a typo can no longer mint a duplicate silently.
 *
 * Two-way bindings:
 *   v-model            -> selected team id (null when nothing is picked)
 *   v-model:createName -> name to create (empty unless the create row is chosen)
 * Exactly one of the two is non-empty at any time.
 */
const props = defineProps({
  modelValue: { type: Number, default: null },
  createName: { type: String, default: '' },
  teams: { type: Array, default: () => [] },
  // When set, only teams mapped to this age group are offered.
  ageGroupId: { type: Number, default: null },
  allowCreate: { type: Boolean, default: true },
  required: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Search teams…' },
  maxOptions: { type: Number, default: 8 },
  // When set, replaces the plain team name (and its league badge) with a
  // richer label — e.g. MatchesView's "TeamName (League - Division)" for My
  // Club, where a club can field the same team name in more than one league.
  labelFormatter: { type: Function, default: null },
});

const emit = defineEmits(['update:modelValue', 'update:createName']);

// The create row has no team id of its own; this sentinel is how it is
// told apart from a real team selection once it reaches onSelect below.
const CREATE_ID = '__create__';

const query = ref('');
const searchSelectRef = ref(null);

// A team with no league is one of the lightweight rows created for a
// tournament opponent — worth flagging so it is distinguishable from the real
// club team of the same name.
const badgeFor = team =>
  team.league_name || (team.league_id == null ? 'tournament' : '');

const inAgeGroup = team => {
  if (props.ageGroupId == null) return true;
  const ids =
    team.age_group_ids ||
    (team.age_groups || []).map(a => (typeof a === 'object' ? a.id : a));
  // A team with no age-group data recorded is not excluded — filtering it out
  // would hide real opponents whose mappings we simply do not have here.
  if (!ids || !ids.length) return true;
  return ids.includes(props.ageGroupId);
};

const matches = computed(() => {
  const q = query.value.trim().toLowerCase();
  const pool = props.teams.filter(inAgeGroup);
  if (!q) return pool.slice(0, props.maxOptions);
  return pool
    .filter(t => (t.name || '').toLowerCase().includes(q))
    .slice(0, props.maxOptions);
});

// A pre-selected team (e.g. a club fan/manager's own team, SB-599) can sit
// outside the first `maxOptions` once a club fields more teams than the cap,
// so SearchSelect can't always find it in the (capped) `options` array above
// to resolve a label from. This looks it up in the full, unfiltered `teams`
// list instead — see SearchSelect's `resolveLabel` doc comment for why this
// is kept separate from `options` rather than folded into it.
const resolveLabel = id => {
  const team = props.teams.find(t => t.id === id);
  return team ? teamLabel(team) : undefined;
};

// Same edge case, but for the "✓ selected" confirmation line (and its
// #selected slot, which needs the `{ kind: 'team', team }` shape `options`
// uses below, not the bare team): SearchSelect's own `selectedOption` looks
// the id up in the capped `options` array, which this pre-selected team can
// likewise sort past (SB-964 regression — the checkmark line was vanishing
// even though the input above it, resolved via `resolveLabel`, still showed
// the right name).
const resolveOption = id => {
  const team = props.teams.find(t => t.id === id);
  return team ? { kind: 'team', team } : null;
};

const exactMatch = computed(() => {
  const q = query.value.trim().toLowerCase();
  return q && props.teams.some(t => (t.name || '').toLowerCase() === q);
});

const options = computed(() => {
  const opts = matches.value.map(team => ({ kind: 'team', team }));
  if (props.allowCreate && query.value.trim() && !exactMatch.value) {
    opts.push({ kind: 'create' });
  }
  return opts;
});

const teamLabel = team =>
  props.labelFormatter ? props.labelFormatter(team) : team.name;

const getOptionId = opt => (opt.kind === 'create' ? CREATE_ID : opt.team.id);
const getOptionLabel = opt =>
  opt.kind === 'create' ? query.value.trim() : teamLabel(opt.team);
const getOptionTestId = opt => (opt.kind === 'create' ? 'create' : 'option');

const onSelect = id => {
  if (id === CREATE_ID) {
    emit('update:modelValue', null);
    emit('update:createName', query.value.trim());
  } else {
    emit('update:createName', '');
    emit('update:modelValue', id);
  }
};

// Parent resets (new form) clear the visible text too — but only once the
// list is closed, so this can't stomp on text the user is mid-typing (typing
// already clears both modelValue and createName one keystroke at a time).
watch(
  () => [props.modelValue, props.createName],
  ([id, name]) => {
    if (id == null && !name && !searchSelectRef.value?.isOpen()) {
      searchSelectRef.value?.clear();
    }
  }
);

defineExpose({ focus: () => searchSelectRef.value?.focus() });
</script>
