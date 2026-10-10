<template>
  <div class="p-4 sm:p-6" data-testid="admin-invites">
    <h2 class="text-xl sm:text-2xl font-bold mb-4 sm:mb-6">
      Invite Management
    </h2>

    <!-- Create Invite Section -->
    <div
      class="bg-card rounded-lg shadow p-4 sm:p-6 mb-4 sm:mb-6"
      data-testid="create-invite-section"
    >
      <h3 class="text-base sm:text-lg font-semibold mb-3 sm:mb-4">
        Create New Invite
      </h3>

      <form
        @submit.prevent="createInvite"
        class="space-y-4"
        data-testid="create-invite-form"
      >
        <!-- Invite Type Selection -->
        <div>
          <label class="block text-sm font-medium text-fg mb-2"
            >Invite Type</label
          >
          <select
            v-model="newInvite.inviteType"
            required
            data-testid="invite-type-select"
            class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Select type...</option>
            <option v-if="isAdmin" value="club_manager">Club Manager</option>
            <option value="club_fan">Club Fan</option>
            <option value="team_manager">Team Manager</option>
            <option value="team_player">Team Player</option>
          </select>
        </div>

        <!-- Club Selection (for club-level invites) -->
        <div
          v-if="
            newInvite.inviteType === 'club_manager' ||
            newInvite.inviteType === 'club_fan'
          "
        >
          <label class="block text-sm font-medium text-fg mb-2">Club</label>
          <select
            v-model="newInvite.clubId"
            required
            data-testid="invite-club-select"
            class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Select club...</option>
            <option v-for="club in clubs" :key="club.id" :value="club.id">
              {{ club.name }}
            </option>
          </select>
        </div>

        <!-- Team Selection (for team-level invites) -->
        <div
          v-if="
            newInvite.inviteType &&
            newInvite.inviteType !== 'club_manager' &&
            newInvite.inviteType !== 'club_fan'
          "
        >
          <label class="block text-sm font-medium text-fg mb-2">Team</label>
          <select
            v-model="newInvite.teamId"
            required
            data-testid="invite-team-select"
            class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Select team...</option>
            <option v-for="team in teams" :key="team.id" :value="team.id">
              {{ team.name }}
            </option>
          </select>
        </div>

        <!-- Age Group Selection (for team-level invites) -->
        <div
          v-if="
            newInvite.inviteType &&
            newInvite.inviteType !== 'club_manager' &&
            newInvite.inviteType !== 'club_fan'
          "
        >
          <label class="block text-sm font-medium text-fg mb-2"
            >Age Group</label
          >
          <select
            v-model="newInvite.ageGroupId"
            required
            data-testid="invite-age-group-select"
            class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Select age group...</option>
            <option
              v-for="ageGroup in ageGroups"
              :key="ageGroup.id"
              :value="ageGroup.id"
            >
              {{ ageGroup.name }}
            </option>
          </select>
        </div>

        <!-- Jersey Number + Season (for team_player invites) -->
        <div v-if="newInvite.inviteType === 'team_player'">
          <label class="block text-sm font-medium text-fg mb-2"
            >Jersey Number (Optional)</label
          >
          <input
            v-model.number="newInvite.jerseyNumber"
            type="number"
            min="1"
            max="99"
            placeholder="e.g., 10"
            data-testid="invite-jersey-number-input"
            class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p class="mt-1 text-xs text-fg-muted">
            The player must already be on the roster with this number — when
            they accept the invite, their account claims that roster spot.
          </p>
        </div>
        <div v-if="newInvite.inviteType === 'team_player'">
          <label class="block text-sm font-medium text-fg mb-2">Season</label>
          <select
            v-model="newInvite.seasonId"
            data-testid="invite-season-select"
            class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option :value="null">Current season (default)</option>
            <option
              v-for="season in seasons"
              :key="season.id"
              :value="season.id"
            >
              {{ season.name }}
            </option>
          </select>
          <p class="mt-1 text-xs text-fg-muted">
            The season whose roster spot the invite claims.
          </p>
        </div>

        <!-- Email (Optional) -->
        <div>
          <label class="block text-sm font-medium text-fg mb-2"
            >Email (Optional)</label
          >
          <input
            v-model="newInvite.email"
            type="email"
            placeholder="Pre-fill email for recipient"
            data-testid="invite-email-input"
            class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p class="text-xs text-fg-muted mt-1">
            If provided, the invite link will be auto-emailed to this address
            once the invite is created.
          </p>
        </div>

        <!-- iPhone beta (admin only, SB-1314) -->
        <div v-if="isAdmin" data-testid="invite-ios-beta-section">
          <label class="inline-flex items-center gap-2 text-sm text-fg">
            <input
              v-model="newInvite.iosBeta"
              type="checkbox"
              data-testid="invite-ios-beta-checkbox"
              class="rounded border-line"
            />
            iPhone beta
          </label>
          <p class="mt-1 text-xs text-fg-muted">
            Adds them to the TestFlight beta — Apple emails them an invitation
            to install the iPhone app.
          </p>
          <div v-if="newInvite.iosBeta" class="mt-2">
            <label class="block text-sm font-medium text-fg mb-2"
              >TestFlight email</label
            >
            <input
              v-model="newInvite.testflightEmail"
              type="email"
              :required="!newInvite.email"
              :placeholder="newInvite.email || 'Their Apple Account email'"
              data-testid="invite-testflight-email-input"
              class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <p class="mt-1 text-xs text-fg-muted">
              The Apple Account email on their iPhone — often not the same as
              the invite email. Leave blank to use the invite email.
            </p>
          </div>
        </div>

        <!-- Note (Optional) -->
        <div>
          <label class="block text-sm font-medium text-fg mb-2"
            >Note (Optional)</label
          >
          <input
            v-model="newInvite.note"
            type="text"
            maxlength="500"
            placeholder="Who is this invite for? e.g., John Smith - U13 coach"
            data-testid="invite-note-input"
            class="w-full px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p class="mt-1 text-xs text-fg-muted">
            Personal reminder — visible only to you, not sent to the recipient.
          </p>
        </div>

        <!-- Submit Button -->
        <button
          type="submit"
          :disabled="loading"
          data-testid="create-invite-submit"
          class="w-full bg-brand-600 text-white py-2 px-4 rounded-md hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:opacity-50"
        >
          {{ loading ? 'Creating...' : 'Create Invite' }}
        </button>
      </form>

      <!-- Success Message -->
      <div
        v-if="createdInvite"
        class="mt-4 p-4 bg-green-50 border border-green-200 rounded-md"
        data-testid="invite-success-message"
      >
        <h4 class="font-semibold text-green-800 mb-2">
          Invite Created Successfully!
        </h4>

        <!-- Invite Details Summary -->
        <div class="space-y-1 text-sm mb-4">
          <p>
            <span class="font-medium">Type:</span>
            {{ formatInviteType(createdInvite.invite_type) }}
          </p>
          <p v-if="createdInvite.club_id">
            <span class="font-medium">Club:</span>
            {{ getClubName(createdInvite.club_id) }}
          </p>
          <p v-if="createdInvite.team_id">
            <span class="font-medium">Team:</span>
            {{ getTeamName(createdInvite.team_id) }}
          </p>
          <p v-if="createdInvite.age_group_id">
            <span class="font-medium">Age Group:</span>
            {{ getAgeGroupName(createdInvite.age_group_id) }}
          </p>
          <p v-if="createdInvite.jersey_number">
            <span class="font-medium">Jersey Number:</span>
            #{{ createdInvite.jersey_number }}
          </p>
          <p v-if="createdInvite.note">
            <span class="font-medium">Note:</span>
            {{ createdInvite.note }}
          </p>
          <p>
            <span class="font-medium">Expires:</span>
            {{ formatDate(createdInvite.expires_at) }}
          </p>
        </div>

        <!-- Copy-Ready Invite Message -->
        <div class="bg-card border border-line rounded-md p-4 mb-3">
          <div class="flex justify-between items-center mb-2">
            <span class="text-sm font-medium text-fg"
              >Invite Message (copy and send):</span
            >
            <button
              @click="copyInviteMessage"
              data-testid="copy-invite-message-button"
              class="text-sm bg-brand-600 text-white hover:bg-brand-700 px-3 py-1 rounded flex items-center gap-1"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
              {{ copyButtonText }}
            </button>
          </div>
          <pre
            class="text-sm text-fg whitespace-pre-wrap font-sans bg-surface-alt p-3 rounded border border-line"
            >{{ generatedInviteMessage }}</pre
          >
        </div>

        <!-- Copy Link Only Button -->
        <button
          @click="copyInviteLink(createdInvite.invite_code)"
          data-testid="copy-invite-link-button"
          class="text-sm bg-surface-alt text-fg hover:bg-line px-3 py-1 rounded"
        >
          Copy Link Only
        </button>
      </div>
    </div>

    <!-- Existing Invites -->
    <div
      class="bg-card rounded-lg shadow p-4 sm:p-6"
      data-testid="existing-invites-section"
    >
      <h3 class="text-base sm:text-lg font-semibold mb-3 sm:mb-4">
        Existing Invites
      </h3>

      <!-- Filter -->
      <div class="mb-4">
        <select
          v-model="statusFilter"
          @change="fetchInvites"
          data-testid="invite-status-filter"
          class="w-full sm:w-auto px-3 py-2 bg-card text-fg border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All Invites</option>
          <option value="pending">Pending</option>
          <option value="used">Used</option>
          <option value="expired">Expired</option>
        </select>
      </div>

      <!-- Mobile Card View -->
      <div class="sm:hidden space-y-3">
        <div
          v-for="invite in invites"
          :key="invite.id"
          class="border border-line rounded-lg p-3 bg-surface-alt"
        >
          <div class="flex justify-between items-start mb-2">
            <span class="font-mono text-sm font-medium">{{
              invite.invite_code
            }}</span>
            <span
              :class="{
                'bg-yellow-100 text-yellow-800': invite.status === 'pending',
                'bg-green-100 text-green-800': invite.status === 'used',
                'bg-red-100 text-red-800': invite.status === 'expired',
              }"
              class="px-2 py-1 text-xs rounded-full"
            >
              {{ invite.status }}
            </span>
          </div>
          <div class="text-sm space-y-1">
            <p>
              <span class="text-fg-muted">Type:</span>
              {{ formatInviteType(invite.invite_type) }}
            </p>
            <p>
              <span class="text-fg-muted">For:</span>
              <template v-if="invite.club_id">
                {{ invite.clubs?.name || 'Club ' + invite.club_id }}
              </template>
              <template v-else>
                {{ invite.teams?.name }} - {{ invite.age_groups?.name }}
              </template>
            </p>
            <p v-if="invite.used_by_user">
              <span class="text-fg-muted">Used by:</span>
              {{
                invite.used_by_user.display_name || invite.used_by_user.username
              }}
            </p>
            <p v-if="invite.testflight_status">
              <span class="text-fg-muted">TestFlight:</span>
              <span
                :class="testflightBadgeClass(invite.testflight_status)"
                :title="invite.testflight_error || ''"
                class="ml-1 px-2 py-0.5 text-xs rounded-full"
                >{{ invite.testflight_status }}</span
              >
              <button
                v-if="canRetryTestflight(invite)"
                type="button"
                class="ml-2 text-blue-600 hover:text-blue-900 text-xs font-medium"
                :disabled="retryingTestflightId === invite.id"
                @click="retryTestflight(invite)"
              >
                {{ retryingTestflightId === invite.id ? 'Retrying…' : 'Retry' }}
              </button>
            </p>
            <p v-if="invite.note" class="text-fg text-xs italic">
              {{ invite.note }}
            </p>
            <p class="text-fg-muted text-xs">
              {{ formatDate(invite.created_at) }}
            </p>
          </div>
          <div
            class="mt-2 pt-2 border-t border-line"
            v-if="invite.status === 'pending'"
          >
            <button
              @click="cancelInvite(invite.id)"
              class="text-red-600 hover:text-red-900 text-sm font-medium"
            >
              Cancel Invite
            </button>
          </div>
        </div>
        <p v-if="invites.length === 0" class="text-fg-muted text-center py-4">
          No invites found
        </p>
      </div>

      <!-- Desktop Table View -->
      <div
        class="hidden sm:block overflow-x-auto"
        data-testid="invites-table-container"
      >
        <table
          class="min-w-full divide-y divide-line"
          data-testid="invites-table"
        >
          <thead class="bg-surface-alt">
            <tr>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Code
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Type
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Club/Team
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Email Sent To
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Status
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Used By
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Note
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Created
              </th>
              <th
                class="px-6 py-3 text-left text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Actions
              </th>
            </tr>
          </thead>
          <tbody
            class="bg-card divide-y divide-line"
            data-testid="invites-tbody"
          >
            <tr
              v-for="invite in invites"
              :key="invite.id"
              :data-testid="`invite-row-${invite.id}`"
              data-invite-row
            >
              <td
                class="px-6 py-4 whitespace-nowrap text-sm font-mono"
                data-testid="invite-code"
              >
                {{ invite.invite_code }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                {{ formatInviteType(invite.invite_type) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <template v-if="invite.club_id">
                  {{ invite.clubs?.name || 'Club ' + invite.club_id }}
                </template>
                <template v-else>
                  {{ invite.teams?.name }} - {{ invite.age_groups?.name }}
                </template>
              </td>
              <td
                class="px-6 py-4 whitespace-nowrap text-sm"
                data-testid="invite-email-cell"
              >
                <span
                  v-if="invite.email"
                  :title="`Invite email auto-sent to ${invite.email}`"
                  class="inline-flex items-center gap-1 text-fg"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="w-3.5 h-3.5 text-green-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M3 8l9 6 9-6M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                    />
                  </svg>
                  {{ invite.email }}
                </span>
                <span v-else class="text-fg-muted">—</span>
                <div
                  v-if="invite.testflight_status"
                  class="mt-1 flex items-center gap-2"
                  data-testid="invite-testflight-cell"
                >
                  <span
                    :class="testflightBadgeClass(invite.testflight_status)"
                    :title="invite.testflight_error || ''"
                    class="px-2 py-0.5 text-xs rounded-full"
                    >TestFlight: {{ invite.testflight_status }}</span
                  >
                  <button
                    v-if="canRetryTestflight(invite)"
                    type="button"
                    data-testid="retry-testflight-button"
                    class="text-blue-600 hover:text-blue-900 text-xs font-medium"
                    :disabled="retryingTestflightId === invite.id"
                    @click="retryTestflight(invite)"
                  >
                    {{
                      retryingTestflightId === invite.id ? 'Retrying…' : 'Retry'
                    }}
                  </button>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span
                  :class="{
                    'bg-yellow-100 text-yellow-800':
                      invite.status === 'pending',
                    'bg-green-100 text-green-800': invite.status === 'used',
                    'bg-red-100 text-red-800': invite.status === 'expired',
                  }"
                  class="px-2 py-1 text-xs rounded-full"
                >
                  {{ invite.status }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-fg">
                <template v-if="invite.used_by_user">
                  {{
                    invite.used_by_user.display_name ||
                    invite.used_by_user.username
                  }}
                </template>
                <span v-else class="text-fg-muted">-</span>
              </td>
              <td class="px-6 py-4 text-sm text-fg-muted max-w-xs">
                <span
                  v-if="invite.note"
                  :title="invite.note"
                  class="truncate block"
                  >{{ invite.note }}</span
                >
                <span v-else class="text-fg-muted">-</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-fg-muted">
                {{ formatDate(invite.created_at) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <div class="flex items-center gap-3">
                  <button
                    type="button"
                    data-testid="view-invite-button"
                    class="text-blue-600 hover:text-blue-900 font-medium"
                    @click="openInviteDetail(invite)"
                  >
                    View
                  </button>
                  <button
                    v-if="invite.status === 'pending'"
                    @click="cancelInvite(invite.id)"
                    data-testid="cancel-invite-button"
                    class="text-red-600 hover:text-red-900"
                  >
                    Cancel
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Invite detail modal: shows every field of an invitation in a
         readable layout, since the table can't fit them all comfortably. -->
    <div
      v-if="selectedInvite"
      class="fixed inset-0 z-50 bg-black/60 overflow-y-auto"
      data-testid="invite-detail-modal"
      @click.self="closeInviteDetail"
    >
      <div class="min-h-full flex items-start justify-center p-4 sm:p-8">
        <div
          class="relative w-full max-w-2xl bg-card rounded-lg shadow-2xl"
          @click.stop
        >
          <button
            type="button"
            aria-label="Close invite details"
            class="absolute top-3 right-3 inline-flex items-center justify-center w-8 h-8 rounded-full text-fg-muted hover:text-fg hover:bg-surface-alt"
            @click="closeInviteDetail"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>

          <div class="px-6 py-5 border-b border-line">
            <h3 class="text-lg font-semibold text-fg">Invitation details</h3>
            <p class="text-xs text-fg-muted mt-1">
              Code:
              <span class="font-mono text-fg">
                {{ selectedInvite.invite_code }}
              </span>
            </p>
          </div>

          <dl
            class="px-6 py-5 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 text-sm"
          >
            <div>
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Type
              </dt>
              <dd class="mt-1 text-fg">
                {{ formatInviteType(selectedInvite.invite_type) }}
              </dd>
            </div>

            <div>
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Status
              </dt>
              <dd class="mt-1">
                <span
                  :class="{
                    'bg-yellow-100 text-yellow-800':
                      selectedInvite.status === 'pending',
                    'bg-green-100 text-green-800':
                      selectedInvite.status === 'used',
                    'bg-red-100 text-red-800':
                      selectedInvite.status === 'expired',
                  }"
                  class="px-2 py-1 text-xs rounded-full"
                >
                  {{ selectedInvite.status }}
                </span>
              </dd>
            </div>

            <div>
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Club / Team
              </dt>
              <dd class="mt-1 text-fg">
                <template v-if="selectedInvite.club_id">
                  {{
                    selectedInvite.clubs?.name ||
                    `Club ${selectedInvite.club_id}`
                  }}
                </template>
                <template v-else-if="selectedInvite.teams">
                  {{ selectedInvite.teams?.name }} —
                  {{ selectedInvite.age_groups?.name }}
                </template>
                <span v-else class="text-fg-muted">—</span>
              </dd>
            </div>

            <div>
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Email Sent To
              </dt>
              <dd class="mt-1 text-fg">
                <span v-if="selectedInvite.email">
                  {{ selectedInvite.email }}
                </span>
                <span v-else class="text-fg-muted">— (none provided)</span>
              </dd>
            </div>

            <div>
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Used By
              </dt>
              <dd class="mt-1 text-fg">
                <template v-if="selectedInvite.used_by_user">
                  {{
                    selectedInvite.used_by_user.display_name ||
                    selectedInvite.used_by_user.username
                  }}
                </template>
                <span v-else class="text-fg-muted">— (not redeemed)</span>
              </dd>
            </div>

            <div
              v-if="selectedInvite.testflight_status"
              class="sm:col-span-2"
              data-testid="invite-detail-testflight"
            >
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                iPhone beta (TestFlight)
              </dt>
              <dd class="mt-1 text-fg space-y-1">
                <div class="flex items-center gap-2">
                  <span
                    :class="
                      testflightBadgeClass(selectedInvite.testflight_status)
                    "
                    class="px-2 py-1 text-xs rounded-full"
                    >{{ selectedInvite.testflight_status }}</span
                  >
                  <span>{{ selectedInvite.testflight_email }}</span>
                  <button
                    v-if="canRetryTestflight(selectedInvite)"
                    type="button"
                    class="text-blue-600 hover:text-blue-900 text-sm font-medium"
                    :disabled="retryingTestflightId === selectedInvite.id"
                    @click="retryTestflight(selectedInvite)"
                  >
                    {{
                      retryingTestflightId === selectedInvite.id
                        ? 'Retrying…'
                        : 'Retry'
                    }}
                  </button>
                </div>
                <p
                  v-if="selectedInvite.testflight_error"
                  class="text-xs text-red-700 break-words"
                >
                  {{ selectedInvite.testflight_error }}
                </p>
              </dd>
            </div>

            <div>
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Created
              </dt>
              <dd class="mt-1 text-fg">
                {{ formatDate(selectedInvite.created_at) }}
              </dd>
            </div>

            <div v-if="selectedInvite.expires_at">
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Expires
              </dt>
              <dd class="mt-1 text-fg">
                {{ formatDate(selectedInvite.expires_at) }}
              </dd>
            </div>

            <div v-if="selectedInvite.jersey_number" class="sm:col-span-1">
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Jersey #
              </dt>
              <dd class="mt-1 text-fg">
                {{ selectedInvite.jersey_number }}
              </dd>
            </div>

            <div class="sm:col-span-2">
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Note
              </dt>
              <dd
                class="mt-1 text-fg whitespace-pre-wrap break-words"
                data-testid="invite-detail-note"
              >
                <template v-if="selectedInvite.note">
                  {{ selectedInvite.note }}
                </template>
                <span v-else class="text-fg-muted">— (no note)</span>
              </dd>
            </div>

            <div class="sm:col-span-2 pt-2 border-t border-line">
              <dt
                class="text-xs font-medium text-fg-muted uppercase tracking-wider"
              >
                Redemption link
              </dt>
              <dd class="mt-1 text-fg break-all font-mono text-xs">
                {{ currentOrigin }}/?code={{ selectedInvite.invite_code }}
              </dd>
            </div>
          </dl>

          <div class="px-6 py-4 border-t border-line flex justify-end gap-2">
            <button
              v-if="selectedInvite.status === 'pending'"
              type="button"
              class="px-4 py-2 text-sm rounded-md border border-red-300 text-red-700 hover:bg-red-50"
              @click="cancelInviteFromModal(selectedInvite.id)"
            >
              Cancel invite
            </button>
            <button
              type="button"
              class="px-4 py-2 text-sm rounded-md bg-gray-900 text-white hover:bg-gray-700"
              @click="closeInviteDetail"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { getApiBaseUrl } from '../../config/api';
import { errorMessage } from '../../utils/apiError';

const authStore = useAuthStore();

// Check if current user is admin
const isAdmin = computed(() => authStore.userRole.value === 'admin');

// State
const teams = ref([]);
const ageGroups = ref([]);
const seasons = ref([]);
const clubs = ref([]);
const invites = ref([]);
const loading = ref(false);
const createdInvite = ref(null);
const statusFilter = ref('');
const copyButtonText = ref('Copy Message');
// Selected invite for the detail modal. `null` = modal closed.
const selectedInvite = ref(null);
// Invite whose TestFlight add is being retried (SB-1314).
const retryingTestflightId = ref(null);

const openInviteDetail = invite => {
  selectedInvite.value = invite;
};

const closeInviteDetail = () => {
  selectedInvite.value = null;
};

const cancelInviteFromModal = async id => {
  await cancelInvite(id);
  closeInviteDetail();
};

// Safely get the current origin
const currentOrigin = computed(() => {
  if (typeof window !== 'undefined' && window.location) {
    return window.location.origin;
  }
  return 'http://localhost:8080'; // fallback for SSR or when window is undefined
});

// Generate the invite message for easy copy/paste
const generatedInviteMessage = computed(() => {
  if (!createdInvite.value) return '';

  const invite = createdInvite.value;
  const registrationUrl = `${currentOrigin.value}/register?code=${invite.invite_code}`;
  const roleDescription = formatInviteType(invite.invite_type);

  // Get organization name
  let orgName = '';
  if (invite.club_id) {
    orgName = getClubName(invite.club_id);
  } else if (invite.team_id) {
    const teamName = getTeamName(invite.team_id);
    const ageGroupName = invite.age_group_id
      ? getAgeGroupName(invite.age_group_id)
      : '';
    orgName = ageGroupName ? `${teamName} (${ageGroupName})` : teamName;
  }

  // Format expiration date nicely
  const expiresDate = new Date(invite.expires_at).toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  // Add jersey number info if present
  const jerseyInfo = invite.jersey_number
    ? `\n\n🏃 Your jersey number #${invite.jersey_number} has been reserved for you!`
    : '';

  return `🎉 You're Invited!

You've been invited to join Missing Table as a ${roleDescription}${orgName ? ` for ${orgName}` : ''}!${jerseyInfo}

📋 To get started:

1️⃣ Click this link to register:
   ${registrationUrl}

2️⃣ Fill out the registration form:
   • Username (required) - choose a unique username
   • Password (required) - create a secure password
   • Invite Code - already filled in for you ✅
   • Display Name (optional)
   • Email (optional)

3️⃣ Click "Sign Up" and you're done!

🔑 You'll automatically have ${roleDescription} access once registered.

⏰ This invite expires on ${expiresDate}.

❓ Questions? Reply to this message for help.`;
});

const newInvite = ref({
  inviteType: '',
  clubId: '',
  teamId: '',
  ageGroupId: '',
  email: '',
  jerseyNumber: null,
  seasonId: null,
  note: '',
  iosBeta: false,
  testflightEmail: '',
});

// Fetch teams, age groups, and clubs
const fetchReferenceData = async () => {
  try {
    const headers = authStore.getAuthHeaders();

    // Fetch teams
    const teamsResponse = await fetch(`${getApiBaseUrl()}/api/teams`, {
      headers,
    });
    teams.value = await teamsResponse.json();

    // Fetch age groups
    const ageGroupsResponse = await fetch(`${getApiBaseUrl()}/api/age-groups`, {
      headers,
    });
    ageGroups.value = await ageGroupsResponse.json();

    // Fetch seasons (team_player invites pin a season for the roster claim)
    const seasonsResponse = await fetch(`${getApiBaseUrl()}/api/seasons`, {
      headers,
    });
    seasons.value = await seasonsResponse.json();

    // Fetch clubs
    const clubsResponse = await fetch(`${getApiBaseUrl()}/api/clubs`, {
      headers,
    });
    clubs.value = await clubsResponse.json();
  } catch (error) {
    console.error('Error fetching reference data:', error);
  }
};

// Fetch invites
const fetchInvites = async () => {
  try {
    const headers = authStore.getAuthHeaders();
    let url = `${getApiBaseUrl()}/api/invites/my-invites`;
    if (statusFilter.value) {
      url += `?status=${statusFilter.value}`;
    }

    const response = await fetch(url, { headers });
    invites.value = await response.json();
  } catch (error) {
    console.error('Error fetching invites:', error);
  }
};

// Create invite
const createInvite = async () => {
  loading.value = true;
  createdInvite.value = null;

  try {
    const headers = {
      ...authStore.getAuthHeaders(),
      'Content-Type': 'application/json',
    };

    // Determine endpoint and body based on invite type and user role
    let endpoint;
    let body;

    // iPhone beta (SB-1314) is admin-only; manager endpoints refuse it.
    const iosBeta =
      isAdmin.value && newInvite.value.iosBeta
        ? {
            ios_beta: true,
            testflight_email:
              newInvite.value.testflightEmail || newInvite.value.email || null,
          }
        : {};

    if (newInvite.value.inviteType === 'club_manager') {
      endpoint = '/api/invites/admin/club-manager';
      body = JSON.stringify({
        club_id: parseInt(newInvite.value.clubId),
        email: newInvite.value.email || null,
        note: newInvite.value.note || null,
        ...iosBeta,
      });
    } else if (newInvite.value.inviteType === 'club_fan') {
      // Club managers use their own endpoint, admins use admin endpoint
      endpoint =
        authStore.userRole.value === 'club_manager'
          ? '/api/invites/club-manager/club-fan'
          : '/api/invites/admin/club-fan';
      body = JSON.stringify({
        club_id: parseInt(newInvite.value.clubId),
        email: newInvite.value.email || null,
        note: newInvite.value.note || null,
        ...iosBeta,
      });
    } else {
      endpoint = '/api/invites/admin/';
      if (newInvite.value.inviteType === 'team_manager') {
        endpoint += 'team-manager';
      } else if (newInvite.value.inviteType === 'team_player') {
        endpoint += 'team-player';
      }
      const requestBody = {
        invite_type: newInvite.value.inviteType,
        team_id: parseInt(newInvite.value.teamId),
        age_group_id: parseInt(newInvite.value.ageGroupId),
        email: newInvite.value.email || null,
        note: newInvite.value.note || null,
        ...iosBeta,
      };
      // Add jersey_number + season for team_player invites
      if (newInvite.value.inviteType === 'team_player') {
        if (newInvite.value.jerseyNumber) {
          requestBody.jersey_number = newInvite.value.jerseyNumber;
        }
        if (newInvite.value.seasonId) {
          requestBody.season_id = newInvite.value.seasonId;
        }
      }
      body = JSON.stringify(requestBody);
    }

    const response = await fetch(`${getApiBaseUrl()}${endpoint}`, {
      method: 'POST',
      headers,
      body,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorMessage(errorData, 'Failed to create invite'));
    }

    createdInvite.value = await response.json();

    // Reset form
    newInvite.value = {
      inviteType: '',
      clubId: '',
      teamId: '',
      ageGroupId: '',
      email: '',
      jerseyNumber: null,
      seasonId: null,
      note: '',
      iosBeta: false,
      testflightEmail: '',
    };

    // Refresh invites list
    await fetchInvites();
  } catch (error) {
    console.error('Error creating invite:', error);
    alert(`Failed to create invite: ${error.message}`);
  } finally {
    loading.value = false;
  }
};

// Cancel invite
const cancelInvite = async inviteId => {
  if (!confirm('Are you sure you want to cancel this invite?')) return;

  try {
    const headers = authStore.getAuthHeaders();
    const response = await fetch(`${getApiBaseUrl()}/api/invites/${inviteId}`, {
      method: 'DELETE',
      headers,
    });

    if (!response.ok) {
      throw new Error('Failed to cancel invite');
    }

    await fetchInvites();
  } catch (error) {
    console.error('Error cancelling invite:', error);
    alert('Failed to cancel invite. Please try again.');
  }
};

// Retry the TestFlight add for an iPhone beta invite (SB-1314)
const retryTestflight = async invite => {
  retryingTestflightId.value = invite.id;
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/api/invites/admin/${invite.id}/testflight/retry`,
      { method: 'POST', headers: authStore.getAuthHeaders() }
    );
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(errorMessage(data, 'Failed to retry TestFlight'));
    }
    if (selectedInvite.value?.id === invite.id) {
      selectedInvite.value = { ...selectedInvite.value, ...data };
    }
    if (data.testflight_status === 'failed') {
      alert(`TestFlight still failing: ${data.testflight_error || 'unknown'}`);
    }
    await fetchInvites();
  } catch (error) {
    console.error('Error retrying TestFlight:', error);
    alert(`Failed to retry TestFlight: ${error.message}`);
  } finally {
    retryingTestflightId.value = null;
  }
};

const canRetryTestflight = invite =>
  isAdmin.value &&
  (invite.testflight_status === 'failed' ||
    invite.testflight_status === 'pending');

const testflightBadgeClass = status =>
  ({
    pending: 'bg-yellow-100 text-yellow-800',
    added: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    removed: 'bg-gray-100 text-gray-800',
  })[status] || 'bg-gray-100 text-gray-800';

// Utility functions
const formatInviteType = type => {
  const types = {
    club_manager: 'Club Manager',
    club_fan: 'Club Fan',
    team_manager: 'Team Manager',
    team_player: 'Team Player',
    team_fan: 'Team Fan',
  };
  return types[type] || type;
};

const getClubName = clubId => {
  const club = clubs.value.find(c => c.id === clubId);
  return club?.name || 'Unknown';
};

const formatDate = dateString => {
  return new Date(dateString).toLocaleString();
};

const getTeamName = teamId => {
  const team = teams.value.find(t => t.id === teamId);
  return team?.name || 'Unknown';
};

const getAgeGroupName = ageGroupId => {
  const ageGroup = ageGroups.value.find(ag => ag.id === ageGroupId);
  return ageGroup?.name || 'Unknown';
};

const copyInviteLink = code => {
  const link = `${currentOrigin.value}/register?code=${code}`;
  navigator.clipboard.writeText(link);
  alert('Registration link copied to clipboard!');
};

const copyInviteMessage = async () => {
  try {
    await navigator.clipboard.writeText(generatedInviteMessage.value);
    copyButtonText.value = 'Copied!';
    setTimeout(() => {
      copyButtonText.value = 'Copy Message';
    }, 2000);
  } catch (err) {
    console.error('Failed to copy:', err);
    alert('Failed to copy message. Please select and copy manually.');
  }
};

// Lifecycle
onMounted(async () => {
  await fetchReferenceData();
  await fetchInvites();
});
</script>
