<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Deep-link match detail (from a push notification: ?matchId=). Overlays
         everything; works for any match status. -->
    <div
      v-if="deepLinkMatchId"
      class="fixed inset-0 z-50 bg-black/60 overflow-y-auto"
      @click.self="closeDeepLinkMatch"
    >
      <div class="min-h-full flex items-start justify-center p-3 sm:p-6">
        <div
          class="relative w-full max-w-4xl bg-white rounded-lg shadow-2xl"
          @click.stop
        >
          <button
            type="button"
            aria-label="Close match details"
            class="absolute top-2 right-2 z-10 inline-flex items-center justify-center w-8 h-8 rounded-full text-gray-500 hover:text-gray-900 hover:bg-gray-100"
            @click="closeDeepLinkMatch"
          >
            ✕
          </button>
          <MatchDetailView
            :matchId="deepLinkMatchId"
            @back="closeDeepLinkMatch"
          />
        </div>
      </div>
    </div>

    <!-- PWA chrome: install prompt, offline indicator, update banner -->
    <IosInstallTooltip />
    <OfflineIndicator />
    <UpdateAvailablePrompt />

    <!-- Navigation -->
    <AuthNav @show-login="showLoginModal = true" @logout="handleLogout" />

    <!-- Login Modal -->
    <div v-if="showLoginModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <button @click="closeModal" class="modal-close">×</button>
        <ResetPasswordForm
          v-if="resetToken"
          :token="resetToken"
          @back-to-login="
            () => {
              resetToken = null;
              showForgotPassword = false;
            }
          "
        />
        <ForgotPasswordForm
          v-else-if="showForgotPassword"
          @back-to-login="showForgotPassword = false"
        />
        <LoginForm
          v-else
          @login-success="handleLoginSuccess"
          @show-forgot-password="showForgotPassword = true"
        />
      </div>
    </div>

    <!-- Main Content -->
    <div class="container mx-auto px-4 pt-2 pb-8">
      <!-- Loading indicator -->
      <div v-if="authStore.state.loading" class="loading-container">
        <div class="loading-spinner"></div>
        <p>Loading...</p>
      </div>

      <!-- Auth Error Display -->
      <div v-if="authStore.state.error" class="error-banner">
        <p>{{ authStore.state.error }}</p>
        <button @click="authStore.clearError()" class="error-close">×</button>
      </div>

      <!-- Content based on auth status -->
      <div v-if="!authStore.state.loading">
        <!-- Unauthenticated view -->
        <div v-if="!authStore.state.session" class="max-w-4xl mx-auto">
          <!-- Hero (inside loading guard — renders exactly once) -->
          <div
            class="text-center mb-8 rounded-2xl py-14 px-6 text-white shadow-lg relative overflow-hidden"
            style="
              background-image: url('/hero-goal.png');
              background-size: cover;
              background-position: center;
            "
          >
            <div class="absolute inset-0 bg-brand-700/55 rounded-2xl"></div>
            <div class="relative z-10">
              <div
                class="inline-flex items-center justify-center w-14 h-14 bg-white/15 rounded-full mb-5"
              >
                <svg
                  class="w-7 h-7 text-white/80"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke-width="1.5"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
                  />
                </svg>
              </div>
              <h1 class="text-4xl font-bold mb-3 tracking-tight">
                The table you've been missing.
              </h1>
              <p class="text-lg text-slate-300 max-w-xl mx-auto">
                Community-built standings, tracking the top youth soccer leagues
                in the US
              </p>
            </div>
          </div>
          <!-- Main Card -->
          <div
            class="bg-white rounded-2xl shadow-lg ring-1 ring-slate-200/60 p-8 text-center mb-6"
          >
            <div
              class="inline-flex items-center justify-center w-16 h-16 bg-slate-100 rounded-full mb-5"
            >
              <svg
                class="w-8 h-8 text-slate-600"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke-width="1.5"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
                />
              </svg>
            </div>
            <h2 class="text-2xl font-bold text-slate-800 mb-3">
              Invite-Only Platform
            </h2>
            <p class="text-slate-500 mb-7 max-w-md mx-auto">
              Missing Table is an invite-only community platform for tracking
              youth soccer league standings and games.
            </p>
            <div class="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                @click="showLoginModal = true"
                class="bg-brand-500 text-white px-8 py-3 rounded-lg font-semibold hover:bg-brand-600 transition-colors text-base shadow-sm"
              >
                Login
              </button>
              <button
                @click="showInviteRequestModal = true"
                class="bg-white text-slate-700 px-8 py-3 rounded-lg font-semibold hover:bg-slate-50 transition-colors text-base border border-slate-300 shadow-sm"
              >
                Request Invite
              </button>
            </div>
          </div>

          <!-- Features Section -->
          <div class="grid md:grid-cols-3 gap-4">
            <div
              class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/60 p-6 text-center"
            >
              <div
                class="inline-flex items-center justify-center w-12 h-12 bg-brand-50 rounded-xl mb-4"
              >
                <svg
                  class="w-6 h-6 text-brand-500"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke-width="1.5"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
                  />
                </svg>
              </div>
              <h3 class="font-semibold text-slate-800 mb-2">Live Standings</h3>
              <p class="text-sm text-slate-500">
                Real-time league tables with automatic point calculations and
                rankings
              </p>
            </div>
            <div
              class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/60 p-6 text-center"
            >
              <div
                class="inline-flex items-center justify-center w-12 h-12 bg-sky-50 rounded-xl mb-4"
              >
                <svg
                  class="w-6 h-6 text-sky-600"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke-width="1.5"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
                  />
                </svg>
              </div>
              <h3 class="font-semibold text-slate-800 mb-2">Match Tracking</h3>
              <p class="text-sm text-slate-500">
                Track scores, schedules, and results for your team's games
              </p>
            </div>
            <div
              class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/60 p-6 text-center"
            >
              <div
                class="inline-flex items-center justify-center w-12 h-12 bg-violet-50 rounded-xl mb-4"
              >
                <svg
                  class="w-6 h-6 text-violet-600"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke-width="1.5"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"
                  />
                </svg>
              </div>
              <h3 class="font-semibold text-slate-800 mb-2">Team Management</h3>
              <p class="text-sm text-slate-500">
                Manage rosters, match types, and team information all in one
                place
              </p>
            </div>
          </div>
        </div>

        <!-- Invite Request Modal -->
        <div
          v-if="showInviteRequestModal"
          class="modal-overlay"
          @click="showInviteRequestModal = false"
        >
          <div class="modal-content p-6" @click.stop>
            <button @click="showInviteRequestModal = false" class="modal-close">
              ×
            </button>
            <h3 class="text-xl font-bold text-gray-800 mb-4">Request Invite</h3>
            <p class="text-gray-600 mb-4">
              Missing Table is currently invite-only. Please provide your
              information and we'll reach out when spots are available.
            </p>
            <form @submit.prevent="submitInviteRequest" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Email</label
                >
                <input
                  v-model="inviteRequest.email"
                  type="email"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="your@email.com"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Name</label
                >
                <input
                  v-model="inviteRequest.name"
                  type="text"
                  required
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Your name"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Team/Club (optional)</label
                >
                <input
                  v-model="inviteRequest.team"
                  type="text"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Your team or club name"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1"
                  >Why do you want to join?</label
                >
                <textarea
                  v-model="inviteRequest.reason"
                  rows="3"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Tell us about your interest in Missing Table"
                ></textarea>
              </div>
              <!-- Honeypot field - hidden from humans, bots will fill it -->
              <div style="position: absolute; left: -9999px" aria-hidden="true">
                <input
                  v-model="inviteRequest.website"
                  type="text"
                  name="website"
                  tabindex="-1"
                  autocomplete="off"
                />
              </div>
              <div class="flex gap-3">
                <button
                  type="submit"
                  :disabled="inviteRequestSubmitting"
                  class="flex-1 bg-brand-600 text-white py-2 rounded-md font-semibold hover:bg-brand-700 transition-colors disabled:opacity-50"
                >
                  {{
                    inviteRequestSubmitting ? 'Submitting...' : 'Submit Request'
                  }}
                </button>
                <button
                  type="button"
                  @click="showInviteRequestModal = false"
                  class="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
              </div>
            </form>
            <div
              v-if="inviteRequestMessage"
              :class="[
                'mt-4 p-3 rounded-md text-sm',
                inviteRequestSuccess
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800',
              ]"
            >
              {{ inviteRequestMessage }}
            </div>
          </div>
        </div>

        <!-- Tabs + Content card (authenticated users) -->
        <div
          v-if="authStore.state.session"
          class="bg-white rounded-xl shadow-sm ring-1 ring-slate-200/60 overflow-hidden"
        >
          <nav
            class="flex space-x-1 border-b border-slate-200 overflow-x-auto px-2"
            aria-label="Tabs"
          >
            <button
              v-for="tab in availableTabs"
              :key="tab.id"
              @click="
                tab.id === 'live' ? handleLiveTabClick() : (currentTab = tab.id)
              "
              :class="[
                currentTab === tab.id
                  ? 'border-b-2 border-brand-500 text-brand-500'
                  : tab.isLive
                    ? 'text-red-600 hover:text-red-700 live-tab-pulse border-b-2 border-transparent'
                    : 'text-slate-500 hover:text-slate-700 border-b-2 border-transparent hover:border-slate-300',
                'px-4 py-3 font-medium text-sm whitespace-nowrap transition-colors',
              ]"
            >
              <span v-if="tab.isLive" class="live-dot"></span>
              {{ tab.name }}
              <span
                v-if="tab.isBeta"
                class="beta-badge"
                data-testid="beta-badge"
                aria-label="Beta feature"
                >Beta</span
              >
              <span
                v-if="
                  tab.id === 'admin' &&
                  authStore.isAdmin.value &&
                  adminAttention.total.value > 0
                "
                class="admin-attention-dot"
                data-testid="admin-attention-dot"
                :title="adminAttention.tooltip.value"
                :aria-label="`Needs attention: ${adminAttention.tooltip.value}`"
              ></span>
            </button>
          </nav>
          <!-- Standings -->
          <div v-if="currentTab === 'table'" class="p-4">
            <LeagueTable
              :initial-age-group-id="tableFilters.ageGroupId"
              :initial-league-id="tableFilters.leagueId"
              :initial-division-id="tableFilters.divisionId"
              :filter-key="tableFilters.key"
              @navigate-to-team="handleNavigateToTeam"
            />
          </div>

          <!-- Matches -->
          <div v-if="currentTab === 'scores'" class="p-4">
            <MatchesView
              :initial-age-group-id="matchesFilters.ageGroupId"
              :initial-league-id="matchesFilters.leagueId"
              :initial-division-id="matchesFilters.divisionId"
              :initial-club-id="matchesFilters.clubId"
              :initial-team-id="matchesFilters.teamId"
              :initial-season-id="matchesFilters.seasonId"
              :initial-match-type-id="matchesFilters.matchTypeId"
              :filter-key="matchesFilters.key"
            />
          </div>

          <!-- Match Center -->
          <div v-if="currentTab === 'match-center'" class="p-4">
            <TournamentMatchCenter />
          </div>

          <!-- Leaderboard -->
          <div v-if="currentTab === 'leaderboard'" class="p-4">
            <GoalsLeaderboard />
          </div>

          <!-- QoP Rankings -->
          <div v-if="currentTab === 'qop'" class="p-4">
            <QoPStandings />
          </div>

          <!-- Add Match Form (auth required) -->
          <div v-if="currentTab === 'add-match'" class="p-4">
            <div v-if="!authStore.isAuthenticated" class="auth-required">
              <p>You must be logged in to add matches.</p>
              <button @click="showLoginModal = true" class="login-prompt-btn">
                Login
              </button>
            </div>
            <div v-else-if="!authStore.canManageTeam" class="permission-denied">
              <p>You need team manager or admin permissions to add matches.</p>
            </div>
            <MatchForm v-else />
          </div>

          <!-- Profile (auth required) -->
          <div v-if="currentTab === 'profile'" class="p-4">
            <ProfileRouter
              @logout="handleLogout"
              @switch-tab="handleSwitchTab"
            />
          </div>

          <!-- My Club (players only) -->
          <div v-if="currentTab === 'my-club'" class="p-4">
            <TeamRosterRouter />
          </div>

          <!-- Admin Panel (admin only) -->
          <div v-if="currentTab === 'admin'" class="p-4">
            <AdminPanel />
          </div>

          <!-- Live Match -->
          <div v-if="currentTab === 'live'" class="live-tab-content">
            <!-- Match Picker (if multiple live matches and none selected) -->
            <div
              v-if="liveMatches.length > 1 && !selectedLiveMatchId"
              class="p-4"
            >
              <h2 class="text-xl font-bold mb-4">Live Matches</h2>
              <div class="space-y-3">
                <button
                  v-for="match in liveMatches"
                  :key="match.match_id"
                  @click="selectLiveMatch(match.match_id)"
                  class="w-full p-4 bg-gray-50 hover:bg-gray-100 rounded-lg text-left border border-gray-200"
                >
                  <div class="flex justify-between items-center">
                    <div>
                      <span class="font-semibold">{{
                        match.home_team_name
                      }}</span>
                      <span class="text-gray-500 mx-2">vs</span>
                      <span class="font-semibold">{{
                        match.away_team_name
                      }}</span>
                    </div>
                    <div class="text-lg font-bold">
                      {{ match.home_score ?? 0 }} - {{ match.away_score ?? 0 }}
                    </div>
                  </div>
                </button>
              </div>
            </div>

            <!-- Live Match View -->
            <LiveMatchView
              v-else-if="selectedLiveMatchId"
              :match-id="selectedLiveMatchId"
              @back="handleLiveMatchBack"
            />

            <!-- No live matches fallback -->
            <div
              v-else-if="liveMatches.length === 0"
              class="p-8 text-center text-gray-500"
            >
              <p>No live matches at the moment.</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Version Footer -->
      <VersionFooter @open-whats-new="showWhatsNew = true" />
    </div>

    <!-- What's New (changelog) overlay, launched from the footer version -->
    <WhatsNewView v-if="showWhatsNew" @close="showWhatsNew = false" />
  </div>
