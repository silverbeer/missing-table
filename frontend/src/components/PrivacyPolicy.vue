<template>
  <article
    class="max-w-3xl mx-auto bg-card rounded-xl shadow-sm ring-1 ring-line p-5 sm:p-8 text-fg privacy-policy"
    data-testid="privacy-policy"
  >
    <h1 class="text-2xl sm:text-3xl font-bold mb-1">Privacy Policy</h1>
    <p class="text-sm text-fg-muted mb-6">
      Effective {{ effectiveDate }} · Applies to the Missing Table website
      (missingtable.com) and the Missing Table iOS app.
    </p>

    <p>
      Missing Table publishes standings, scores and live match updates for youth
      soccer leagues. It is invite-only. This policy explains, in plain
      language, what information we hold, why, who helps us process it, and how
      you can ask us to change or delete it.
    </p>

    <h2>Information we collect</h2>

    <h3>Account information</h3>
    <p>When you accept an invite and create an account, we store:</p>
    <ul>
      <li>your email address, username and display name;</li>
      <li>
        your role (for example fan, team manager or club manager) and the club
        or team your invite connects you to;
      </li>
      <li>
        your password, which is handled by our authentication provider and
        stored only in hashed form — or, if you sign in with Google, your name,
        email address and Google profile picture as provided by Google;
      </li>
      <li>
        optional profile details you choose to add, such as first and last name,
        phone number, hometown, jersey number, positions, profile photos, and
        Instagram, Snapchat, TikTok, Telegram or Discord handles;
      </li>
      <li>
        your preferences, such as the teams and brackets you follow and your
        notification settings.
      </li>
    </ul>
    <p>
      If you request an invite, we store the name, email address, team and
      message you submit so an administrator can review it.
    </p>

    <h3>Player and roster information</h3>
    <p>
      Team rosters are entered by club and team managers, not by the players
      themselves. A roster entry can include a player's first and last name,
      jersey number and positions, along with match lineups and statistics such
      as goals, cards and minutes played. Many players are minors. Roster
      entries do not need a Missing Table account, and we do not ask for a
      player's date of birth, address or contact details.
    </p>

    <h3>Match information</h3>
    <p>
      Fixtures, scores, standings, goal scorers, cards, lineups and match photos
      are entered by managers and administrators, or collected from publicly
      published league schedules and results.
    </p>

    <h3>Live match chat</h3>
    <p>
      Messages you post in a live match's chat are stored with your username and
      are visible to other signed-in users. Chat messages are deleted
      automatically after about 10 days.
    </p>

    <h3>Push notifications</h3>
    <p>
      If you turn on notifications, we store what your device needs to receive
      them: on iPhone, an Apple Push Notification service (APNs) device token
      plus the app version and a device label; in a web browser (including on
      Android), a web push subscription plus your browser's user agent. We keep
      a log of notifications sent to you. You can turn notifications off at any
      time in the app or your device settings.
    </p>

    <h3>Support email</h3>
    <p>
      If you email us, we keep the messages in our support inbox so we can
      answer you and follow up.
    </p>

    <h3>Sign-in and usage information</h3>
    <p>
      For security, we record sign-in attempts: the username, whether the
      attempt succeeded, your role and your IP address. Our servers also keep
      ordinary operational logs.
    </p>
    <p>
      The website uses Grafana Faro to help us find bugs and performance
      problems. It records page-load performance measurements, JavaScript
      errors, browser console messages, the timing of requests the site makes to
      our servers, which sections of the site are viewed, and a random session
      identifier stored in your browser. It is used only to keep the site
      working. We do not attach your name or email address to this data. The iOS
      app does not include any third-party analytics or advertising SDKs.
    </p>

    <h2>How we use information</h2>
    <ul>
      <li>
        to run Missing Table: show standings, scores and rosters, and power live
        match updates and chat;
      </li>
      <li>
        to control who can see and edit what, based on your role and club or
        team;
      </li>
      <li>
        to send you the notifications and emails you ask for, such as invites,
        password resets and match alerts;
      </li>
      <li>to answer support requests;</li>
      <li>to keep the service secure and fix problems.</li>
    </ul>
    <p>
      <strong>We do not sell your information</strong>, and we do not use it for
      advertising. Missing Table has no ads and no advertising or cross-site
      tracking.
    </p>

    <h2>Who we share it with</h2>
    <p>
      Other signed-in users can see the league, team and roster information
      their role allows, and the chat messages and usernames in live matches.
      Beyond that, we share information only with the service providers that run
      Missing Table for us, and only so they can do so:
    </p>
    <ul>
      <li>Supabase — database, sign-in and profile photo storage;</li>
      <li>Linode (Akamai) — the cloud servers that run the application;</li>
      <li>Cloudflare R2 — storage for match photos;</li>
      <li>Resend — sending and receiving email;</li>
      <li>Apple — delivering push notifications to iPhones;</li>
      <li>
        your browser's push service (for example Google or Mozilla) — delivering
        web push notifications;
      </li>
      <li>Grafana — the website diagnostics described above;</li>
      <li>Google — only if you choose to sign in with Google.</li>
    </ul>
    <p>
      An optional AI assistant, where offered, uses Google Gemini to generate
      answers.
    </p>
    <p>We may also disclose information if the law requires it.</p>

    <h2>How long we keep it</h2>
    <p>
      We keep account and profile information while your account exists. Live
      chat messages are deleted after about 10 days. Device tokens and push
      subscriptions are removed when you delete your account, and those that
      stop working are removed automatically. Rosters, match results and
      statistics form part of a league's historical record and are kept unless a
      club or team manager removes them or you ask us to.
    </p>

    <h2>Your choices and deleting your data</h2>
    <p>
      You can update your profile, remove profile photos and turn off
      notifications yourself. To delete your account, or to ask us to correct or
      remove other information — including a player's roster entry — email
      <SupportEmailLink
        subject="Privacy request"
        data-testid="privacy-contact"
      />. We may need to confirm the request comes from you, or from the
      player's parent or guardian. When we delete an account, its devices,
      follows and preferences are deleted with it. We may keep a record of
      support correspondence about the request.
    </p>

    <h2>Children</h2>
    <p>
      Missing Table covers youth soccer. Accounts exist only by invitation from
      Missing Table or from a club or team manager. Some accounts belong to
      youth players and are created through their club or team's invitation.
      Players' roster information is provided by their club or team. A parent or
      guardian can ask us to review or delete a child's information by emailing
      the address below.
    </p>

    <h2>Security</h2>
    <p>
      Information is sent over encrypted (HTTPS) connections, access to data is
      restricted by role, and passwords are never stored in plain text. No
      system is perfectly secure, but we work to protect your information and
      limit who can reach it.
    </p>

    <h2>Changes to this policy</h2>
    <p>
      If we change this policy, we will post the new version on this page with a
      new effective date.
    </p>

    <h2>Contact</h2>
    <p>
      Questions or requests about privacy:
      <SupportEmailLink subject="Privacy question" />.
    </p>

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
// Linked from the App Store / TestFlight listing, so it must never depend on
// auth state or the API.
export const PRIVACY_EFFECTIVE_DATE = 'October 10, 2026';

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

.privacy-policy h3 {
  font-size: 1rem;
  font-weight: 600;
  margin-top: 1.25rem;
  margin-bottom: 0.25rem;
}

.privacy-policy p {
  margin-bottom: 0.75rem;
}

.privacy-policy ul {
  list-style: disc;
  padding-left: 1.5rem;
  margin-bottom: 0.75rem;
}

.privacy-policy li {
  margin-bottom: 0.25rem;
}

.privacy-back-link {
  color: #2563eb;
  font-weight: 500;
}

.privacy-back-link:hover {
  text-decoration: underline;
}
</style>
