<template>
  <div>
    <!-- Selected positions, in priority order -->
    <div v-if="selected.length > 0" class="flex flex-wrap gap-1 mb-2">
      <span
        v-for="(code, index) in selected"
        :key="code"
        class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-brand-100 text-brand-800"
      >
        {{ code }}
        <span
          v-if="index === 0"
          class="px-1 rounded bg-brand-600 text-white text-[10px] uppercase"
          >Primary</span
        >
        <button
          type="button"
          class="ml-0.5 text-brand-600 hover:text-brand-900"
          :aria-label="`Remove ${code}`"
          @click="toggle(code)"
        >
          &times;
        </button>
      </span>
    </div>
    <p v-else class="text-xs text-fg-muted mb-2">
      No positions selected. First pick becomes the primary position.
    </p>

    <!-- Grouped picker -->
    <div class="space-y-2">
      <div v-for="(codes, group) in positionGroups" :key="group">
        <div class="text-xs font-semibold text-fg-muted uppercase mb-1">
          {{ groupNames[group] }}
        </div>
        <div class="flex flex-wrap gap-1">
          <button
            v-for="code in codes"
            :key="code"
            type="button"
            class="px-2 py-1 rounded text-xs border"
            :class="
              selected.includes(code)
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-card text-fg border-line hover:bg-surface-alt'
            "
            @click="toggle(code)"
          >
            {{ code }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch } from 'vue';
import { GROUP_NAMES, POSITION_GROUPS } from '@/constants/positions';

export default {
  name: 'PositionPicker',
  props: {
    // Ordered array of position codes; index 0 = primary.
    modelValue: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    // Internal copy so rapid toggles don't read a stale prop (the parent's
    // v-model update lands asynchronously).
    const selected = ref([...props.modelValue]);
    watch(
      () => props.modelValue,
      value => {
        if (JSON.stringify(value) !== JSON.stringify(selected.value)) {
          selected.value = [...value];
        }
      }
    );

    const toggle = code => {
      selected.value = selected.value.includes(code)
        ? selected.value.filter(c => c !== code)
        : [...selected.value, code];
      emit('update:modelValue', [...selected.value]);
    };

    return {
      positionGroups: POSITION_GROUPS,
      groupNames: GROUP_NAMES,
      selected,
      toggle,
    };
  },
};
</script>
