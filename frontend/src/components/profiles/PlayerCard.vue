<template>
  <div
    class="player-card"
    :style="cardStyle"
    @click="$emit('click', player)"
    role="button"
    tabindex="0"
    @keydown.enter="$emit('click', player)"
    @keydown.space.prevent="$emit('click', player)"
  >
    <!-- Photo with overlay -->
    <div class="card-photo">
      <PlayerPhotoOverlay
        :photoUrl="profilePhotoUrl"
        :number="player.player_number"
        :position="primaryPosition"
        :overlayStyle="effectiveOverlayStyle"
        :primaryColor="effectivePrimaryColor"
        :textColor="effectiveTextColor"
        :accentColor="effectiveAccentColor"
        :altText="`${displayName} profile photo`"
      />
    </div>

    <!-- Player info -->
    <div class="card-info">
      <div class="player-name">{{ displayName }}</div>
      <div v-if="secondaryInfo" class="player-secondary">
        {{ secondaryInfo }}
      </div>

      <!-- Social media icons -->
      <div v-if="hasSocialMedia" class="social-icons">
        <a
          v-if="player.instagram_handle"
          :href="`https://instagram.com/${player.instagram_handle}`"
          target="_blank"
          rel="noopener noreferrer"
          class="social-icon instagram"
          @click.stop
          :title="`@${player.instagram_handle}`"
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path
              d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"
            />
          </svg>
        </a>
        <a
          v-if="player.snapchat_handle"
          :href="`https://snapchat.com/add/${player.snapchat_handle}`"
          target="_blank"
          rel="noopener noreferrer"
          class="social-icon snapchat"
          @click.stop
          :title="`@${player.snapchat_handle}`"
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path
              d="M12.166 2c1.34.006 2.613.139 3.49.476.96.369 1.715.984 2.285 1.794.548.779.86 1.728.98 2.979.066.69.068 1.43.068 2.21v.242c.002.4.004.775.038 1.172.043.498.13.805.286 1.048.13.203.342.395.749.584.16.074.33.143.52.22l.18.073c.5.2.87.37 1.138.557.404.28.567.563.567.813s-.163.533-.567.813c-.268.187-.638.357-1.138.557l-.18.073c-.19.077-.36.146-.52.22-.407.189-.619.381-.749.584-.156.243-.243.55-.286 1.048-.034.397-.036.772-.038 1.172v.242c0 .78-.002 1.52-.068 2.21-.12 1.251-.432 2.2-.98 2.979-.57.81-1.325 1.425-2.285 1.794-.877.337-2.15.47-3.49.476h-.332c-1.34-.006-2.613-.139-3.49-.476-.96-.369-1.715-.984-2.285-1.794-.548-.779-.86-1.728-.98-2.979-.066-.69-.068-1.43-.068-2.21v-.242c-.002-.4-.004-.775-.038-1.172-.043-.498-.13-.805-.286-1.048-.13-.203-.342-.395-.749-.584-.16-.074-.33-.143-.52-.22l-.18-.073c-.5-.2-.87-.37-1.138-.557-.404-.28-.567-.563-.567-.813s.163-.533.567-.813c.268-.187.638-.357 1.138-.557l.18-.073c.19-.077.36-.146.52-.22.407-.189.619-.381.749-.584.156-.243.243-.55.286-1.048.034-.397.036-.772.038-1.172v-.242c0-.78.002-1.52.068-2.21.12-1.251.432-2.2.98-2.979.57-.81 1.325-1.425 2.285-1.794.877-.337 2.15-.47 3.49-.476z"
            />
          </svg>
        </a>
        <a
          v-if="player.tiktok_handle"
          :href="`https://tiktok.com/@${player.tiktok_handle}`"
          target="_blank"
          rel="noopener noreferrer"
          class="social-icon tiktok"
          @click.stop
          :title="`@${player.tiktok_handle}`"
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path
              d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.05A6.33 6.33 0 0 0 5 20.1a6.34 6.34 0 0 0 10.86-4.43v-7a8.16 8.16 0 0 0 4.77 1.52v-3.4a4.85 4.85 0 0 1-1-.1z"
            />
          </svg>
        </a>
      </div>
    </div>
  </div>
</template>

<script>
import { computed } from 'vue';
import PlayerPhotoOverlay from './PlayerPhotoOverlay.vue';

