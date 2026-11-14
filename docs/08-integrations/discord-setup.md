# Discord setup for a club or squad (SB-1612)

This guide is for the manager who runs the Discord server. Missing Table is independent community software: it posts match updates into your channels, and **you own and moderate the server**. MT never calls a channel private or verified: anyone who has an invite link can pass it on.

**Age:** Discord requires members to be at least 13, and older in some countries ([Discord support](https://support.discord.com/hc/articles/360040724612), [Terms](https://discord.com/terms)). That is why MT offers Discord player channels from U14 up.

## Recommended layout

| Channel | Type | Who | What posts there |
|---|---|---|---|
| `#match-updates` | Text | fans | Missing Table, through a webhook |
| `#match-threads` | Forum | fans | Missing Table: one post per match, updates as replies |
| `#ifa-announcements` (players, U14+) | Text, read-only | every player in the club | Missing Table (every squad's match updates) + managers; players react and cheer the other squads |
| `#ifa-hg-u15` (squad chat) | Text | that squad's players | the squad's own chat, plus Missing Table's updates for that squad |

Fans and players are kept on separate servers (or at least separate channels). MT's access rules never show a player channel to a fan, or a fan channel to a player.

## 1. Webhook for match updates

1. You need the **Manage Webhooks** permission.
2. Open `#match-updates` → gear icon → **Integrations → Webhooks → New Webhook**.
3. Name it `Missing Table`, check the channel, and **Copy Webhook URL**. It works like a password: anyone with it can post.
4. In Missing Table, open your club or team page → **Manage chat channels** → add a Discord channel and paste the URL. Click **Send test**.

Point this webhook at a **text** channel. For one post per match, use a forum channel instead (section 2).

## 2. Forum channel for match threads (SB-1606)

With a forum channel, each match gets its own post ("IFA vs NEFC · U15 · Sat Nov 14"), and kickoff, goals and the final score go into it as replies.

1. **Create Channel → Forum**, name it `#match-threads`. Add tags if you like (`League`, `Flex`, `Tournament`).
2. In the forum channel: gear icon → **Integrations → Webhooks → New Webhook**, and copy its URL.
3. In Missing Table, add a Discord channel with that URL and tick **One post per match**.
4. Click **Send test**. MT creates a post called "Missing Table test", then replies inside it using the thread id Discord sent back. If both appear in the same post, threads work. Delete the test post afterwards.

A webhook into a forum channel needs **One post per match** ticked. Without it Discord rejects every post, and the channel's Last post shows the error. A text channel must leave it unticked: Discord only accepts `thread_name` in forum and media channels.

A club players channel always posts flat, because read-only permissions are not confirmed to work with forum posts.

## 3. Player channels (SB-1673)

Players get two channels. Give every player an **IFA Players** role and their squad's role (e.g. **IFA HG U15**) when they join from MT.

**Squad chat** (`#ifa-hg-u15`): Private Channel, visible to the squad's role, with **Send Messages left on**. It is the team's chat; MT posts that squad's match updates into it too.

**Club announcements** for players, read-only with reactions. Players react; only managers and MT post.

1. Open `#ifa-announcements` → gear icon → **Permissions** → add **@everyone**, or the players' role.
2. **Deny:** Send Messages, Send Messages in Threads, Create Public Threads, Create Private Threads.
3. **Allow:** View Channel, Read Message History, Add Reactions. Reacting needs Read Message History.
4. Check no other role gives **Send Messages** back. A role-level allow on another role can undo the channel deny.
5. Log in as a test player account and check that you can react and can't type here, and can chat in the squad channel.

> **Not yet verified on a live server.** The permission names come from [Discord's permission reference](https://docs.discord.com/developers/topics/permissions.md). One community report says Read Message History is needed to add reactions. Step 5 is the check: run it once on a real channel before relying on this guide.

The webhook still posts, because webhooks are not bound by channel permissions.

## 4. Invite link

**Server Settings → Invites**, or right-click the channel → **Invite People** → **Edit invite link**:
- Set it to **never expire**, so the link you save in MT keeps working.
- Paste it into the channel's **Invite link** field in MT.

MT shows the link only to people its rules allow: approved fans, or players on the squad. They can still forward it. Remove someone on Discord itself if you need to.
