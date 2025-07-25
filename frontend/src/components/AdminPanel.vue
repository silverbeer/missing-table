<template>
  <div class="admin-panel">
    <!-- Admin Access Check -->
    <div v-if="!authStore.isAdmin.value" class="text-center py-12">
      <div class="max-w-md mx-auto">
        <div class="text-red-600 text-6xl mb-4">🚫</div>
        <h2 class="text-2xl font-bold text-gray-900 mb-2">Access Denied</h2>
        <p class="text-gray-600">You need administrator privileges to access this page.</p>
      </div>
    </div>

    <!-- Admin Content (only for admins) -->
    <div v-else>
      <!-- Admin Header -->
      <div class="mb-6">
        <h2 class="text-2xl font-bold text-gray-900 mb-2">Admin Panel</h2>
        <p class="text-gray-600">Manage league data and configurations</p>
      </div>

    <!-- Admin Navigation -->
    <div class="mb-8">
      <nav class="flex space-x-1 bg-gray-100 p-1 rounded-lg" aria-label="Admin sections">
        <button
          v-for="section in adminSections"
          :key="section.id"
          @click="currentSection = section.id"
          :class="[
            currentSection === section.id
              ? 'bg-white text-gray-900 shadow'
              : 'text-gray-600 hover:text-gray-900',
            'px-4 py-2 text-sm font-medium rounded-md transition-colors'
          ]"
        >
          {{ section.name }}
        </button>
      </nav>
    </div>

    <!-- Section Content -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200">
      <!-- Age Groups Management -->
      <div v-if="currentSection === 'age-groups'" class="p-6">
        <AdminAgeGroups />
      </div>

      <!-- Seasons Management -->
      <div v-if="currentSection === 'seasons'" class="p-6">
        <AdminSeasons />
      </div>

      <!-- Divisions Management -->
      <div v-if="currentSection === 'divisions'" class="p-6">
        <AdminDivisions />
      </div>

      <!-- Teams Management -->
      <div v-if="currentSection === 'teams'" class="p-6">
        <AdminTeams />
      </div>

      <!-- Games Management -->
      <div v-if="currentSection === 'games'" class="p-6">
        <AdminGames />
      </div>
    </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AdminAgeGroups from './admin/AdminAgeGroups.vue'
import AdminSeasons from './admin/AdminSeasons.vue'
import AdminDivisions from './admin/AdminDivisions.vue'
import AdminTeams from './admin/AdminTeams.vue'
import AdminGames from './admin/AdminGames.vue'

export default {
  name: 'AdminPanel',
  components: {
    AdminAgeGroups,
    AdminSeasons,
    AdminDivisions,
    AdminTeams,
    AdminGames
  },
  setup() {
    const authStore = useAuthStore()
    const currentSection = ref('age-groups')

    const adminSections = [
      { id: 'age-groups', name: 'Age Groups' },
      { id: 'seasons', name: 'Seasons' },
      { id: 'divisions', name: 'Divisions' },
      { id: 'teams', name: 'Teams' },
      { id: 'games', name: 'Games' }
    ]

    return {
      authStore,
      currentSection,
      adminSections
    }
  }
}
</script>

<style scoped>
.admin-panel {
  max-width: 1200px;
  margin: 0 auto;
}
</style>