<template>
  <!--
    What club and team managers do in MT (SB-1799). Teaches that the roles
    exist; deliberately has no request or apply button. Every capability
    listed here is enforced in the backend (auth.py can_manage_team /
    can_edit_match) — keep it that way when editing the copy.
  -->
  <div
    class="fixed inset-0 z-50 bg-black/60 overflow-y-auto"
    data-testid="manager-roles-overlay"
    @click.self="$emit('close')"
  >
    <div class="min-h-full flex items-start justify-center p-3 sm:p-6">
      <article
        class="relative w-full max-w-2xl bg-card rounded-lg shadow-2xl text-fg"
        @click.stop
      >
        <button
          type="button"
          aria-label="Close manager roles"
          data-testid="manager-roles-close"
          class="absolute top-3 right-3 z-10 inline-flex items-center justify-center w-8 h-8 rounded-full text-fg-muted hover:text-fg hover:bg-surface-alt"
          @click="$emit('close')"
        >
          ✕
        </button>

        <div class="p-5 sm:p-7 roles-body">
          <h2 class="text-xl font-bold mb-1">Club and team managers</h2>
          <p class="text-sm text-fg-muted mb-5">
            Every team's results and schedule come into Missing Table
            automatically. Managers add what results alone can't show.
          </p>

          <section data-testid="role-team-manager">
            <h3>Team manager</h3>
            <p class="role-scope text-fg-muted">For one team.</p>
            <ul>
              <li>
                <strong>Live score matches</strong>: kickoff, goals, cards,
                substitutions, halftime and full time, so fans can follow as it
                happens.
              </li>
              <li>Set the lineup for a match.</li>
              <li>Build the roster: players and jersey numbers.</li>
              <li>Record goals, assists and cards after a match.</li>
              <li>Add match photos.</li>
              <li>Invite the team's players and fans.</li>
              <li>Run the team's notification channels.</li>
            </ul>
          </section>

          <section data-testid="role-club-manager">
            <h3>Club manager</h3>
            <p class="role-scope text-fg-muted">For every team in one club.</p>
            <ul>
              <li>
                Everything a team manager can do, for any of the club's teams.
              </li>
              <li>Add the club's teams and the age groups they play in.</li>
              <li>Invite the club's fans.</li>
              <li>Approve requests to join the club's channels.</li>
            </ul>
          </section>

          <section data-testid="role-results">
            <h3>Results and manager entries</h3>
            <p>
              The official result always comes from MLS NEXT. What a manager
              records (who scored, who assisted, the lineup) is shown alongside
              it and never changes the official score.
            </p>
          </section>

          <section data-testid="role-how">
            <h3>How someone becomes a manager</h3>
            <p>
              Manager roles are by invitation from Missing Table. There is no
              sign-up.
            </p>
          </section>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
defineEmits(['close']);
</script>

<style scoped>
.roles-body h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-top: 1.25rem;
}
.roles-body .role-scope {
  font-size: 0.8125rem;
  margin-bottom: 0.25rem;
}
.roles-body ul {
  list-style: disc;
  padding-left: 1.25rem;
  font-size: 0.875rem;
  line-height: 1.5;
}
.roles-body li + li {
  margin-top: 0.25rem;
}
.roles-body p {
  font-size: 0.875rem;
  line-height: 1.5;
}
</style>
