<template>
  <div class="color-palette">
    <label v-if="label" class="palette-label">{{ label }}</label>
    <div class="color-grid">
      <button
        v-for="color in colors"
        :key="color"
        type="button"
        class="color-swatch"
        :class="{ selected: modelValue === color }"
        :style="{ backgroundColor: color }"
        :title="color"
        @click="selectColor(color)"
      >
        <span v-if="modelValue === color" class="check-mark">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            />
          </svg>
        </span>
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ColorPalette',
  props: {
    modelValue: {
      type: String,
      default: '#3B82F6',
    },
    label: {
      type: String,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    // 16 preset colors organized by hue
    const colors = [
      // Blues
      '#3B82F6', // Blue 500
      '#1D4ED8', // Blue 700
      '#0EA5E9', // Sky 500
      '#06B6D4', // Cyan 500
      // Greens
      '#22C55E', // Green 500
      '#10B981', // Emerald 500
      '#14B8A6', // Teal 500
      // Warm colors
      '#EF4444', // Red 500
      '#DC2626', // Red 600
      '#F97316', // Orange 500
      '#F59E0B', // Amber 500
      // Purples
      '#8B5CF6', // Violet 500
      '#A855F7', // Purple 500
      '#EC4899', // Pink 500
      // Neutrals
      '#FFFFFF', // White
      '#000000', // Black
    ];

    const selectColor = color => {
      emit('update:modelValue', color);
    };

    return {
      colors,
      selectColor,
    };
  },
};
</script>

<style scoped>
.color-palette {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.palette-label {
  font-weight: 600;
  color: #374151;
  font-size: 14px;
}

.color-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 8px;
}

@media (max-width: 480px) {
  .color-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

.color-swatch {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  border: 2px solid transparent;
  cursor: pointer;
  position: relative;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.color-swatch:hover {
  transform: scale(1.1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.color-swatch.selected {
  border-color: #1f2937;
  box-shadow:
    0 0 0 2px white,
    0 0 0 4px #1f2937;
}

/* White swatch needs a visible border */
.color-swatch[style*='#FFFFFF'],
.color-swatch[style*='white'] {
  border-color: #e5e7eb;
}

.color-swatch.selected[style*='#FFFFFF'],
.color-swatch.selected[style*='white'] {
  border-color: #1f2937;
}

.check-mark {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.check-mark svg {
  width: 14px;
  height: 14px;
}

/* Dark colors get white checkmark */
.color-swatch[style*='#1D4ED8'] .check-mark,
.color-swatch[style*='#DC2626'] .check-mark,
.color-swatch[style*='#000000'] .check-mark,
.color-swatch[style*='#8B5CF6'] .check-mark,
.color-swatch[style*='#A855F7'] .check-mark {
  color: white;
}

/* Light colors get dark checkmark */
.color-swatch[style*='#FFFFFF'] .check-mark,
.color-swatch[style*='#F59E0B'] .check-mark,
.color-swatch[style*='#22C55E'] .check-mark,
.color-swatch[style*='#0EA5E9'] .check-mark {
  color: #1f2937;
}

/* Default checkmark color based on luminance */
.check-mark {
  color: white;
}
</style>
