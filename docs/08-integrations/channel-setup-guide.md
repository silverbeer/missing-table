# Channel setup guide for club managers (SB-1672, SB-1673)

The in-app guide club managers use to set up chat channels for Missing Table. It lives in the app, not here: managers never see this repo. This page records where it is, how it is built, and the sources behind every platform fact.

## Words

- **Platform**: Slack, Telegram or Discord. A platform hosts channels.
- **Channel**: what Missing Table posts into (a Slack channel, a Telegram channel or group, a Discord channel). Never "room".
- **People**: fans, players, club managers and team managers. Nobody else (no "parents", no "families").

## Where it is

`components/notifications/ChannelSetupGuide.vue`, a dialog opened from:

- **Setup guide: Slack, Telegram and Discord** in the header of every channel manager (Admin → Live Match Notifications, the club manager's Profile → Club chat channels, the team page → Manage chat channels). Not on the admin "Every match" feed.
- **Full guide** at the bottom of the channel form's "How to set up …" section. It opens at the audience being set up (Fans or Players), on the form's platform.

## Structure

Tabs: **Start here** · **Fans** · **Players**. Each audience tab has Slack / Telegram / Discord, and each platform has four steps: create the channels, connect Missing Table, make an invite link, add them in Missing Table. Notes carry age floors and plan limits.

Each audience gets two channels:

| Audience | Club announcements | Chat |
|---|---|---|
| Fans | read-only, every match update | fan chat: club-wide and/or one per squad (fans request a squad's, managers approve) |
| Players | read-only with reactions, every squad's match updates, so players cheer the club's other squads | squad chat (e.g. #ifa-hg-u15): the team's own chat, which also gets that squad's match updates |

**Start here leads with the decision** (SB-1673), not an explanation: two cards, **Players U14 and up → Discord** and **Fans → Slack** (most adults already use Slack at work; few use Discord or Telegram). Each card opens its tab on that platform. Below them: Telegram for fans may run alongside Slack, the IFA example, links to the two tabs, and a collapsed "Good to know".

On the Players tab, Slack and Telegram say why they are not offered and link to the Discord steps (`unavailable: true` in the data).

The words are data in `components/notifications/channelGuide.js`, tested in `__tests__/components/ChannelSetupGuide.spec.js` (every audience covers every platform with two channels; players get Discord only, with the reason for the others; players' announcements are read-only and squad chat is not; Start here leads with Discord for players and Slack for fans; no "parent", "famil" or "room"; nothing tells a manager to email a link).

The model it teaches (IFA as the example): fans on Slack (#ifa-announcements read-only, #ifa-fans, a private channel per squad), optionally Telegram for fans too; players on a separate Discord server (#ifa-announcements read-only for the IFA Players role, and #ifa-hg-u15 squad chat visible only to that squad's role).

## Which platform may host players

`min_player_age` on each adapter, enforced by `notifications/audience.py`:

| Platform | Player channels | Why |
|---|---|---|
| Discord | U14 and up (Missing Table's own floor) | Discord's minimum age is 13 |
| Slack | none, fans only (SB-1673; was U17) | Slack requires users over 16, and U17 squads include 15-year-olds |
| Telegram | none, fans only | Telegram requires 18+ in the EU, UK and Australia |

## Rules the guide follows

- SB-1612: rooms are community-run. Missing Table never promises a room is private; the guide names Slack's "Private" setting and Discord roles as platform settings, and says plainly that they do not stop forwarding.
- Invite links are never sent by email; members find them under Profile → Community channels (SB-1671).
- A Slack link admits people to the workspace and a Discord link to the server, so squads are separated on the platform: a private Slack channel the manager adds approved fans to, a Discord role, or a Telegram link with Request Admin Approval.

## Sources (checked 2026-11-13)

| Fact | Source |
|------|--------|
| Slack posting permissions (Settings → Posting permissions) | https://slack.com/help/articles/360004635551 |
| Slack default channels (Admin → Workspace settings) | https://slack.com/help/articles/201898998 |
| Slack private channels | https://slack.com/help/articles/201402297 |
| Slack incoming webhooks ("Pick features", "Authorize", join a private channel first) | https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/ |
| Slack free plan: 10 apps, 90 days history | https://slack.com/help/articles/115002422943 |
| Slack invite links: 400 uses, 30-day default, not on Android | https://slack.com/help/articles/201330256 |
| Slack minimum age 16 | https://slack.com/trust/privacy/privacy-policy |
| Telegram channels vs groups, reactions | https://telegram.org/faq_channels, https://telegram.org/faq |
| Telegram bot admin right `can_post_messages` | https://core.telegram.org/bots/api |
| Telegram chat id format (-100…) | https://core.telegram.org/api/bots/ids |
| Telegram invite links with Request Admin Approval | https://telegram.org/faq |
| Telegram minimum age 18 in the EU, UK and Australia | https://telegram.org/tos |
| Discord permissions (Send Messages in Threads not inherited) | https://docs.discord.com/developers/topics/permissions |
| Discord forum webhooks need `thread_name` / `thread_id` | https://docs.discord.com/developers/resources/webhook |
| Discord minimum age 13 (up to 16 by country) | https://discord.com/terms |

Not settled by the vendors' pages, so the guide tells the manager to check in their app: whether Slack members keep reactions in a posting-restricted channel; Discord's exact invite expiry menu ("Never" reportedly needs a Community server); finding a Telegram chat id via web.telegram.org. Discord's help centre could not be read directly, so its menu paths come from search excerpts of the official articles.
