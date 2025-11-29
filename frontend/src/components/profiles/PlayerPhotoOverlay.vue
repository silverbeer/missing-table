<template>
  <div class="player-photo-overlay" :class="overlayStyle">
    <!-- Photo container -->
    <div class="photo-container">
      <img
        v-if="photoUrl"
        :src="photoUrl"
        :alt="altText"
        class="player-photo"
        @error="handleImageError"
      />
      <div v-else class="photo-placeholder">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.5"
            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
          />
        </svg>
      </div>
    </div>

    <!-- Badge Style Overlay -->
    <div
      v-if="overlayStyle === 'badge' && hasOverlayContent"
      class="badge-overlay"
    >
      <div
        v-if="number"
        class="badge-number"
        :style="{ backgroundColor: primaryColor, color: textColor }"
      >
        {{ number }}
      </div>
      <div
        v-if="position"
        class="badge-position"
        :style="{ backgroundColor: accentColor, color: textColor }"
      >
        {{ position }}
      </div>
    </div>

    <!-- Jersey Style Overlay -->
    <div
      v-if="overlayStyle === 'jersey' && hasOverlayContent"
      class="jersey-overlay"
    >
      <div
        class="jersey-number"
        :style="{
          color: primaryColor,
          textShadow: `2px 2px 0 ${accentColor}, -2px -2px 0 ${accentColor}, 2px -2px 0 ${accentColor}, -2px 2px 0 ${accentColor}`,
        }"
      >
        {{ number || '?' }}
      </div>
      <div
        v-if="position"
        class="jersey-position"
        :style="{ backgroundColor: primaryColor, color: textColor }"
      >
        {{ position }}
      </div>
    </div>

    <!-- Caption Style Overlay -->
    <div
      v-if="overlayStyle === 'caption' && hasOverlayContent"
      class="caption-overlay"
      :style="{ backgroundColor: primaryColor }"
    >
      <span v-if="number" class="caption-number" :style="{ color: textColor }">
        #{{ number }}
      </span>
      <span
        v-if="number && position"
        class="caption-divider"
        :style="{ color: textColor }"
      >
        |
      </span>
      <span
        v-if="position"
        class="caption-position"
        :style="{ color: textColor }"
      >
        {{ position }}
      </span>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue';

export default {
  name: 'PlayerPhotoOverlay',
  props: {
    photoUrl: {
      type: String,
      default: null,
    },
    number: {
      type: [String, Number],
      default: null,
    },
    position: {
      type: String,
      default: null,
    },
    overlayStyle: {
      type: String,
      default: 'badge',
      validator: value =>
        ['badge', 'jersey', 'caption', 'none'].includes(value),
    },
    primaryColor: {
      type: String,
      default: '#3B82F6',
    },
    textColor: {
      type: String,
      default: '#FFFFFF',
    },
    accentColor: {
      type: String,
      default: '#1D4ED8',
    },
    altText: {
      type: String,
      default: 'Player photo',
    },
  },
  setup(props) {
    const hasOverlayContent = computed(() => {
      return props.number || props.position;
    });

    const handleImageError = event => {
      // Replace broken image with placeholder
      event.target.style.display = 'none';
      const placeholder =
        event.target.parentElement.querySelector('.photo-placeholder');
      if (placeholder) {
        placeholder.style.display = 'flex';
      }
    };

    return {
      hasOverlayContent,
      handleImageError,
    };
  },
};
</script>

<style scoped>
.player-photo-overlay {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  background-color: #f3f4f6;
}

.photo-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.player-photo {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #e5e7eb;
  color: #9ca3af;
}

.photo-placeholder svg {
  width: 40%;
  height: 40%;
}

/* Badge Style */
.badge-overlay {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.badge-number {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.badge-position {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

/* Jersey Style */
.jersey-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.jersey-number {
  font-size: 72px;
  font-weight: 900;
  line-height: 1;
  font-family: 'Impact', 'Arial Black', sans-serif;
  letter-spacing: -2px;
}

.jersey-position {
  margin-top: 8px;
  padding: 6px 16px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

/* Caption Style */
.caption-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.caption-number {
  font-weight: 700;
  font-size: 16px;
}

.caption-divider {
  opacity: 0.6;
}

.caption-position {
  font-weight: 600;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* None style - no overlay */
.player-photo-overlay.none .badge-overlay,
.player-photo-overlay.none .jersey-overlay,
.player-photo-overlay.none .caption-overlay {
  display: none;
}

/* Responsive adjustments */
@media (max-width: 480px) {
  .badge-number {
    width: 32px;
    height: 32px;
    font-size: 14px;
  }

  .badge-position {
    font-size: 10px;
    padding: 3px 8px;
  }

  .jersey-number {
    font-size: 48px;
  }

  .jersey-position {
    font-size: 12px;
    padding: 4px 12px;
  }

  .caption-overlay {
    padding: 8px 12px;
  }

  .caption-number {
    font-size: 14px;
  }

  .caption-position {
    font-size: 12px;
  }
}
</style>
