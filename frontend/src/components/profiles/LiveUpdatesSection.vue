<template>
  <div
    v-if="authStore.state.profile?.team_id || authStore.state.profile?.club_id"
    id="live-updates-section"
    class="live-updates-section"
  >
    <h3 class="section-title">Live Match Updates</h3>
    <p class="section-desc">
      Get goal alerts and follow your team live. Enter your handle and request
      access — an admin will add you to the channel.
    </p>

    <div class="platforms">
      <!-- Telegram -->
      <div class="platform-item">
        <div class="platform-header">
          <span class="platform-name">✈️ Telegram</span>
          <span
            :class="statusClass(channelAccess.telegram_status)"
            class="status-pill"
          >
            {{ statusLabel(channelAccess.telegram_status) }}
          </span>
        </div>
        <div
          v-if="channelAccess.telegram_status === 'approved'"
          class="approved-msg"
        >
          Added to channel as @{{ authStore.state.profile.telegram_handle }}
        </div>
        <div v-else>
          <div class="input-row">
            <input
              v-model="telegramHandle"
              type="text"
              placeholder="@yourusername"
              class="handle-input"
              :disabled="channelAccess.telegram_status === 'pending'"
            />
            <button
              v-if="channelAccess.telegram_status !== 'pending'"
              @click="request('telegram')"
              :disabled="
                !telegramHandle.trim() || requestingChannel === 'telegram'
              "
              class="request-btn"
            >
              {{
                requestingChannel === 'telegram'
                  ? 'Requesting...'
                  : 'Request Access'
              }}
            </button>
          </div>
          <p
            v-if="channelAccess.telegram_status === 'pending'"
            class="status-msg"
          >
            Request pending — an admin will add you to the channel.
          </p>
          <p
            v-if="channelAccess.telegram_status === 'denied'"
            class="status-msg denied"
          >
            Request denied. Update your handle and try again.
          </p>
        </div>
      </div>

      <!-- Discord -->
      <div class="platform-item">
        <div class="platform-header">
          <span class="platform-name">🎮 Discord</span>
          <span
            :class="statusClass(channelAccess.discord_status)"
            class="status-pill"
          >
            {{ statusLabel(channelAccess.discord_status) }}
          </span>
        </div>
        <div
          v-if="channelAccess.discord_status === 'approved'"
          class="approved-msg"
        >
          Added to server as {{ authStore.state.profile.discord_handle }}
        </div>
        <div v-else>
          <div class="input-row">
            <input
              v-model="discordHandle"
              type="text"
              placeholder="username or username#0000"
              class="handle-input"
              :disabled="channelAccess.discord_status === 'pending'"
            />
            <button
              v-if="channelAccess.discord_status !== 'pending'"
              @click="request('discord')"
              :disabled="
                !discordHandle.trim() || requestingChannel === 'discord'
              "
              class="request-btn"
            >
              {{
                requestingChannel === 'discord'
                  ? 'Requesting...'
                  : 'Request Access'
              }}
            </button>
          </div>
          <p
            v-if="channelAccess.discord_status === 'pending'"
            class="status-msg"
          >
            Request pending — an admin will add you to the server.
          </p>
          <p
            v-if="channelAccess.discord_status === 'denied'"
            class="status-msg denied"
          >
            Request denied. Update your handle and try again.
          </p>
        </div>
      </div>
    </div>

    <p v-if="requestError" class="error-msg">{{ requestError }}</p>
  </div>
</template>

<script>
import { ref, watch, onMounted } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';

export default {
  name: 'LiveUpdatesSection',
  setup() {
    const authStore = useAuthStore();

    const telegramHandle = ref('');
    const discordHandle = ref('');
    const channelAccess = ref({
      telegram_status: 'none',
      discord_status: 'none',
    });
    const requestingChannel = ref(null);
    const requestError = ref('');

    const statusLabel = status =>
      ({
        none: 'Not requested',
        pending: 'Pending',
        approved: 'Added',
        denied: 'Denied',
      })[status] || status;

    const statusClass = status => ({
      'pill-none': status === 'none',
      'pill-pending': status === 'pending',
      'pill-approved': status === 'approved',
      'pill-denied': status === 'denied',
    });

    const populateHandles = () => {
      telegramHandle.value = authStore.state.profile?.telegram_handle || '';
      discordHandle.value = authStore.state.profile?.discord_handle || '';
    };

    const fetchChannelAccess = async () => {
      if (
        !authStore.state.profile?.team_id &&
        !authStore.state.profile?.club_id
      )
        return;
      populateHandles();
      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/channel-requests/me`
        );
        if (response && !response.error) {
          channelAccess.value.telegram_status =
            response.telegram_status || 'none';
          channelAccess.value.discord_status =
            response.discord_status || 'none';
          if (response.telegram_handle)
            telegramHandle.value = response.telegram_handle;
          if (response.discord_handle)
            discordHandle.value = response.discord_handle;
        }
      } catch {
        // 404 = no request yet, that's fine
      }
    };

    const request = async platform => {
      requestError.value = '';
      requestingChannel.value = platform;
      try {
        const handle =
          platform === 'telegram'
            ? telegramHandle.value.trim()
            : discordHandle.value.trim();
        const response = await fetch(
          `${getApiBaseUrl()}/api/channel-requests`,
          {
            method: 'POST',
            headers: {
              ...authStore.getAuthHeaders(),
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              [platform]: true,
              [`${platform}_handle`]: handle,
            }),
          }
        );
        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Failed to submit request');
        }
        await fetchChannelAccess();
      } catch (err) {
        requestError.value = err.message;
      } finally {
        requestingChannel.value = null;
      }
    };

    watch(
      () => authStore.state.profile,
      () => populateHandles(),
      { immediate: true }
    );

    onMounted(fetchChannelAccess);

    return {
      authStore,
      telegramHandle,
      discordHandle,
      channelAccess,
      requestingChannel,
      requestError,
      statusLabel,
      statusClass,
      request,
    };
  },
};
</script>

<style scoped>
.live-updates-section {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 12px;
  padding: 20px;
  margin-top: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: #0369a1;
  margin: 0 0 6px 0;
}

.section-desc {
  font-size: 13px;
  color: #475569;
  margin: 0 0 16px 0;
  line-height: 1.5;
}

.platforms {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.platform-item {
  background: white;
  border: 1px solid #e0f2fe;
  border-radius: 8px;
  padding: 14px;
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.platform-name {
  font-weight: 600;
  font-size: 14px;
  color: #1e293b;
}

.status-pill {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}
.pill-none {
  background: #f1f5f9;
  color: #94a3b8;
}
.pill-pending {
  background: #fef9c3;
  color: #a16207;
}
.pill-approved {
  background: #dcfce7;
  color: #15803d;
}
.pill-denied {
  background: #fee2e2;
  color: #dc2626;
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.handle-input {
  flex: 1;
  padding: 7px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
}

.handle-input:disabled {
  background: #f9fafb;
  color: #9ca3af;
}

.request-btn {
  padding: 7px 14px;
  background: #0ea5e9;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.request-btn:hover:not(:disabled) {
  background: #0284c7;
}

.request-btn:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

.approved-msg {
  font-size: 13px;
  color: #15803d;
  font-weight: 600;
}

.status-msg {
  font-size: 12px;
  color: #64748b;
  margin: 6px 0 0;
  font-style: italic;
}

.status-msg.denied {
  color: #dc2626;
}

.error-msg {
  font-size: 13px;
  color: #dc2626;
  margin-top: 10px;
}
</style>
