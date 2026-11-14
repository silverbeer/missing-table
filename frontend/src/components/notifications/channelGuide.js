/**
 * Channel setup guide content (SB-1672).
 *
 * One entry per channel type, each with Slack / Telegram / Discord steps.
 * Kept as data so the words can be reviewed and tested without the component.
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
  { id: 'announce', label: 'Club announcements' },
  { id: 'fans', label: 'Fan chat' },
  { id: 'players', label: 'Players' },
];

// "Start here": the model every club follows, IFA as the worked example.
export const START = {
  intro:
    'Missing Table posts live match updates (kickoff, goals, half time, full time) into chat rooms your club runs. You own and moderate the rooms; Missing Table only posts into them and decides who sees each invite link.',
  types: [
    {
      tab: 'announce',
      title: 'Club announcements (read-only)',
      text: 'One room for the whole club. Missing Table posts, members only read and react. The easiest place to start.',
    },
    {
      tab: 'fans',
      title: 'Fan chat',
      text: 'A room where parents and fans talk, club-wide or one per squad (e.g. U15). Squad rooms are private: fans request access in Missing Table and you approve.',
    },
    {
      tab: 'players',
      title: 'Players',
      text: "Read-only rooms for a squad's players, with reactions. Players are kept apart from fans. Check the platform's minimum age first.",
    },
  ],
  example: [
    'Fans on Slack: #ifa-announcements (read-only), #ifa-fans, and a private #ifa-u15-fans per squad.',
    'Players on Discord: a read-only #ifa-u15-players per squad, visible only to that squad’s role.',
  ],
  advice: [
    'Pick one platform per audience. A second app splits the conversation, and a fan in both gets every update twice.',
    'An invite link admits people to the whole Slack workspace or Discord server, not one channel. Private channels (Slack), roles (Discord) or separate groups (Telegram) are what keep squads apart.',
    'Private (Slack), role-only (Discord) and approval-only links (Telegram) keep a room off other people’s lists. They do not stop a member forwarding what they see, so post nothing you would not share.',
    'Never send an invite link by email. Members find it in Missing Table under Profile → Community channels, and only once they qualify.',
  ],
  order: [
    'Create the room on the platform and set its permissions (the tabs below).',
    'Connect Missing Table: a webhook URL (Slack, Discord) or our bot plus the chat ID (Telegram).',
    'Make an invite link.',
    'In Missing Table: club rooms under your Profile → Club chat channels; squad rooms on the team page → Manage chat channels. Add a channel, then Send test.',
    'Members join from Profile → Community channels. Approve squad requests in Manage chat channels.',
  ],
};

// Registering the room in Missing Table, per channel type.
const REGISTER = {
  announce: [
    'Profile → Club chat channels → Add a channel (admins: Admin → Live Match Notifications → your club).',
    'Who it’s for: Fans. What to post: Every match event.',
    'Paste the webhook URL or chat ID and the invite link, then Add channel → Send test.',
  ],
  fans: [
    'Club-wide room: Profile → Club chat channels → Add a channel.',
    'Squad room: team page → Manage chat channels → pick the squad → Add a channel.',
    'Who it’s for: Fans. Paste the webhook URL or chat ID and the invite link, then Add channel → Send test.',
  ],
  players: [
    'Team page → Manage chat channels → pick the squad → Add a channel (or Profile → Club chat channels for a club-wide player room).',
    'Who it’s for: Players. Players on that squad see a Join button; fans never see player rooms.',
    'Paste the webhook URL or chat ID and the invite link, then Add channel → Send test.',
  ],
};

const SLACK_WEBHOOK = [
  'Go to api.slack.com/apps → Create New App → Pick features. Name it “Missing Table” and pick your workspace.',
  'Open Incoming Webhooks and turn on Activate Incoming Webhooks.',
  'Click Add New Webhook to Workspace, pick the channel, and click Authorize. For a private channel, join it first or it will not be listed.',
  'Copy the webhook URL (https://hooks.slack.com/services/…). Treat it like a password. One webhook per channel; reuse the same app for the others.',
];

const SLACK_INVITE = [
  'Workspace name → Invite people → Copy invite link. Edit link settings to choose when it expires.',
  'A link works for up to 400 people and lasts 30 days by default. When it runs out, make a new one and update it in Missing Table. Links cannot be made in the Android app.',
];

const TELEGRAM_BOT = [
  'Add @missingtable_bot to the room. In a channel it must be an admin with Post Messages; in a group, a member is enough.',
  'Find the chat ID: open the room at web.telegram.org and copy the number in the address bar. Channels and supergroups start with -100. If Send test fails, try adding -100 in front.',
];

const DISCORD_WEBHOOK = [
  'You need the Manage Webhooks permission.',
  'Edit Channel (gear icon) → Integrations → Webhooks → New Webhook. Name it “Missing Table”, check the channel, then Copy Webhook URL. Treat it like a password.',
];

const DISCORD_INVITE = [
  'Right-click a channel everyone can see → Invite People → Edit invite link. Set Max uses to No limit. “Never” expires is only offered on Community servers; otherwise links last at most 30 days.',
  'The link admits people to the whole server. Make it from a channel everyone can see, not a private one.',
];

export const GUIDE = {
  announce: {
    slack: {
      summary:
        'A public channel only admins post in. Make it a default channel so new members land in it.',
      steps: [
        'Create a public channel, e.g. #ifa-announcements.',
        'Click the channel name → Settings → Posting permissions → Edit. Choose who may post (you and your managers), then Save Changes. Everyone else can only read.',
        'Make it a default channel: Admin (sidebar) → Workspace settings → Default Channels → Expand → add it. Owners and admins only; it applies to people who join from now on.',
        'Check from a member account that they can react. Slack’s help does not say whether reactions stay on.',
      ],
      connect: SLACK_WEBHOOK,
      invite: SLACK_INVITE,
      notes: [
        'Slack does not allow anyone under 16. Use it for parents and fans.',
        'The free plan allows 10 apps and keeps 90 days of history.',
      ],
    },
    telegram: {
      summary:
        'Use a Telegram channel: it is read-only by design. Turn on reactions so members can respond.',
      steps: [
        'New Channel (pencil button on Android, the icon at the top of Chats on iPhone). Name it, e.g. “IFA Announcements”, and make it private.',
        'Channel info → Edit → Reactions: choose which reactions members may use.',
        'Optional: link a discussion group if you also want fans to talk (see Fan chat).',
      ],
      connect: TELEGRAM_BOT,
      invite: [
        'Channel info → Invite Links → create a link. You can name it and set an expiry or usage limit.',
      ],
      notes: [
        'Telegram requires members in the EU, UK and Australia to be 18 or older.',
      ],
    },
    discord: {
      summary:
        'A text channel where @everyone can read and react but not post.',
      steps: [
        'Create a text channel, e.g. #ifa-announcements.',
        'Edit Channel → Permissions → @everyone: deny Send Messages, Send Messages in Threads, Create Public Threads and Create Private Threads. Allow View Channel, Read Message History and Add Reactions.',
        'Check no other role gives Send Messages back, then test from a member account.',
      ],
      connect: DISCORD_WEBHOOK,
      invite: DISCORD_INVITE,
      notes: [
        'Discord requires members to be at least 13, and older in some countries.',
        'For one post per match, use a Forum channel instead and tick “One post per match” in Missing Table.',
      ],
    },
  },

  fans: {
    slack: {
      summary:
        'A public #club-fans for everyone, plus a private channel per squad that you add approved fans to.',
      steps: [
        'Club room: create a public channel, e.g. #ifa-fans. Add it to Default Channels so new members join it.',
        'Squad room: + → Channel → name it (e.g. #ifa-u15-fans) → make it Private → Create.',
        'When you approve a squad request in Missing Table, add that person to the private channel in Slack. The invite link only gets them into the workspace.',
      ],
      connect: SLACK_WEBHOOK,
      invite: [
        'Use the same workspace invite link for every channel.',
        ...SLACK_INVITE,
      ],
      notes: [
        'Anyone in the workspace can see and join every public channel. Keep unrelated channels private.',
      ],
    },
    telegram: {
      summary:
        'A group per room. Groups have their own links, so squads stay separate without extra work.',
      steps: [
        'New Group (desktop: top-left menu → New Group). Name it, e.g. “IFA U15 Fans”.',
        'Add @missingtable_bot as a member.',
        'For a squad room, make the invite link ask for approval (below), so only people you approved in Missing Table get in.',
      ],
      connect: TELEGRAM_BOT,
      invite: [
        'Group info → Add Member → Invite to Group via Link → create an additional link with Request Admin Approval on.',
        'Requests appear in a bar at the top of the chat; approve the people you approved in Missing Table.',
      ],
      notes: [
        'Telegram requires members in the EU, UK and Australia to be 18 or older.',
      ],
    },
    discord: {
      summary:
        'A channel for the club, and a private channel per squad that only that squad’s role can see.',
      steps: [
        'Club room: a text channel everyone can see, e.g. #ifa-fans.',
        'Squad room: create a role (e.g. “U15 Fans”), then a channel → Edit Channel → Permissions → turn on Private Channel → add the role.',
        'When you approve a squad request in Missing Table, give that person the squad’s role in Discord. The invite link only gets them into the server.',
      ],
      connect: DISCORD_WEBHOOK,
      invite: DISCORD_INVITE,
      notes: [
        'Discord requires members to be at least 13, and older in some countries.',
      ],
    },
  },

  players: {
    slack: {
      summary:
        'Not recommended for players: Slack does not allow anyone under 16.',
      steps: [
        'Missing Table offers Slack player rooms only for U17 squads and older.',
        'If you use it: a private channel per squad, Posting permissions limited to managers, and test reactions from a player account.',
      ],
      connect: SLACK_WEBHOOK,
      invite: SLACK_INVITE,
      notes: [
        'Slack does not allow anyone under 16.',
        'Players and fans must never share a workspace channel.',
      ],
    },
    telegram: {
      summary: 'A private read-only channel per squad, with reactions on.',
      steps: [
        'New Channel → private → name it, e.g. “IFA U15 Players”.',
        'Channel info → Edit → Reactions: allow reactions.',
        'Make its invite link ask for approval and approve only players on the squad.',
      ],
      connect: TELEGRAM_BOT,
      invite: [
        'Channel info → Invite Links → create a link with Request Admin Approval on.',
      ],
      notes: [
        'Telegram requires members in the EU, UK and Australia to be 18 or older, which rules out most players there.',
      ],
    },
    discord: {
      summary:
        'The recommended home for players: a read-only channel per squad, visible only to that squad’s role.',
      steps: [
        'Create a role per squad (e.g. “U15 Players”).',
        'Create the channel → Edit Channel → Permissions → turn on Private Channel → add the squad role.',
        'For the role: deny Send Messages, Send Messages in Threads, Create Public Threads and Create Private Threads. Allow View Channel, Read Message History and Add Reactions.',
        'When a player joins from Missing Table, give them the squad role. Test from a player account that they can react but not post.',
      ],
      connect: DISCORD_WEBHOOK,
      invite: DISCORD_INVITE,
      notes: [
        'Missing Table offers Discord player rooms for U14 squads and older: Discord requires members to be at least 13.',
        'Keep fans out of the players’ server, or at least out of every player channel.',
      ],
    },
  },
};

export const registerSteps = tab => REGISTER[tab] || [];
