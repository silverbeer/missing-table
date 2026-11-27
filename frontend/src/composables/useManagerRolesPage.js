import { ref } from 'vue';

// The "Manager roles" page (SB-1799) is an overlay, like What's New. One flag
// shared app-wide so the user menu and the live-scoring hint (SB-1800) can
// both open it.
const isOpen = ref(false);

export function useManagerRolesPage() {
  return {
    isOpen,
    open: () => {
      isOpen.value = true;
    },
    close: () => {
      isOpen.value = false;
    },
  };
}
