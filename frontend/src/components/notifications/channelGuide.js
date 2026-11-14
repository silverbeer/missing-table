/**
 * Channel setup guide content (SB-1672, SB-1673).
 *
 * Words: Slack, Telegram and Discord are *platforms*; what they host are
 * *channels*. Missing Table's people are fans, players, club managers and team
 * managers, nobody else.
 *
 * A tab per audience (fans, players). Each has two channels: club
 * announcements (read-only) and chat (fan chat / squad chat), with steps per
 * platform. Kept as data so the words can be reviewed and tested without the
 * component.
 *
 * Platform facts were checked against the vendors' own help pages on
 * 2026-11-13 (sources in docs/08-integrations/channel-setup-guide.md). Where a
 * vendor page did not settle a detail, the step tells the manager to check it
 * in their app rather than asserting it.
 */

export const PLATFORMS = [
  { id: 'slack', label: 'Slack' },
  { id: 'telegram', label: 'Telegram' },
  { id: 'discord', label: 'Discord' },
];

export const TABS = [
  { id: 'start', label: 'Start here' },
  { id: 'fans', label: 'Fans' },
  { id: 'players', label: 'Players' },
];

// "Start here": the decision first (SB-1673), then where to go next.
export const START = {
  lead: 'Missing Table posts live match updates into your club’s channels on Slack, Telegram or Discord. First pick a platform for each group:',
  decisions: [
    {
      who: 'Players, U14 and up',
      pick: 'Discord',
      tab: 'players',
      platform: 'discord',
      why: 'The only platform Missing Table supports for players. Two channels: club announcements, where players react and cheer the club’s other squads, and a squad channel for team chat.',
    },
    {
      who: 'Fans',
      pick: 'Slack',
      tab: 'fans',
      platform: 'slack',
      why: 'Most adults already use Slack at work; few use Discord or Telegram.',
    },
  ],
  both: 'Some fans would rather use Telegram on their phone. You can run Telegram for fans alongside Slack: both get the same updates, and each fan joins one.',
  example:
    'IFA: fans on Slack; players on Discord, with #ifa-announcements and a squad channel such as #ifa-hg-u15.',
  next: [
    {
      tab: 'fans',
      text: 'club announcements (read-only) and fan chat.',
    },
    {
      tab: 'players',
      text: 'club announcements (read-only, with reactions) and a chat channel per squad.',
    },
  ],
  goodToKnow: [
    'An invite link lets people into your whole Slack workspace or Discord server. Private channels (Slack) and roles (Discord) keep squads apart.',
    'Members can still forward what they see. Post nothing you would not share.',
    'Never send an invite link by email. Members find it in Missing Table under Profile → Community channels.',
  ],
};

// Adding the channels in Missing Table, per audience.
const REGISTER = {
  fans: [
    'Club announcements and club-wide fan chat: Profile → Club chat channels → Add a channel (admins: Admin → Live Match Notifications → your club).',
    'Squad fan chat: team page → Manage chat channels → pick the squad → Add a channel.',
    'Who it’s for: Fans. Paste the webhook URL or chat ID and the invite link, then Add channel → Send test.',
  ],
  players: [
    'Club announcements: Profile → Club chat channels → Add a channel → Who it’s for: Players.',
    'Squad chat: team page → Manage chat channels → pick the squad → Add a channel → Who it’s for: Players.',
    'Paste the webhook URL and the invite link, then Add channel → Send test.',
    'Players on the club’s U14 and older squads see Join for club announcements, and players on the squad see it for squad chat. Fans never see player channels.',
  ],
};

const SLACK_WEBHOOK = [
  'Go to api.slack.com/apps → Create New App → Pick features. Name it “Missing Table” and pick your workspace.',
  'Open Incoming Webhooks and turn on Activate Incoming Webhooks.',
  'Click Add New Webhook to Workspace, pick the channel, and click Authorize. For a private channel, join it first or it will not be listed.',
  'Copy the webhook URL (https://hooks.slack.com/services/…). Treat it like a password. One webhook per channel; reuse the same app for the others.',
];

const SLACK_INVITE = [
  'One workspace invite link covers every channel: workspace name → Invite people → Copy invite link. Edit link settings to choose when it expires.',
  'A link works for up to 400 people and lasts 30 days by default. When it runs out, make a new one and update it in Missing Table. Links cannot be made in the Android app.',
];

const TELEGRAM_BOT = [
  'Add @missingtable_bot to each channel and group. In a channel it must be an admin with Post Messages; in a group, a member is enough.',
  'Find the chat ID: open it at web.telegram.org and copy the number in the address bar. Channels and supergroups start with -100. If Send test fails, try adding -100 in front.',
];

const DISCORD_WEBHOOK = [
  'You need the Manage Webhooks permission.',
  'In each channel: Edit Channel (gear icon) → Integrations → Webhooks → New Webhook. Name it “Missing Table”, check the channel, then Copy Webhook URL. Treat it like a password.',
];

const DISCORD_INVITE = [
  'Right-click a channel everyone can see → Invite People → Edit invite link. Set Max uses to No limit. “Never” expires is only offered on Community servers; otherwise links last at most 30 days.',
  'The link admits people to the whole server. Make it from a channel everyone can see, not a private one.',
];

const DISCORD_READ_ONLY =
  'deny Send Messages, Send Messages in Threads, Create Public Threads and Create Private Threads. Allow View Channel, Read Message History and Add Reactions.';

