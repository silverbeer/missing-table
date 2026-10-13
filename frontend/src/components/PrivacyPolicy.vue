<template>
  <article
    class="max-w-3xl mx-auto bg-card rounded-xl shadow-sm ring-1 ring-line p-5 sm:p-8 text-fg privacy-policy"
    data-testid="privacy-policy"
  >
    <h1 class="text-2xl sm:text-3xl font-bold mb-1">Privacy Policy</h1>
    <p class="text-sm text-fg-muted mb-6">Effective {{ effectiveDate }}</p>

    <p>
      Missing Table is an invite-only service for youth soccer standings, scores
      and live match updates.
    </p>

    <h2>What we collect</h2>
    <p>
      Information you give us when you create an account, such as your name,
      email address and username; optional details you choose to add, such as
      photos and social media handles; content you post, such as live chat
      messages; team rosters and match information entered by club and team
      managers; and basic technical information needed to run the service and
      keep it secure.
    </p>

    <h2>How we use it</h2>
    <p>
      To run Missing Table, show you the information your role allows, send you
      notifications you ask for, answer support requests, and keep the service
      secure. We do not sell your information or use it for advertising.
    </p>

    <h2>Sharing</h2>
    <p>
      We share information only with service providers that help us run Missing
      Table, and only for that purpose. They are required to protect it at least
      as well as this policy does. We may disclose information if the law
      requires it.
    </p>

    <h2>Retention and deletion</h2>
    <p>
      We keep your information while your account exists. You can edit your
      profile at any time. To delete your account, email
      <SupportEmailLink subject="Delete my account" />.
    </p>

    <h2>Changes</h2>
    <p>We'll post any changes on this page.</p>

    <h2>Contact</h2>
    <p><SupportEmailLink subject="Privacy question" /></p>

    <p class="mt-8">
      <a href="/" class="privacy-back-link" data-testid="privacy-home-link"
        >← Back to Missing Table</a
      >
    </p>
  </article>
</template>

<script>
import SupportEmailLink from '@/components/SupportEmailLink.vue';

// Public page (SB-1310): rendered at /privacy for everyone, signed in or not.
// Opened from the iOS app and the App Store listing, so it must never depend
// on auth state or the API. Deliberately generic and unlinked on the web
// (SB-1328): no vendors or technical detail.
export const PRIVACY_EFFECTIVE_DATE = 'October 13, 2026';

export default {
  name: 'PrivacyPolicy',
  components: { SupportEmailLink },
  setup() {
    return { effectiveDate: PRIVACY_EFFECTIVE_DATE };
  },
};
</script>

<style scoped>
.privacy-policy {
  line-height: 1.65;
}

.privacy-policy h2 {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 2rem;
  margin-bottom: 0.5rem;
}

.privacy-policy p {
  margin-bottom: 0.75rem;
}

.privacy-back-link {
  color: #2563eb;
  font-weight: 500;
}

.privacy-back-link:hover {
  text-decoration: underline;
}
</style>
