<template>
  <div class="overflow-x-auto">
    <!-- Loading State -->
    <div v-if="loading" class="text-center py-4">
      Loading table data...
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-center py-4 text-red-600">
      Error: {{ error }}
    </div>

    <!-- Table -->
    <table v-else class="min-w-full divide-y divide-gray-200">
      <thead class="bg-gray-50">
        <tr>
          <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pos</th>
          <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Team</th>
          <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">GP</th>
          <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">W</th>
          <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">D</th>
          <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">L</th>
          <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">GF</th>
          <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">GA</th>
          <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">GD</th>
          <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Pts</th>
        </tr>
      </thead>
      <tbody class="bg-white divide-y divide-gray-200">
        <tr v-for="(team, index) in tableData" :key="team.team">
          <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ index + 1 }}</td>
          <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ team.team }}</td>
          <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">{{ team.played }}</td>
          <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">{{ team.wins }}</td>
          <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">{{ team.draws }}</td>
          <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">{{ team.losses }}</td>
          <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">{{ team.goals_for }}</td>
          <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">{{ team.goals_against }}</td>
          <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">{{ team.goal_difference }}</td>
          <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500">{{ team.points }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'

export default {
  name: 'LeagueTable',
  setup() {
    const tableData = ref([])
    const error = ref(null)
    const loading = ref(true)

    const fetchTableData = async () => {
      loading.value = true
      console.log('Fetching table data...')
      try {
        const response = await fetch('http://localhost:8000/api/table')
        console.log('Response:', response)
        
        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.detail || 'Failed to fetch table data')
        }
        
        const data = await response.json()
        console.log('Table data received:', data)
        
        tableData.value = data
        console.log('Table data set:', tableData.value)
      } catch (err) {
        console.error('Error fetching table data:', err)
        error.value = err.message
      } finally {
        loading.value = false
      }
    }

    onMounted(() => {
      console.log('LeagueTable component mounted')
      fetchTableData()
    })

    return {
      tableData,
      error,
      loading
    }
  }
}
</script> 