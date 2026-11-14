<template>
  <form
    v-if="form"
    class="channel-form"
    data-testid="channel-form"
    @submit.prevent="submit"
  >
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="field">
        <span>Platform</span>
        <select
          v-model="form.platform"
          :disabled="editing || busy"
          data-testid="form-platform"
        >
          <option v-for="p in platforms" :key="p.id" :value="p.id">
            {{ p.icon }} {{ p.label }}
          </option>
        </select>
      </label>

      <fieldset v-if="scopeType !== 'global'" class="field">
        <legend>Who it's for</legend>
        <div class="flex gap-4 text-sm text-fg pt-1">
          <label class="inline-flex items-center gap-1.5">
            <input
              v-model="form.audience"
              type="radio"
              value="fans"
              :disabled="editing || busy"
              data-testid="form-audience-fans"
            />
            Fans
          </label>
          <label class="inline-flex items-center gap-1.5">
            <input
              v-model="form.audience"
              type="radio"
              value="players"
              :disabled="editing || busy"
              data-testid="form-audience-players"
            />
            Players
          </label>
        </div>
      </fieldset>
    </div>

    <label class="field">
      <span>Name <em>(optional)</em></span>
      <input
        v-model="form.label"
        maxlength="80"
        :disabled="busy"
        placeholder="e.g. #u15-live or IFA U15 parents"
        data-testid="form-label"
      />
      <small>Only managers see this. It tells your channels apart.</small>
    </label>

    <label class="field">
      <span>{{ destinationLabel }}</span>
      <input
        v-model="form.destination"
        :disabled="busy"
        :placeholder="
          editing
            ? 'Leave blank to keep the current one'
            : platform?.placeholder
        "
        autocomplete="off"
        data-testid="form-destination"
      />
      <small
        v-if="destinationError"
        class="error"
        data-testid="form-destination-error"
      >
        {{ destinationError }}
      </small>
    </label>

    <label class="field">
      <span>Invite link <em>(optional)</em></span>
      <input
        v-model="form.invite_url"
        :disabled="busy"
        placeholder="The link people use to join"
        autocomplete="off"
        data-testid="form-invite"
      />
      <small v-if="inviteError" class="error" data-testid="form-invite-error">
        {{ inviteError }}
      </small>
      <small v-else>
        Shown only to people you approve, or who qualify to join. Anyone who has
        the link can pass it on, so treat the room as open to them.
      </small>
    </label>

    <label
      v-if="threadsOffered"
      class="field inline-flex items-start gap-2 text-sm text-fg"
    >
      <input
        v-model="form.post_as_threads"
        type="checkbox"
        :disabled="busy"
        data-testid="form-threads"
      />
      <span>
        One post per match
        <small class="block">
          For a Discord forum channel: each match gets its own post and its
          updates go into it. Point the webhook at the forum channel itself.
        </small>
      </span>
    </label>

    <fieldset class="field">
      <legend>What to post</legend>
      <div class="flex gap-4 text-sm text-fg pt-1">
        <label class="inline-flex items-center gap-1.5">
          <input
            v-model="form.eventsMode"
            type="radio"
            value="all"
            :disabled="busy"
            data-testid="form-events-all"
          />
          Every match event
        </label>
        <label class="inline-flex items-center gap-1.5">
          <input
            v-model="form.eventsMode"
            type="radio"
            value="some"
            :disabled="busy"
            data-testid="form-events-some"
          />
          Only these
        </label>
      </div>
      <div
        v-if="form.eventsMode === 'some'"
        class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-fg mt-2"
      >
        <label
          v-for="e in offeredEvents"
          :key="e.id"
          class="inline-flex items-center gap-1.5"
        >
          <input
            v-model="form.events"
            type="checkbox"
            :value="e.id"
            :disabled="busy"
            :data-testid="`form-event-${e.id}`"
          />
          {{ e.label }}
        </label>
      </div>
      <small
        v-if="form.eventsMode === 'some' && !form.events.length"
        class="warn"
        data-testid="form-events-none"
      >
        Nothing is selected, so nothing will be posted.
      </small>
    </fieldset>

    <details
      v-if="platform?.setup_steps?.length"
      class="setup"
      :open="!editing"
      data-testid="form-setup"
    >
      <summary>How to set up {{ platform.label }}</summary>
      <ol>
        <li v-for="(step, i) in platform.setup_steps" :key="i">{{ step }}</li>
      </ol>
      <template
        v-if="
          form.audience === 'players' && platform.player_setup_steps?.length
        "
      >
        <p class="setup-sub">For a player channel</p>
        <ol data-testid="form-player-setup">
          <li v-for="(step, i) in platform.player_setup_steps" :key="i">
            {{ step }}
          </li>
        </ol>
      </template>
      <p
        v-if="platform.age_note"
        class="setup-note"
        data-testid="form-age-note"
      >
        {{ platform.age_note }}
      </p>
      <p class="setup-note">
        You own and moderate this room. Missing Table only posts match updates
        to it.
      </p>
      <button
        type="button"
        class="guide-link"
        data-testid="form-open-guide"
        @click="
          emit('open-guide', {
            platform: form.platform,
            audience: form.audience,
          })
        "
      >
        Full guide: permissions, invite links and private rooms
      </button>
    </details>

    <div class="flex gap-2 mt-1">
      <button
        type="submit"
        class="btn primary"
        :disabled="!valid || busy"
        data-testid="form-save"
      >
        {{ busy ? 'Saving…' : editing ? 'Save' : 'Add channel' }}
      </button>
      <button
        type="button"
        class="btn secondary"
        :disabled="busy"
        data-testid="form-cancel"
        @click="emit('cancel')"
      >
        Cancel
      </button>
    </div>
  </form>
