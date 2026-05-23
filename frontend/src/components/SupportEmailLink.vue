<template>
  <a
    :href="mailtoHref"
    class="support-email-link"
    data-testid="support-email-link"
  >
    {{ displayText || address }}
  </a>
</template>

<script setup>
import { computed } from 'vue';

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
const SUPPORT_DOMAIN = 'missingtable.com';
const address = `${SUPPORT_USER}@${SUPPORT_DOMAIN}`;

const mailtoHref = computed(() => {
  const params = [];
  if (props.subject)
    params.push(`subject=${encodeURIComponent(props.subject)}`);
  if (props.body) params.push(`body=${encodeURIComponent(props.body)}`);
  const query = params.length ? `?${params.join('&')}` : '';
  return `mailto:${address}${query}`;
});
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
</style>