</template>

<script>
import {
  ref,
  computed,
  onMounted,
  onUnmounted,
  watch,
  defineAsyncComponent,
} from 'vue';
import { useAuthStore } from './stores/auth';
import { useAdminAttentionCounts } from './composables/useAdminAttentionCounts';
import { getApiBaseUrl } from './config/api';
import { recordPageView, recordInviteRequest } from './faro';

// Eagerly loaded: initial-paint view (LeagueTable is the default tab) and the
// always-mounted chrome (nav, footer, indicators, login screen). These belong
// in the initial bundle so first paint has no async waterfall.
import LeagueTable from './components/LeagueTable.vue';
import AuthNav from './components/AuthNav.vue';
import LoginForm from './components/LoginForm.vue';
import VersionFooter from './components/VersionFooter.vue';
import IosInstallTooltip from './components/IosInstallTooltip.vue';
import OfflineIndicator from './components/OfflineIndicator.vue';
import UpdateAvailablePrompt from './components/UpdateAvailablePrompt.vue';

// Lazily loaded (SB-122): every view that lives behind a tab `v-if` and isn't
// shown on first paint. Each becomes its own chunk, fetched only when its tab
// is opened — keeps the initial bundle (and TTI) small. TournamentMatchCenter
// pulls the heavy bracket components, so this is the biggest single win.
const MatchForm = defineAsyncComponent(
  () => import('./components/MatchForm.vue')
);
const MatchesView = defineAsyncComponent(
  () => import('./components/MatchesView.vue')
);
const MatchDetailView = defineAsyncComponent(
  () => import('./components/MatchDetailView.vue')
);
const GoalsLeaderboard = defineAsyncComponent(
  () => import('./components/GoalsLeaderboard.vue')
);
const ForgotPasswordForm = defineAsyncComponent(
  () => import('./components/ForgotPasswordForm.vue')
);
const ResetPasswordForm = defineAsyncComponent(
  () => import('./components/ResetPasswordForm.vue')
);
const ProfileRouter = defineAsyncComponent(
  () => import('./components/ProfileRouter.vue')
);
const TeamRosterRouter = defineAsyncComponent(
  () => import('./components/profiles/TeamRosterRouter.vue')
);
const AdminPanel = defineAsyncComponent(
  () => import('./components/AdminPanel.vue')
);
const TournamentMatchCenter = defineAsyncComponent(
  () => import('./components/TournamentMatchCenter.vue')
);
const QoPStandings = defineAsyncComponent(
  () => import('./components/QoPStandings.vue')
);
const WhatsNewView = defineAsyncComponent(
  () => import('./components/WhatsNewView.vue')
);
const LiveMatchView = defineAsyncComponent(() =>
  import('./components/live').then(m => m.LiveMatchView)
);

