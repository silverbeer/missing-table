<template>
  <div class="min-h-screen bg-gray-100">
    <div class="container mx-auto px-4 py-8">
      <h1 class="text-3xl font-bold text-blue-600 mb-8">
        MLS NEXT U13 Northeast Division
      </h1>
      
      <!-- Tabs -->
      <div class="mb-4">
        <nav class="flex space-x-4" aria-label="Tabs">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="currentTab = tab.id"
            :class="[
              currentTab === tab.id
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-500 hover:text-gray-700',
              'px-3 py-2 font-medium text-sm rounded-md'
            ]"
          >
            {{ tab.name }}
          </button>
        </nav>
      </div>

      <!-- Tab Content -->
      <div class="bg-white rounded-lg shadow">
        <!-- League Table -->
        <div v-if="currentTab === 'table'" class="p-4">
          <h2 class="text-xl font-semibold mb-4">U13 Northeast Table</h2>
          <LeagueTable />
        </div>

        <!-- Scores/Schedule -->
        <div v-if="currentTab === 'scores'" class="p-4">
          <h2 class="text-xl font-semibold mb-4">Scores/Schedule</h2>
          <ScoresSchedule />
        </div>

        <!-- Add Game Form -->
        <div v-if="currentTab === 'add-game'" class="p-4">
          <h2 class="text-xl font-semibold mb-4">Schedule/Score Game</h2>
          <GameForm />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import GameForm from './components/GameForm.vue'
import LeagueTable from './components/LeagueTable.vue'
import ScoresSchedule from './components/ScoresSchedule.vue'

export default {
  name: 'App',
  components: {
    GameForm,
    LeagueTable,
    ScoresSchedule
  },
  setup() {
    const currentTab = ref('table')
    const tabs = [
      { id: 'table', name: 'U13 Northeast Table' },
      { id: 'scores', name: 'Scores/Schedule' },
      { id: 'add-game', name: 'Schedule/Score Game' }
    ]

    return {
      currentTab,
      tabs
    }
  }
}
</script>