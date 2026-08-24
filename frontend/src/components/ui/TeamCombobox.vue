<template>
  <div class="relative" @keydown.escape.stop="close">
    <input
      ref="inputEl"
      v-model="query"
      type="text"
      role="combobox"
      aria-autocomplete="list"
      :aria-expanded="open"
      :aria-controls="listId"
      :placeholder="placeholder"
      :required="required && selectedTeamId == null && !createName"
      data-testid="team-combobox-input"
      class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
      @focus="open = true"
      @input="onInput"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.enter.prevent="choose(options[activeIndex])"
    />

    <!-- Selected / pending-create state, so the choice is visible after the
         list closes and the input just shows text. -->
    <p
      v-if="selectedTeam"
      class="text-xs text-emerald-600 dark:text-emerald-400 mt-1"
      data-testid="team-combobox-selected"
    >
      ✓ {{ selectedTeam.name
      }}{{ badgeFor(selectedTeam) ? ` · ${badgeFor(selectedTeam)}` : '' }}
    </p>
    <p
      v-else-if="createName"
      class="text-xs text-amber-600 dark:text-amber-400 mt-1"
      data-testid="team-combobox-create-pending"
    >
      ＋ Will create new team “{{ createName }}”
    </p>

    <ul
      v-if="open && options.length"
      :id="listId"
      role="listbox"
      data-testid="team-combobox-list"
      class="absolute z-20 mt-1 w-full max-h-64 overflow-auto bg-card border border-line rounded-md shadow-lg"
    >
      <li
        v-for="(opt, i) in options"
        :key="opt.kind === 'create' ? '__create__' : opt.team.id"
        role="option"
        :aria-selected="i === activeIndex"
        :data-testid="
          opt.kind === 'create'
            ? 'team-combobox-create'
            : 'team-combobox-option'
        "
        class="px-3 py-2 cursor-pointer flex items-center justify-between gap-2"
        :class="
          i === activeIndex
            ? 'bg-brand-50 dark:bg-brand-500/15'
            : 'hover:bg-line/40'
        "
        @mousedown.prevent="choose(opt)"
        @mouseenter="activeIndex = i"
      >
        <template v-if="opt.kind === 'create'">
          <span class="text-sm text-fg"
            >＋ Create new team “{{ query.trim() }}”</span
          >
        </template>
        <template v-else>
          <span class="text-sm text-fg truncate">{{ opt.team.name }}</span>
          <span
            v-if="badgeFor(opt.team)"
            class="text-xs px-1.5 py-0.5 rounded shrink-0"
            :class="
              badgeFor(opt.team) === 'tournament'
                ? 'bg-line/60 text-fg-muted'
                : 'bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300'
            "
          >
            {{ badgeFor(opt.team) }}
          </span>
        </template>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

/**
 * Team picker with type-ahead (SB-817).
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
});

const emit = defineEmits(['update:modelValue', 'update:createName']);

const query = ref('');
const open = ref(false);
const activeIndex = ref(0);
const inputEl = ref(null);
const listId = `team-combobox-${Math.random().toString(36).slice(2, 9)}`;

const selectedTeamId = computed(() => props.modelValue);
const selectedTeam = computed(
  () => props.teams.find(t => t.id === props.modelValue) || null
);

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

watch(options, () => {
  if (activeIndex.value >= options.value.length) activeIndex.value = 0;
});

// Typing invalidates any prior choice — otherwise an edited name would submit
// against the team picked before the edit.
const onInput = () => {
  open.value = true;
  activeIndex.value = 0;
  if (props.modelValue != null) emit('update:modelValue', null);
  if (props.createName) emit('update:createName', '');
};

const move = delta => {
  if (!open.value) {
    open.value = true;
    return;
  }
  const n = options.value.length;
  if (!n) return;
  activeIndex.value = (activeIndex.value + delta + n) % n;
};

const choose = opt => {
  if (!opt) return;
  if (opt.kind === 'create') {
    emit('update:modelValue', null);
    emit('update:createName', query.value.trim());
  } else {
    query.value = opt.team.name;
    emit('update:createName', '');
    emit('update:modelValue', opt.team.id);
  }
  open.value = false;
};

const close = () => {
  open.value = false;
};

// Parent resets (new form) clear the visible text too.
watch(
  () => [props.modelValue, props.createName],
  ([id, name]) => {
    if (id == null && !name && !open.value) query.value = '';
  }
);

defineExpose({ focus: () => inputEl.value?.focus() });
</script>