export const GUIDE = {
  fans: {
    slack: {
      summary:
        'Both channels live in one workspace: a read-only club announcements channel, and fan chat.',
      channels: [
        {
          title: 'Club announcements (read-only)',
          steps: [
            'Create a public channel, e.g. #ifa-announcements.',
            'Click the channel name → Settings → Posting permissions → Edit. Choose who may post (you and your managers), then Save Changes. Everyone else can only read.',
            'Make it a default channel: Admin (sidebar) → Workspace settings → Default Channels → Expand → add it. Owners and admins only; it applies to people who join from now on.',
            'Check from a fan account that they can react. Slack’s help does not say whether reactions stay on.',
          ],
        },
        {
          title: 'Fan chat',
          steps: [
            'Club-wide: create a public channel, e.g. #ifa-fans, and add it to Default Channels.',
            'Per squad: + → Channel → name it (e.g. #ifa-hg-u15-fans) → make it Private → Create.',
            'When you approve a squad request in Missing Table, add that fan to the private channel in Slack. The invite link only gets them into the workspace.',
          ],
        },
      ],
      connect: SLACK_WEBHOOK,
      invite: SLACK_INVITE,
      notes: [
        'Slack does not allow anyone under 16.',
        'The free plan allows 10 apps and keeps 90 days of history.',
        'Anyone in the workspace can see and join every public channel. Keep unrelated channels private.',
      ],
    },
    telegram: {
      summary:
        'A Telegram channel for club announcements (read-only by design), and a group for each fan chat.',
      channels: [
        {
          title: 'Club announcements (read-only)',
          steps: [
            'New Channel (pencil button on Android, the icon at the top of Chats on iPhone). Name it, e.g. “IFA Announcements”, and make it private.',
            'Channel info → Edit → Reactions: choose which reactions fans may use.',
          ],
        },
        {
          title: 'Fan chat',
          steps: [
            'New Group (desktop: top-left menu → New Group). Name it, e.g. “IFA Fans” or “IFA HG U15 Fans”.',
            'Each group has its own invite link, so squads stay separate without extra work.',
          ],
        },
      ],
      connect: TELEGRAM_BOT,
      invite: [
        'Each channel and group has its own link: Info → Invite Links (groups: Add Member → Invite to Group via Link) → create a link.',
        'For a squad’s fan chat, turn on Request Admin Approval. Requests appear in a bar at the top of the chat; approve the fans you approved in Missing Table.',
      ],
      notes: [
        'Telegram requires members in the EU, UK and Australia to be 18 or older.',
      ],
    },
    discord: {
      summary:
        'A read-only club announcements channel and fan chat, in a server separate from your players.',
      channels: [
        {
          title: 'Club announcements (read-only)',
          steps: [
            'Create a text channel, e.g. #ifa-announcements.',
            `Edit Channel → Permissions → @everyone: ${DISCORD_READ_ONLY}`,
            'Check no other role gives Send Messages back, then test from a fan account.',
          ],
        },
        {
          title: 'Fan chat',
          steps: [
            'Club-wide: a text channel everyone can see, e.g. #ifa-fans.',
            'Per squad: create a role (e.g. “IFA HG U15 Fans”), then a channel → Edit Channel → Permissions → turn on Private Channel → add the role.',
            'When you approve a squad request in Missing Table, give that fan the squad’s role in Discord. The invite link only gets them into the server.',
          ],
        },
      ],
      connect: DISCORD_WEBHOOK,
      invite: DISCORD_INVITE,
      notes: [
        'Discord requires members to be at least 13, and older in some countries.',
        'For one post per match, use a Forum channel instead and tick “One post per match” in Missing Table.',
      ],
    },
  },

  players: {
    // Fans only (SB-1673): these platforms' age limits rule out most squads.
    slack: {
      unavailable: true,
      summary:
        'Missing Table does not support Slack for players: Slack does not allow anyone under 16, and U17 squads include 15-year-olds. Use Discord.',
    },
    telegram: {
      unavailable: true,
      summary:
        'Missing Table does not support Telegram for players: Telegram requires members in the EU, UK and Australia to be 18 or older. Use Discord.',
    },
    discord: {
      summary:
        'Players get two channels, and both get match updates: club announcements, where they react and cheer the club’s other squads, and a squad channel for team chat.',
      channels: [
        {
          title: 'Club announcements (read-only, with reactions)',
          steps: [
            'Create a role for every player, e.g. “IFA Players”.',
            'Create #ifa-announcements → Edit Channel → Permissions → turn on Private Channel → add the IFA Players role.',
            `For IFA Players: ${DISCORD_READ_ONLY}`,
            'Every squad’s match updates land here, so players can cheer the rest of the club.',
          ],
        },
        {
          title: 'Squad chat',
          steps: [
            'Create a role per squad, e.g. “IFA HG U15”.',
            'Create #ifa-hg-u15 → Edit Channel → Permissions → turn on Private Channel → add the squad role. Leave Send Messages on: this is the team’s chat.',
            'Missing Table posts that squad’s match updates here too.',
            'When a player joins from Missing Table, give them IFA Players and their squad role. Test from a player account: they can react but not post in announcements, and chat in their squad channel.',
          ],
        },
      ],
      connect: DISCORD_WEBHOOK,
      invite: DISCORD_INVITE,
      notes: [
        'Missing Table supports Discord player channels for U14 squads and older: Discord requires members to be at least 13.',
        'Use a separate server for players, so fans never see player channels.',
        'Squad chat is players talking to each other. You and your team managers moderate it.',
      ],
    },
  },
};

export const registerSteps = tab => REGISTER[tab] || [];
