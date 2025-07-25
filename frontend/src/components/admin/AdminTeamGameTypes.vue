<template>
  <div class="bg-white rounded-lg shadow p-6">
    <h2 class="text-2xl font-bold mb-6">Manage Team Game Type Participation</h2>
    
    <!-- Add Team Section -->
    <div class="mb-8 p-4 border border-gray-200 rounded-lg">
      <h3 class="text-lg font-semibold mb-4">Add New Team</h3>
      <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Team Name</label>
          <input 
            v-model="newTeam.name" 
            type="text" 
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            placeholder="e.g., Visiting Club ABC"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">City</label>
          <input 
            v-model="newTeam.city" 
            type="text" 
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            placeholder="e.g., Toronto"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Team Type</label>
          <select 
            v-model="newTeam.teamType" 
            @change="onTeamTypeChange"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">Select Team Type</option>
            <option value="league">League Team</option>
            <option value="guest">Guest Team</option>
            <option value="tournament">Tournament Team</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Age Group</label>
          <select 
            v-model="newTeam.ageGroupId" 
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">Select Age Group</option>
            <option v-for="ageGroup in ageGroups" :key="ageGroup.id" :value="ageGroup.id">
              {{ ageGroup.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            Game Types
            <span class="text-xs text-gray-500">(auto-selected based on team type)</span>
          </label>
          <div class="space-y-1">
            <label v-for="gameType in gameTypes" :key="gameType.id" class="flex items-center text-sm">
              <input 
                type="checkbox" 
                :value="gameType.id" 
                v-model="newTeam.gameTypeIds"
                class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span class="ml-2">{{ gameType.name }}</span>
            </label>
          </div>
        </div>
      </div>
      <button 
        @click="addTeam"
        :disabled="!newTeam.name || !newTeam.ageGroupId || !newTeam.teamType || newTeam.gameTypeIds.length === 0"
        class="mt-4 bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600 disabled:bg-gray-300"
      >
        Add {{ newTeam.teamType ? (newTeam.teamType.charAt(0).toUpperCase() + newTeam.teamType.slice(1)) : '' }} Team
      </button>
    </div>

    <!-- Team Management Section -->
    <div class="mb-6">
      <h3 class="text-lg font-semibold mb-4">Manage Existing Teams</h3>
      
      <!-- Filters -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Filter by Age Group</label>
          <select 
            v-model="filterAgeGroup" 
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">All Age Groups</option>
            <option v-for="ageGroup in ageGroups" :key="ageGroup.id" :value="ageGroup.id">
              {{ ageGroup.name }}
            </option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Filter by Game Type</label>
          <select 
            v-model="filterGameType" 
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="">All Game Types</option>
            <option v-for="gameType in gameTypes" :key="gameType.id" :value="gameType.id">
              {{ gameType.name }}
            </option>
          </select>
        </div>
        <div class="flex items-end">
          <button 
            @click="loadTeams"
            class="bg-gray-500 text-white px-4 py-2 rounded-md hover:bg-gray-600"
          >
            Refresh
          </button>
        </div>
      </div>

      <!-- Teams Table -->
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Team</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">City</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Age Groups</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Game Types</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="team in filteredTeams" :key="team.id">
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                {{ team.name }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ team.city }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                <span v-for="ageGroup in team.age_groups" :key="ageGroup.id" 
                      class="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full mr-1">
                  {{ ageGroup.name }}
                </span>
              </td>
              <td class="px-6 py-4 text-sm text-gray-500">
                <div class="space-y-1">
                  <div v-for="ageGroup in team.age_groups" :key="ageGroup.id">
                    <span class="font-medium">{{ ageGroup.name }}:</span>
                    <span v-for="gameType in gameTypes" :key="gameType.id" 
                          class="inline-block text-xs px-2 py-1 rounded mr-1"
                          :class="teamCanParticipate(team.id, gameType.id, ageGroup.id) ? 
                            'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'">
                      {{ gameType.name }}
                    </span>
                  </div>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button 
                  @click="editTeam(team)"
                  class="text-blue-600 hover:text-blue-900 mr-3"
                >
                  Edit Participation
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Success/Error Messages -->
    <div v-if="message" 
         class="p-4 rounded-md"
         :class="{'bg-green-100 text-green-700': !error, 'bg-red-100 text-red-700': error}">
      {{ message }}
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'

export default {
  name: 'AdminTeamGameTypes',
  setup() {
    const teams = ref([])
    const ageGroups = ref([])
    const gameTypes = ref([])
    const message = ref('')
    const error = ref(false)
    
    const filterAgeGroup = ref('')
    const filterGameType = ref('')
    
    const newTeam = ref({
      name: '',
      city: '',
      teamType: '',
      ageGroupId: '',
      gameTypeIds: []
    })

    const filteredTeams = computed(() => {
      let result = teams.value
      
      if (filterAgeGroup.value) {
        result = result.filter(team => 
          team.age_groups.some(ag => ag.id === parseInt(filterAgeGroup.value))
        )
      }
      
      return result
    })

    const loadTeams = async () => {
      try {
        let url = 'http://localhost:8000/api/teams'
        if (filterGameType.value && filterAgeGroup.value) {
          url += `?game_type_id=${filterGameType.value}&age_group_id=${filterAgeGroup.value}`
        }
        
        const response = await fetch(url)
        if (!response.ok) throw new Error('Failed to fetch teams')
        teams.value = await response.json()
      } catch (err) {
        console.error('Error loading teams:', err)
        message.value = 'Error loading teams'
        error.value = true
      }
    }

    const loadReferenceData = async () => {
      try {
        // Load age groups
        const ageGroupsResponse = await fetch('http://localhost:8000/api/age-groups')
        if (ageGroupsResponse.ok) {
          ageGroups.value = await ageGroupsResponse.json()
        }

        // Load game types
        const gameTypesResponse = await fetch('http://localhost:8000/api/game-types')
        if (gameTypesResponse.ok) {
          gameTypes.value = await gameTypesResponse.json()
        }
      } catch (err) {
        console.error('Error loading reference data:', err)
      }
    }

    const onTeamTypeChange = () => {
      // Auto-select game types based on team type
      const teamType = newTeam.value.teamType
      const leagueId = gameTypes.value.find(gt => gt.name === 'League')?.id
      const friendlyId = gameTypes.value.find(gt => gt.name === 'Friendly')?.id
      const tournamentId = gameTypes.value.find(gt => gt.name === 'Tournament')?.id
      const playoffId = gameTypes.value.find(gt => gt.name === 'Playoff')?.id

      if (teamType === 'league') {
        // League teams can participate in all game types
        newTeam.value.gameTypeIds = [leagueId, friendlyId, tournamentId, playoffId].filter(id => id)
      } else if (teamType === 'guest') {
        // Guest teams typically only for friendlies
        newTeam.value.gameTypeIds = [friendlyId].filter(id => id)
      } else if (teamType === 'tournament') {
        // Tournament teams for tournaments and friendlies
        newTeam.value.gameTypeIds = [tournamentId, friendlyId].filter(id => id)
      } else {
        newTeam.value.gameTypeIds = []
      }
    }

    const addTeam = async () => {
      try {
        // First create the team
        const teamResponse = await fetch('http://localhost:8000/api/teams', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: newTeam.value.name,
            city: newTeam.value.city,
            age_group_ids: [parseInt(newTeam.value.ageGroupId)],
            division_ids: []
          })
        })

        if (!teamResponse.ok) throw new Error('Failed to create team')

        // Then add game type participation for each selected game type
        const teamData = await teamResponse.json()
        // Note: This would need the team ID from the response
        // For now, we'll reload teams to see the new team
        
        const gameTypeNames = newTeam.value.gameTypeIds.map(id => 
          gameTypes.value.find(gt => gt.id === id)?.name
        ).join(', ')
        
        message.value = `${newTeam.value.teamType.charAt(0).toUpperCase() + newTeam.value.teamType.slice(1)} team "${newTeam.value.name}" added successfully for ${gameTypeNames} games`
        error.value = false
        
        // Reset form
        newTeam.value = {
          name: '',
          city: '',
          teamType: '',
          ageGroupId: '',
          gameTypeIds: []
        }
        
        // Reload teams
        await loadTeams()
      } catch (err) {
        console.error('Error adding team:', err)
        message.value = 'Error adding team'
        error.value = true
      }
    }

    const teamCanParticipate = (teamId, gameTypeId, ageGroupId) => {
      // This is a placeholder - in a real implementation, you'd fetch this data
      // For now, assume all teams can participate in all game types
      return true
    }

    const editTeam = (team) => {
      // Placeholder for edit functionality
      console.log('Edit team:', team)
      message.value = 'Edit functionality coming soon'
      error.value = false
    }

    onMounted(async () => {
      await loadReferenceData()
      await loadTeams()
    })

    return {
      teams,
      ageGroups,
      gameTypes,
      message,
      error,
      filterAgeGroup,
      filterGameType,
      newTeam,
      filteredTeams,
      loadTeams,
      onTeamTypeChange,
      addTeam,
      teamCanParticipate,
      editTeam
    }
  }
}
</script>