<template>
  <div>
    <div
      class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/60 overflow-hidden"
    >
      <div
        class="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-slate-100"
      >
        <span class="text-sm font-semibold text-slate-800"
          >U14 · Northeast Division</span
        >
        <span
          class="text-xs font-medium text-slate-500 bg-slate-100 rounded-full px-2.5 py-0.5"
          >Sample</span
        >
      </div>
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-200">
          <thead class="bg-brand-500">
            <tr>
              <th
                class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider"
              >
                #
              </th>
              <th
                class="px-2 sm:px-4 md:px-6 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider"
              >
                Team
              </th>
              <th
                class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
                title="Games Played"
              >
                GP
              </th>
              <th
                class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
                title="Wins"
              >
                W
              </th>
              <th
                class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
                title="Draws"
              >
                D
              </th>
              <th
                class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
                title="Losses"
              >
                L
              </th>
              <th
                class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
                title="Goal Difference"
              >
                GD
              </th>
              <th
                class="px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-brand-200 uppercase tracking-wider"
                title="Points"
              >
                Pts
              </th>
              <th
                class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 text-center text-xs font-semibold text-slate-300 uppercase tracking-wider"
                title="Last 5 results"
              >
                Form
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-slate-100">
            <tr
              v-for="(team, index) in sampleStandings"
              :key="team.name"
              class="hover:bg-slate-50 transition-colors"
            >
              <td
                class="px-2 sm:px-4 md:px-6 py-3 whitespace-nowrap text-sm text-gray-500"
              >
                {{ index + 1 }}
              </td>
              <td
                class="px-2 sm:px-4 md:px-6 py-3 text-xs sm:text-sm font-medium text-gray-900 whitespace-nowrap"
              >
                {{ team.name }}
              </td>
              <td
                class="px-2 sm:px-4 md:px-6 py-3 whitespace-nowrap text-sm text-center text-gray-500"
              >
                {{ team.wins + team.draws + team.losses }}
              </td>
              <td
                class="px-2 sm:px-4 md:px-6 py-3 whitespace-nowrap text-sm text-center text-gray-500"
              >
                {{ team.wins }}
              </td>
              <td
                class="px-2 sm:px-4 md:px-6 py-3 whitespace-nowrap text-sm text-center text-gray-500"
              >
                {{ team.draws }}
              </td>
              <td
                class="px-2 sm:px-4 md:px-6 py-3 whitespace-nowrap text-sm text-center text-gray-500"
              >
                {{ team.losses }}
              </td>
              <td
                class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 whitespace-nowrap text-sm text-center text-gray-500"
              >
                {{ team.gd > 0 ? `+${team.gd}` : team.gd }}
              </td>
              <td
                class="px-2 sm:px-4 md:px-6 py-3 whitespace-nowrap text-sm text-center font-bold text-brand-600"
              >
                {{ team.wins * 3 + team.draws }}
              </td>
              <td
                class="hidden md:table-cell px-2 sm:px-4 md:px-6 py-3 whitespace-nowrap text-center"
              >
                <div class="flex items-center justify-center gap-1">
                  <span
                    v-for="(result, rIdx) in team.form"
                    :key="rIdx"
                    class="inline-block w-5 h-5 rounded-full text-[10px] font-bold leading-5 text-white text-center"
                    :class="{
                      'bg-green-500': result === 'W',
                      'bg-red-500': result === 'L',
                      'bg-gray-400': result === 'D',
                    }"
                  >
                    {{ result }}
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <p class="mt-4 text-center text-sm text-slate-500">
      Live standings with automatic rankings · Scores &amp; schedules · Rosters
      &amp; team management
    </p>
  </div>
</template>

<script setup>
// Static sample data — landing page preview only, never fetched
const sampleStandings = [
  {
    name: 'Harbor City FC',
    wins: 8,
    draws: 1,
    losses: 1,
    gd: 18,
    form: ['W', 'W', 'D', 'W', 'W'],
  },
  {
    name: 'Northside United',
    wins: 7,
    draws: 2,
    losses: 1,
    gd: 14,
    form: ['W', 'D', 'W', 'W', 'L'],
  },
  {
    name: 'Riverline SC',
    wins: 6,
    draws: 1,
    losses: 3,
    gd: 7,
    form: ['L', 'W', 'W', 'D', 'W'],
  },
  {
    name: 'Summit Athletic',
    wins: 4,
    draws: 3,
    losses: 3,
    gd: 2,
    form: ['D', 'L', 'W', 'D', 'W'],
  },
  {
    name: 'Bayview Rovers',
    wins: 3,
    draws: 2,
    losses: 5,
    gd: -6,
    form: ['L', 'W', 'L', 'D', 'L'],
  },
  {
    name: 'Ironbridge FC',
    wins: 1,
    draws: 1,
    losses: 8,
    gd: -21,
    form: ['L', 'L', 'D', 'L', 'L'],
  },
];
</script>
