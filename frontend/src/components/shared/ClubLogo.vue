<template>
  <div
    v-if="hasLogo || showInitials"
    :class="containerClass"
    :style="containerStyle"
  >
    <!-- Logo image -->
    <img
      v-if="hasLogo"
      :src="logoUrl"
      :alt="`${name} logo`"
      :class="imgClass"
      @error="onImgError"
    />
    <!-- Initials fallback for md/lg/xl when no logo -->
    <span v-else-if="showInitials" :class="initialsClass">
      {{ initial }}
    </span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  logoUrl: {
    type: String,
    default: '',
  },
  name: {
    type: String,
    default: '',
  },
  size: {
    type: String,
    default: 'sm',
    validator: v => ['xs', 'sm', 'md', 'lg', 'xl'].includes(v),
  },
});

const imgFailed = ref(false);

const onImgError = () => {
  imgFailed.value = true;
};

const hasLogo = computed(() => props.logoUrl && !imgFailed.value);

const initial = computed(() => {
  return props.name ? props.name.charAt(0).toUpperCase() : '?';
});

// Only show initials fallback at md/lg/xl sizes
const showInitials = computed(() => {
  return !hasLogo.value && ['md', 'lg', 'xl'].includes(props.size);
});

const sizeConfig = computed(() => {
  const sizes = {
    xs: { container: 'w-6 h-6', img: 'w-5 h-5', text: 'text-[10px]' },
    sm: { container: 'w-8 h-8', img: 'w-7 h-7', text: 'text-xs' },
    md: { container: 'w-10 h-10', img: 'w-9 h-9', text: 'text-sm' },
    lg: { container: 'w-14 h-14', img: 'w-12 h-12', text: 'text-lg' },
    xl: {
      container: 'w-[140px] h-[140px]',
      img: 'w-[120px] h-[120px]',
      text: 'text-4xl',
    },
  };
  return sizes[props.size];
});

const containerClass = computed(() => {
  const base =
    'rounded-full flex items-center justify-center overflow-hidden flex-shrink-0';
  return `${base} ${sizeConfig.value.container}`;
});

const containerStyle = computed(() => {
  // Only add background for visible content (logo or initials)
  if (hasLogo.value || showInitials.value) {
    return { backgroundColor: 'rgba(255, 255, 255, 0.1)' };
  }
  return {};
});

const imgClass = computed(() => {
  return `${sizeConfig.value.img} object-contain`;
});

const initialsClass = computed(() => {
  return `${sizeConfig.value.text} font-bold text-slate-400`;
});
</script>