export default {
  name: 'PlayerCard',
  components: {
    PlayerPhotoOverlay,
  },
  props: {
    player: {
      type: Object,
      required: true,
    },
    clubColor: {
      type: String,
      default: null,
    },
    // Override colors for team roster view (use club colors instead of player's choice)
    overlayPrimaryColor: {
      type: String,
      default: null,
    },
    overlayTextColor: {
      type: String,
      default: null,
    },
    overlayAccentColor: {
      type: String,
      default: null,
    },
    // Override overlay style for consistent team roster view
    overlayStyleOverride: {
      type: String,
      default: null,
    },
  },
  emits: ['click'],
  setup(props) {
    // Get the profile photo URL based on profile_photo_slot
    const profilePhotoUrl = computed(() => {
      const slot = props.player.profile_photo_slot || 1;
      return props.player[`photo_${slot}_url`] || null;
    });

    // Get display name (fallback to "Player")
    const displayName = computed(() => {
      return props.player.display_name || 'Player';
    });

    // Get primary position (first in array)
    const primaryPosition = computed(() => {
      const positions = props.player.positions;
      if (Array.isArray(positions) && positions.length > 0) {
        return positions[0];
      }
      return null;
    });

    // Secondary info line - just positions (number is shown in overlay)
    const secondaryInfo = computed(() => {
      const positions = props.player.positions;
      if (Array.isArray(positions) && positions.length > 0) {
        return positions.join(', ');
      }
      return null;
    });

    // Check if player has any social media handles
    const hasSocialMedia = computed(() => {
      return (
        props.player.instagram_handle ||
        props.player.snapchat_handle ||
        props.player.tiktok_handle
      );
    });

    // Card style with club color border
    const cardStyle = computed(() => {
      if (props.clubColor) {
        return {
          border: `3px solid ${props.clubColor}`,
        };
      }
      return {};
    });

    // Overlay colors - use override props if provided, otherwise player's choice
    const effectivePrimaryColor = computed(() => {
      return (
        props.overlayPrimaryColor || props.player.primary_color || '#3B82F6'
      );
    });

    const effectiveTextColor = computed(() => {
      return props.overlayTextColor || props.player.text_color || '#FFFFFF';
    });

    const effectiveAccentColor = computed(() => {
      return props.overlayAccentColor || props.player.accent_color || '#1D4ED8';
    });

    const effectiveOverlayStyle = computed(() => {
      return (
        props.overlayStyleOverride || props.player.overlay_style || 'badge'
      );
    });

    return {
      profilePhotoUrl,
      displayName,
      primaryPosition,
      secondaryInfo,
      hasSocialMedia,
      cardStyle,
      effectivePrimaryColor,
      effectiveTextColor,
      effectiveAccentColor,
      effectiveOverlayStyle,
    };
  },
};
</script>

<style scoped>
.player-card {
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
  /* Touch-friendly: entire card is tappable */
  min-height: 44px;
}

.player-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.player-card:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

.player-card:active {
  transform: translateY(0);
}

.card-photo {
  width: 100%;
  /* Square aspect ratio handled by PlayerPhotoOverlay */
}

.card-info {
  padding: 12px;
  text-align: center;
}

.player-name {
  font-weight: 600;
  font-size: 16px;
  color: #1f2937;
  margin-bottom: 4px;
  /* Truncate long names */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.player-secondary {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.social-icons {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 8px;
}

.social-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition:
    transform 0.15s ease,
    background-color 0.15s ease;
  /* Touch-friendly minimum size */
  min-width: 44px;
  min-height: 44px;
}

.social-icon svg {
  width: 18px;
  height: 18px;
}

.social-icon.instagram {
  color: #e4405f;
}

.social-icon.instagram:hover {
  background-color: rgba(228, 64, 95, 0.1);
  transform: scale(1.1);
}

.social-icon.snapchat {
  color: #fffc00;
  /* Add background for visibility on white */
  background-color: rgba(0, 0, 0, 0.8);
  border-radius: 50%;
}

.social-icon.snapchat:hover {
  background-color: rgba(0, 0, 0, 0.9);
  transform: scale(1.1);
}

.social-icon.tiktok {
  color: #000000;
}

.social-icon.tiktok:hover {
  background-color: rgba(0, 0, 0, 0.1);
  transform: scale(1.1);
}

/* Mobile-first responsive adjustments */
@media (max-width: 480px) {
  .player-card {
    border-radius: 12px;
  }

  .card-info {
    padding: 10px;
  }

  .player-name {
    font-size: 14px;
  }

  .player-secondary {
    font-size: 12px;
  }

  .social-icons {
    gap: 8px;
  }

  .social-icon {
    min-width: 40px;
    min-height: 40px;
  }

  .social-icon svg {
    width: 16px;
    height: 16px;
  }
}
</style>
