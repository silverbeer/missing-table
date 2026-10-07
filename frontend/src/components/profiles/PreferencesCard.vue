<template>
  <section class="preferences-card" data-testid="preferences-card">
    <header class="preferences-header">
      <h3>Preferences</h3>
      <p class="preferences-subhead">
        Saved to your account, so they follow you to every device.
      </p>
    </header>

    <div class="preference-row">
      <label for="default-age-group" class="preference-label">
        Default age group
      </label>
      <p class="preference-help">
        Table and Matches open on this age group. Picking a different one on
        those pages still sticks there.
      </p>
      <select
        id="default-age-group"
        v-model="selected"
        class="preference-select"
        data-testid="default-age-group-select"
        :disabled="saving || loadFailed"
        @change="save"
      >
        <option value="">{{ automaticLabel }}</option>
        <option v-for="ag in ageGroups" :key="ag.id" :value="String(ag.id)">
          {{ ag.name }}
        </option>
      </select>
      <p
        v-if="status"
        class="preference-status"
        :class="{ 'is-error': statusIsError }"
        role="status"
        data-testid="preference-status"
      >
        {{ status }}
      </p>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '@/config/api';
import { useFilterMemory } from '@/composables/useFilterMemory';

const authStore = useAuthStore();

const ageGroups = ref([]);
const loadFailed = ref(false);
const saving = ref(false);
const status = ref('');
const statusIsError = ref(false);

// '' = no preference. Kept as a string so the empty option compares cleanly.
const toSelected = id => (id === null || id === undefined ? '' : String(id));
const selected = ref(toSelected(authStore.preferredAgeGroupId?.value));

watch(
  () => authStore.preferredAgeGroupId?.value,
  id => {
    if (!saving.value) selected.value = toSelected(id);
  }
);

// Say what "automatic" resolves to, so the empty option is not a mystery.
const automaticLabel = computed(() => {
  const teamAgeGroup = authStore.userAgeGroupId?.value;
  const name = ageGroups.value.find(ag => ag.id === teamAgeGroup)?.name;
  return name ? `Automatic (my team: ${name})` : 'Automatic (U14)';
});

// Same per-viewer key the Table and Matches tabs use.
const userKey = () =>
  authStore.state?.profile?.id ?? authStore.state?.user?.id ?? null;

const save = async () => {
  saving.value = true;
  status.value = '';
  const id = selected.value === '' ? null : Number(selected.value);
  const result = await authStore.updatePreferences({
    default_age_group_id: id,
  });
  saving.value = false;

  if (result.success) {
    // Last pick wins, so a remembered pick would hide the new preference on
    // this device. Drop it here so the change shows on the next visit.
    useFilterMemory('table', userKey).clear();
    useFilterMemory('matches', userKey).clear();
    statusIsError.value = false;
    status.value = 'Saved';
  } else {
    selected.value = toSelected(authStore.preferredAgeGroupId?.value);
    statusIsError.value = true;
    status.value = result.error || 'Could not save. Please try again.';
  }
};

onMounted(async () => {
  try {
    const data = await authStore.apiRequest(
      `${getApiBaseUrl()}/api/age-groups`
    );
    ageGroups.value = [...data].sort((a, b) => a.name.localeCompare(b.name));
  } catch (err) {
    console.error('Error fetching age groups:', err);
    loadFailed.value = true;
    statusIsError.value = true;
    status.value = 'Age groups could not be loaded.';
  }
});
</script>

<style scoped>
.preferences-card {
  background: rgb(var(--color-card));
  border: 1px solid rgb(var(--color-line));
  border-radius: 12px;
  padding: 20px;
  margin-top: 24px;
}

.preferences-header h3 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
  color: rgb(var(--color-fg));
}

.preferences-subhead {
  margin: 0 0 16px;
  font-size: 14px;
  color: rgb(var(--color-fg-muted));
  line-height: 1.4;
}

.preference-label {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--color-fg));
}

.preference-help {
  margin: 4px 0 10px;
  font-size: 13px;
  color: rgb(var(--color-fg-muted));
  line-height: 1.4;
}

.preference-select {
  width: 100%;
  max-width: 320px;
  min-height: 44px; /* touch target */
  padding: 0 12px;
  border: 1px solid rgb(var(--color-line));
  border-radius: 8px;
  background: rgb(var(--color-card));
  color: rgb(var(--color-fg));
  font-size: 16px; /* 16px stops iOS zooming on focus */
}

.preference-status {
  margin: 8px 0 0;
  font-size: 13px;
  color: rgb(var(--color-fg-muted));
}

.preference-status.is-error {
  color: #b91c1c;
}
</style>
