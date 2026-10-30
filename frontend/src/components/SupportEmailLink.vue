<template>
  <span class="support-email">
    <a
      :href="mailtoHref"
      class="support-email-link"
      data-testid="support-email-link"
    >
      {{ displayText || address }}
    </a>
    <!-- SB-1461: a bare mailto: does nothing on a desktop browser with no mail
         client configured. Give desktop users a webmail compose link and the
         address on the clipboard. Hidden on touch devices, where mailto: opens
         the phone's mail app. -->
    <span class="support-email-fallbacks">
      <a
        :href="gmailHref"
        target="_blank"
        rel="noopener noreferrer"
        class="support-email-action"
        data-testid="support-email-gmail"
      >
        Gmail
      </a>
      <button
        type="button"
        class="support-email-action"
        data-testid="support-email-copy"
        @click="copyAddress"
      >
        {{ copyLabel }}
      </button>
    </span>
    <!-- Clipboard unavailable (insecure context, permission denied): show the
         address so it can be selected by hand. -->
    <span
      v-if="copyFailed"
      class="support-email-address"
      data-testid="support-email-address"
    >
      {{ address }}
    </span>
  </span>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  subject: {
    type: String,
    default: '',
  },
  body: {
    type: String,
    default: '',
  },
  displayText: {
    type: String,
    default: '',
  },
});

const SUPPORT_USER = 'support';
const SUPPORT_DOMAIN = 'contact.missingtable.com';
const address = `${SUPPORT_USER}@${SUPPORT_DOMAIN}`;
const COPIED_RESET_MS = 2000;

const mailtoHref = computed(() => {
  const params = [];
  if (props.subject)
    params.push(`subject=${encodeURIComponent(props.subject)}`);
  if (props.body) params.push(`body=${encodeURIComponent(props.body)}`);
  const query = params.length ? `?${params.join('&')}` : '';
  return `mailto:${address}${query}`;
});

const gmailHref = computed(() => {
  const params = ['view=cm', 'fs=1', `to=${encodeURIComponent(address)}`];
  if (props.subject) params.push(`su=${encodeURIComponent(props.subject)}`);
  if (props.body) params.push(`body=${encodeURIComponent(props.body)}`);
  return `https://mail.google.com/mail/?${params.join('&')}`;
});

const copied = ref(false);
const copyFailed = ref(false);
const copyLabel = computed(() => (copied.value ? 'Copied' : 'Copy address'));

async function copyAddress() {
  try {
    await navigator.clipboard.writeText(address);
    copied.value = true;
    copyFailed.value = false;
    setTimeout(() => {
      copied.value = false;
    }, COPIED_RESET_MS);
  } catch {
    copyFailed.value = true;
  }
}
</script>

<style scoped>
.support-email-link {
  color: #2563eb;
  text-decoration: underline;
  font-weight: 500;
}

.support-email-link:hover {
  color: #1d4ed8;
}

.support-email-fallbacks {
  display: inline-flex;
  gap: 0.5rem;
  margin-left: 0.5rem;
}

.support-email-action {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  font-size: 0.85em;
  color: inherit;
  opacity: 0.8;
  text-decoration: underline;
  cursor: pointer;
}

.support-email-action:hover {
  opacity: 1;
}

.support-email-address {
  margin-left: 0.5rem;
  user-select: all;
}

@media (hover: none) and (pointer: coarse) {
  .support-email-fallbacks {
    display: none;
  }
}
</style>