export default {
  name: 'App',
  components: {
    MatchForm,
    LeagueTable,
    MatchesView,
    MatchDetailView,
    GoalsLeaderboard,
    AuthNav,
    LoginForm,
    ForgotPasswordForm,
    ResetPasswordForm,
    ProfileRouter,
    TeamRosterRouter,
    AdminPanel,
    TournamentMatchCenter,
    QoPStandings,
    VersionFooter,
    WhatsNewView,
    LiveMatchView,
    IosInstallTooltip,
    OfflineIndicator,
    UpdateAvailablePrompt,
  },
  setup() {
    const authStore = useAuthStore();
    const adminAttention = useAdminAttentionCounts();
    const currentTab = ref('table');
    // Deep link from a push notification: ?matchId=<id> opens MatchDetailView
    // as an overlay (SB-86). Works for any match status, incl. completed.
    const deepLinkMatchId = ref(null);
    const closeDeepLinkMatch = () => {
      deepLinkMatchId.value = null;
    };
    // "What's New" changelog overlay, opened from the footer version.
    const showWhatsNew = ref(false);
    const tableFilters = ref({
      ageGroupId: null,
      leagueId: null,
      divisionId: null,
      key: 0, // Used to force re-render when filters change
    });
    const matchesFilters = ref({
      ageGroupId: null,
      leagueId: null,
      divisionId: null,
      clubId: null,
      teamId: null,
      seasonId: null,
      matchTypeId: null,
      key: 0, // Used to force re-render when filters change
    });
    const showLoginModal = ref(false);
    const showForgotPassword = ref(false);
    const resetToken = ref(null);
    const showInviteRequestModal = ref(false);
    const inviteRequest = ref({
      email: '',
      name: '',
      team: '',
      reason: '',
      website: '', // Honeypot field - bots will fill this
    });
    const inviteRequestSubmitting = ref(false);
    const inviteRequestMessage = ref('');
    const inviteRequestSuccess = ref(false);

    // Live match state
    const liveMatches = ref([]);
    const selectedLiveMatchId = ref(null);
    let liveMatchPollInterval = null;

    // Fetch live matches for the LIVE tab
    const fetchLiveMatches = async () => {
      if (!authStore.isAuthenticated.value) {
        liveMatches.value = [];
        return;
      }

      try {
        const response = await authStore.apiRequest(
          `${getApiBaseUrl()}/api/matches/live`
        );
        if (Array.isArray(response)) {
          liveMatches.value = response;
        }
      } catch (error) {
        console.error('Error fetching live matches:', error);
      }
    };

    // Start/stop live match polling
    const startLiveMatchPolling = () => {
      if (liveMatchPollInterval) return;
      fetchLiveMatches(); // Fetch immediately
      liveMatchPollInterval = setInterval(fetchLiveMatches, 30000); // Poll every 30s
    };

    const stopLiveMatchPolling = () => {
      if (liveMatchPollInterval) {
        clearInterval(liveMatchPollInterval);
        liveMatchPollInterval = null;
      }
    };

    // Computed: has live matches
    const hasLiveMatches = computed(() => liveMatches.value.length > 0);

    // Define all possible tabs
    const allTabs = [
      { id: 'table', name: 'Table', requiresAuth: true },
      { id: 'scores', name: 'Matches', requiresAuth: true },
      { id: 'match-center', name: 'Tournaments', requiresAuth: true },
      {
        id: 'leaderboard',
        name: 'Leaderboard',
        requiresAuth: true,
        isBeta: true,
      },
      { id: 'qop', name: 'QoP', requiresAuth: true },
      {
        id: 'add-match',
        name: 'Add Match',
        requiresAuth: true,
        requiresRole: ['admin', 'club_manager', 'team-manager'],
      },
      {
        id: 'my-club',
        name: 'My Club',
        requiresAuth: true,
        requiresRole: ['team-player'],
      },
      {
        id: 'admin',
        name: 'Admin',
        requiresAuth: true,
        requiresRole: ['admin', 'club_manager'],
      },
      { id: 'profile', name: 'Profile', requiresAuth: true },
    ];

    // Computed property for available tabs based on user's auth status and role
    const availableTabs = computed(() => {
      const userRole = authStore.userRole.value;

      let tabs = allTabs
        .filter(tab => {
          // Always show public tabs
          if (!tab.requiresAuth) return true;

          // Don't show auth-required tabs if user is not authenticated
          if (!authStore.isAuthenticated.value) return false;

          // Check role requirements
          if (tab.requiresRole) {
            return tab.requiresRole.includes(userRole);
          }

          return true;
        })
        .map(tab => {
          // Rename "Admin" tab to "Manage Club" for club managers
          if (tab.id === 'admin' && userRole === 'club_manager') {
            return { ...tab, name: 'Manage Club' };
          }
          return tab;
        });

      // Add LIVE tab at the beginning if there are live matches
      if (hasLiveMatches.value && authStore.isAuthenticated.value) {
        tabs = [{ id: 'live', name: 'LIVE', isLive: true }, ...tabs];
      }

      return tabs;
    });

    const closeModal = () => {
      showLoginModal.value = false;
      showForgotPassword.value = false;
      resetToken.value = null;
    };

    const handleLoginSuccess = () => {
      showLoginModal.value = false;
      // Optionally redirect to profile or keep current tab
    };

    const handleLogout = () => {
      // Reset to public tab if current tab requires auth
      const currentTabData = allTabs.find(t => t.id === currentTab.value);
      if (currentTabData && currentTabData.requiresAuth) {
        currentTab.value = 'table';
      }
    };

    const handleSwitchTab = (tabId, filters = null) => {
      // Switch to the requested tab
      currentTab.value = tabId;

      // If filters provided and switching to table, apply them
      if (tabId === 'table' && filters) {
        tableFilters.value = {
          ageGroupId: filters.ageGroupId || null,
          leagueId: filters.leagueId || null,
          divisionId: filters.divisionId || null,
          key: tableFilters.value.key + 1, // Force re-render
        };
      }

      // If filters provided and switching to scores/matches, apply them
      if (tabId === 'scores' && filters) {
        matchesFilters.value = {
          ageGroupId: filters.ageGroupId || null,
          leagueId: filters.leagueId || null,
          divisionId: filters.divisionId || null,
          teamId: filters.teamId || null,
          seasonId: filters.seasonId || null,
          matchTypeId: filters.matchTypeId || null,
          key: matchesFilters.value.key + 1, // Force re-render
        };
      }
    };

    const handleNavigateToTeam = filters => {
      currentTab.value = 'scores';
      matchesFilters.value = {
        ageGroupId: filters.ageGroupId || null,
        leagueId: filters.leagueId || null,
        divisionId: filters.divisionId || null,
        clubId: filters.clubId || null,
        teamId: filters.teamId || null,
        seasonId: filters.seasonId || null,
        matchTypeId: 1, // League
        key: matchesFilters.value.key + 1,
      };
    };

    const submitInviteRequest = async () => {
      inviteRequestSubmitting.value = true;
      inviteRequestMessage.value = '';

      try {
        const response = await fetch(`${getApiBaseUrl()}/api/invite-requests`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(inviteRequest.value),
        });

        const data = await response.json();

        if (response.ok && data.success) {
          inviteRequestSuccess.value = true;
          inviteRequestMessage.value = data.message;
          recordInviteRequest(true);

          // Reset form
          inviteRequest.value = {
            email: '',
            name: '',
            team: '',
            reason: '',
            website: '',
          };
        } else {
          inviteRequestSuccess.value = false;
          inviteRequestMessage.value =
            data.detail || 'Failed to submit request. Please try again.';
          recordInviteRequest(false);
        }
      } catch (error) {
        inviteRequestSuccess.value = false;
        inviteRequestMessage.value =
          'Failed to submit request. Please try again.';
        recordInviteRequest(false);
      } finally {
        inviteRequestSubmitting.value = false;
      }
    };

    // Watch for tab changes and record page views
    watch(currentTab, newTab => {
      recordPageView(newTab, {
        authenticated: authStore.isAuthenticated.value ? 'true' : 'false',
        user_role: authStore.userRole.value || 'anonymous',
      });
    });

    // Initialize auth on app start
    onMounted(async () => {
      // For testing - uncomment the next line to force logout on each page load
      // authStore.forceLogout()

      // Check for OAuth callback (tokens in URL hash from Supabase redirect)
      const hashParams = new URLSearchParams(window.location.hash.substring(1));
      const accessToken = hashParams.get('access_token');

      if (accessToken) {
        // This is an OAuth callback - handle it
        console.log('OAuth callback detected, processing...');
        const result = await authStore.handleOAuthCallback();
        if (result.success) {
          // Redirect to home page and clear the OAuth tokens from URL
          window.history.replaceState(null, '', '/');
          currentTab.value = 'profile'; // Show profile tab after login
          console.log('OAuth login successful');
        } else {
          console.error('OAuth callback failed:', result.error);
          // Redirect to home even on failure to clear the callback URL
          window.history.replaceState(null, '', '/');
        }
      } else {
        // Normal initialization
        await authStore.initialize();
      }

      // Record initial page view after auth initialization
      recordPageView(currentTab.value, {
        authenticated: authStore.isAuthenticated.value ? 'true' : 'false',
        user_role: authStore.userRole.value || 'anonymous',
      });

      // Check for invite code in URL - automatically open login modal for signup
      const urlParams = new URLSearchParams(window.location.search);
      const inviteCode = urlParams.get('code');
      if (inviteCode && !authStore.isAuthenticated.value) {
        showLoginModal.value = true;
      }

      // Check for password reset token in URL
      const resetTokenParam = urlParams.get('reset_token');
      if (resetTokenParam) {
        resetToken.value = resetTokenParam;
        showLoginModal.value = true;
        // Clean token from URL without triggering a reload
        const cleanUrl =
          window.location.pathname +
          (urlParams.get('code') ? `?code=${urlParams.get('code')}` : '');
        window.history.replaceState({}, '', cleanUrl);
      }

      // Deep link from a push notification: ?matchId=<id> → open the match.
      const matchIdParam = urlParams.get('matchId');
      if (matchIdParam && /^\d+$/.test(matchIdParam)) {
        deepLinkMatchId.value = Number(matchIdParam);
        // Strip matchId from the URL so a refresh/share doesn't re-trigger,
        // preserving any invite code (mirrors the reset_token cleanup above).
        const code = urlParams.get('code');
        const cleanUrl =
          window.location.pathname + (code ? `?code=${code}` : '');
        window.history.replaceState({}, '', cleanUrl);
      }

      // Start live match polling if authenticated
      if (authStore.isAuthenticated.value) {
        startLiveMatchPolling();
      }
    });

    // Watch for auth changes to start/stop live match polling
    watch(
      () => authStore.isAuthenticated.value,
      isAuth => {
        if (isAuth) {
          startLiveMatchPolling();
        } else {
          stopLiveMatchPolling();
          liveMatches.value = [];
          selectedLiveMatchId.value = null;
        }
      }
    );

    // Start/stop admin attention-counts polling tied to admin status.
    // When a user logs in as admin (or already-admin auth resolves on app
    // boot), kick off the 60s poll; when they log out or lose admin
    // role, stop. Composable handles the auth check + best-effort errors.
    watch(
      () => authStore.isAdmin.value,
      isAdmin => {
        if (isAdmin) {
          adminAttention.startPolling();
        } else {
          adminAttention.stopPolling();
        }
      },
      { immediate: true }
    );

    // Cleanup on unmount
    onUnmounted(() => {
      stopLiveMatchPolling();
      adminAttention.stopPolling();
    });

    // Handle clicking on LIVE tab
    const handleLiveTabClick = () => {
      if (liveMatches.value.length === 1) {
        // Single live match - go directly to it
        selectedLiveMatchId.value = liveMatches.value[0].match_id;
      } else if (liveMatches.value.length > 1) {
        // Multiple live matches - show picker (just switch tab, picker shown in template)
        selectedLiveMatchId.value = null;
      }
      currentTab.value = 'live';
    };

    // Handle selecting a live match from picker
    const selectLiveMatch = matchId => {
      selectedLiveMatchId.value = matchId;
    };

    // Handle going back from live match view
    const handleLiveMatchBack = () => {
      if (liveMatches.value.length > 1) {
        // Go back to match picker
        selectedLiveMatchId.value = null;
      } else {
        // Go back to previous tab
        currentTab.value = 'scores';
      }
    };

    return {
      authStore,
      adminAttention,
      currentTab,
      deepLinkMatchId,
      closeDeepLinkMatch,
      showWhatsNew,
      tableFilters,
      matchesFilters,
      availableTabs,
      showLoginModal,
      showForgotPassword,
      resetToken,
      showInviteRequestModal,
      inviteRequest,
      inviteRequestSubmitting,
      inviteRequestMessage,
      inviteRequestSuccess,
      closeModal,
      handleLoginSuccess,
      handleLogout,
      handleSwitchTab,
      handleNavigateToTeam,
      submitInviteRequest,
      // Live match
      liveMatches,
      selectedLiveMatchId,
      hasLiveMatches,
      handleLiveTabClick,
      selectLiveMatch,
      handleLiveMatchBack,
    };
  },
};
</script>