</template>

<script setup>
import { computed, watch } from 'vue';

/**
 * Add or edit one notification channel (SB-1605). The parent owns the form
 * object; validation patterns and setup steps come from the platform registry.
 * Platform and audience are fixed once a channel exists.
 */
const form = defineModel({ type: Object, default: null });
const props = defineProps({
  platforms: { type: Array, required: true },
  eventTypes: { type: Array, required: true },
  scopeType: { type: String, required: true },
  editing: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
});
const emit = defineEmits(['submit', 'cancel', 'open-guide']);

const platform = computed(() =>
  props.platforms.find(p => p.id === form.value?.platform)
);

// Match threads (SB-1606): platforms that have them, except a club players
// room, which stays flat.
const threadsOffered = computed(
  () =>
    Boolean(platform.value?.capabilities?.includes('threads')) &&
    !(props.scopeType === 'club' && form.value?.audience === 'players')
);

watch(threadsOffered, offered => {
  if (!offered && form.value) form.value.post_as_threads = false;
});

// Player-only events (SB-1610, e.g. lineup posted) only make sense on a
// squad's player channel; anywhere else they would never be sent.
const playerChannel = computed(
  () => props.scopeType === 'team' && form.value?.audience === 'players'
);

const offeredEvents = computed(() =>
  props.eventTypes.filter(e => !e.player_only || playerChannel.value)
);

watch(playerChannel, isPlayerChannel => {
  if (isPlayerChannel || !form.value?.events) return;
  const playerOnly = new Set(
    props.eventTypes.filter(e => e.player_only).map(e => e.id)
  );
  form.value.events = form.value.events.filter(id => !playerOnly.has(id));
});

const destinationLabel = computed(
  () => platform.value?.destination_label || 'Destination'
);

const matches = (pattern, value) => {
  try {
    return new RegExp(pattern).test(value);
  } catch {
    return true; // the server checks again
  }
};

const destinationError = computed(() => {
  const value = form.value?.destination.trim();
  if (!value || !platform.value) return null;
  return matches(platform.value.destination_pattern, value)
    ? null
    : platform.value.destination_error;
});

const inviteError = computed(() => {
  const value = form.value?.invite_url.trim();
  if (!value || !platform.value?.invite_pattern) return null;
  return matches(platform.value.invite_pattern, value)
    ? null
    : platform.value.invite_error;
});

const valid = computed(() => {
  if (!form.value || !platform.value) return false;
  const hasDestination = Boolean(form.value.destination.trim());
  if (!props.editing && !hasDestination) return false;
  return !destinationError.value && !inviteError.value;
});

const submit = () => {
  if (valid.value) emit('submit');
};
</script>

<style scoped>
.channel-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.75rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8125rem;
  color: rgb(var(--color-fg-muted));
  min-width: 0;
}
.field > span,
.field > legend {
  color: rgb(var(--color-fg));
  font-weight: 500;
}
.field em {
  font-style: normal;
  color: rgb(var(--color-fg-muted));
  font-weight: 400;
}
.field input:not([type='radio']):not([type='checkbox']),
.field select {
  padding: 0.45rem 0.7rem;
  border: 1px solid rgb(var(--color-line));
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  min-width: 0;
}
.field input::placeholder {
  color: rgb(var(--color-fg-muted));
}
.error {
  color: #b91c1c;
}
.warn {
  color: #b45309;
}
.setup {
  font-size: 0.8125rem;
  color: rgb(var(--color-fg-muted));
}
.setup summary {
  cursor: pointer;
  color: rgb(var(--color-fg));
  font-weight: 500;
}
.setup ol {
  margin: 0.5rem 0 0 1.25rem;
  list-style: decimal;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.setup-sub {
  margin: 0.75rem 0 0;
  color: rgb(var(--color-fg));
  font-weight: 500;
}
.setup-note {
  margin: 0.5rem 0 0;
}
.guide-link {
  margin-top: 0.5rem;
  padding: 0;
  background: none;
  border: none;
  color: rgb(37 99 235);
  font-weight: 600;
  font-size: 0.8125rem;
  cursor: pointer;
}
.btn {
  padding: 0.4rem 0.8rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: 1px solid transparent;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.primary {
  background: #2563eb;
  color: #fff;
}
.btn.secondary {
  background: rgb(var(--color-surface-alt));
  color: rgb(var(--color-fg));
  border-color: rgb(var(--color-line));
}

:global(.dark .channel-form .error) {
  color: #fca5a5;
}
:global(.dark .channel-form .warn) {
  color: #fcd34d;
}
</style>