<style>
/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  position: relative;
  background: white;
  border-radius: 12px;
  max-width: 460px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  overflow-x: hidden;
}

.modal-close {
  position: absolute;
  top: 10px;
  right: 15px;
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  z-index: 1001;
}

.modal-close:hover {
  color: #333;
}

/* Loading styles */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #e2e8f0;
  border-top: 4px solid #2563eb;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

/* Error banner */
.error-banner {
  background-color: #f8d7da;
  color: #721c24;
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.error-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #721c24;
}

/* Auth prompts */
.auth-required,
.permission-denied {
  text-align: center;
  padding: 3rem;
  color: #666;
}

.login-prompt-btn {
  background-color: #2563eb;
  color: white;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 1rem;
}

.login-prompt-btn:hover {
  background-color: #1d4ed8;
}

/* Live Tab Styles */
.live-tab-pulse {
  animation: livePulse 2s ease-in-out infinite;
}

@keyframes livePulse {
  0%,
  100% {
    background-color: #fee2e2;
  }
  50% {
    background-color: #fecaca;
  }
}

.live-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  background-color: #dc2626;
  border-radius: 50%;
  margin-right: 6px;
  animation: liveDotPulse 1s ease-in-out infinite;
}

@keyframes liveDotPulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.admin-attention-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-left: 6px;
  vertical-align: 1px;
  background-color: #dc2626;
  border-radius: 50%;
  box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.18);
  cursor: help;
}

.beta-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 0.625rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #92400e;
  background-color: #fef3c7;
  border: 1px solid #fcd34d;
  border-radius: 9999px;
  vertical-align: middle;
}

.live-tab-content {
  min-height: 400px;
}
</style>
