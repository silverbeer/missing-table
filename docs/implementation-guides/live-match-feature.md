# 🔴 Live Match Feature - Implementation Plan

> **Audience**: Developers implementing the live match feature
> **Prerequisites**: Familiarity with Vue 3, FastAPI, Supabase, and the Missing Table architecture
> **Time to Complete**: 3-4 weeks (part-time development)
> **Difficulty**: 🔴 Advanced

This document provides a comprehensive, step-by-step implementation plan for adding live match functionality to Missing Table. This will be your next BIG feature after the production site goes live.

---

## 📋 Table of Contents

1. [Feature Overview](#-feature-overview)
2. [Technology Stack](#-technology-stack)
3. [Architecture Design](#-architecture-design)
4. [Implementation Phases](#-implementation-phases)
5. [Database Schema](#-database-schema)
6. [Backend API](#-backend-api)
7. [Frontend Components](#-frontend-components)
8. [Real-time Implementation](#-real-time-implementation)
9. [Security & Permissions](#-security--permissions)
10. [Testing Strategy](#-testing-strategy)
11. [Deployment Plan](#-deployment-plan)
12. [Performance Considerations](#-performance-considerations)
13. [Future Enhancements](#-future-enhancements)

---

## 🎯 Feature Overview

### User Stories

#### Admin / Game Manager
- ✅ Set a match as "live" from the match list
- ✅ Start/stop the match clock
- ✅ Update scores in real-time
- ✅ Pause the match (halftime)
- ✅ End the match
- ✅ Participate in live chat

#### Team Fan / Viewer
- ✅ See which matches are currently live
- ✅ View live match scores and clock
- ✅ Participate in live chat
- ✅ See how many people are watching

### Key Features
- **Real-time score updates** - All viewers see score changes instantly
- **Live match clock** - Running clock visible to all
- **Live chat** - Real-time messaging during the match
- **Presence tracking** - Show viewer count
- **Role-based permissions** - Only admins/managers can control the match

---

## 🛠️ Technology Stack

### Supabase Realtime Features

We will use all three Supabase Realtime capabilities:

| Feature | Purpose | Why |
|---------|---------|-----|
| **Postgres Changes** | Score updates, match status changes | Persistent data with automatic sync |
| **Broadcast** | Match clock ticks | Low-latency, no database spam |
| **Presence** | Viewer tracking | Built-in state synchronization |

### Supabase Plan Requirements

**Current Free Plan Limits:**
- 200 concurrent connections
- 100 messages/second
- 100 channel joins/second

**Recommendation**: Start with Free plan, upgrade to Pro ($25/month) when:
- You expect 200+ simultaneous viewers on a single match
- You have multiple live matches running simultaneously
- You need higher message throughput

**Pro Plan Benefits:**
- 500 concurrent connections
- 500 messages/second
- 3,000 KB broadcast payloads (vs 256 KB on free)

---

## 🏗️ Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Vue 3)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌──────────────────────────────┐    │
│  │  AdminPanel     │  │  LiveMatchViewer             │    │
│  │  (Control)      │  │  (Fan View)                  │    │
│  └────────┬────────┘  └──────────┬───────────────────┘    │
│           │                       │                         │
│           ▼                       ▼                         │
│  ┌─────────────────────────────────────────────┐          │
│  │     Supabase Realtime Client                │          │
│  │  - Postgres Changes (score, status)         │          │
│  │  - Broadcast (clock ticks)                  │          │
│  │  - Presence (viewer count)                  │          │
│  └────────────┬────────────────────────────────┘          │
│               │                                             │
└───────────────┼─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  API Endpoints                                     │   │
│  │  POST /api/live-matches/start                      │   │
│  │  POST /api/live-matches/{id}/update-score          │   │
│  │  POST /api/live-matches/{id}/toggle-clock          │   │
│  │  POST /api/live-matches/{id}/end                   │   │
│  │  GET  /api/live-matches/active                     │   │
│  └────────────┬───────────────────────────────────────┘   │
│               │                                             │
│               ▼                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  DAO Layer                                         │   │
│  │  - LiveMatchDAO                                    │   │
│  │  - ChatMessageDAO                                  │   │
│  └────────────┬───────────────────────────────────────┘   │
│               │                                             │
└───────────────┼─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                  Supabase Database                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────────────────┐     │
│  │  live_matches   │  │  match_chat_messages        │     │
│  │  - match_id     │  │  - match_id                 │     │
│  │  - status       │  │  - user_id                  │     │
│  │  - home_score   │  │  - username                 │     │
│  │  - away_score   │  │  - message                  │     │
│  │  - clock_secs   │  │  - created_at               │     │
│  │  - clock_run    │  │                             │     │
│  └─────────────────┘  └─────────────────────────────┘     │
│                                                             │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Realtime                                        │     │
│  │  - Postgres Changes (live_matches, chat)         │     │
│  │  - Broadcast (clock_tick)                        │     │
│  │  - Presence (viewers)                            │     │
│  └──────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

#### Score Update Flow
```
1. Admin clicks "Update Score" button
2. Frontend sends POST /api/live-matches/{id}/update-score
3. Backend validates permissions (admin/team_manager)
4. Backend updates database (live_matches table)
5. Supabase Postgres Changes triggers
6. All connected clients receive update event
7. Frontend updates UI automatically
```

#### Clock Tick Flow
```
1. Admin starts the clock
2. Backend sends broadcast message every second
3. All connected clients receive clock_tick event
4. Frontend updates clock display
5. Every 60 seconds, backend persists clock_seconds to database
   (for recovery if admin disconnects)
```

---

## 📅 Implementation Phases

### Phase 0: Planning & Preparation (Week 1)
**Status**: 📝 Current Phase

**Tasks**:
- ✅ Review this implementation plan
- ✅ Review Supabase Realtime documentation
- ✅ Set up development environment
- ✅ Create feature branch: `feature/live-match`
- ✅ Review existing codebase (matches, auth, roles)

**Deliverables**:
- Feature branch created
- Development environment ready
- Team alignment on approach

---

### Phase 1: Database Schema (Week 1)
**Difficulty**: 🟡 Intermediate

**Goal**: Create database tables for live matches and chat

#### Step 1.1: Create Migration File
```bash
cd supabase/migrations
touch 020_add_live_match_tables.sql
```

#### Step 1.2: Define Schema (see [Database Schema](#-database-schema) section below)

#### Step 1.3: Apply Migration
```bash
# Local testing
./switch-env.sh local
npx supabase db reset
./scripts/db_tools.sh restore

# Dev environment
./switch-env.sh dev
npx supabase db push
```

#### Step 1.4: Verify Schema
```bash
cd backend && uv run python inspect_db.py stats
```

**Deliverables**:
- ✅ `020_add_live_match_tables.sql` migration
- ✅ Tables created in local and dev databases
- ✅ RLS policies configured
- ✅ Indexes created for performance

**Testing**:
```bash
# Verify tables exist
cd backend
uv run python -c "
from dao.supabase_data_access import SupabaseConnection
conn = SupabaseConnection()
client = conn.get_client()
print(client.table('live_matches').select('*').limit(1).execute())
print(client.table('match_chat_messages').select('*').limit(1).execute())
"
```

---

### Phase 2: Backend API - Basic CRUD (Week 1-2)
**Difficulty**: 🟡 Intermediate

**Goal**: Create FastAPI endpoints for live match management

#### Step 2.1: Create DAO Layer
```bash
cd backend/dao
touch live_match_dao.py
```

**Contents**: See [Backend API](#-backend-api) section

#### Step 2.2: Create API Endpoints
```bash
cd backend
# Edit app.py or create backend/routers/live_matches.py
```

#### Step 2.3: Add Permission Checks
Reuse existing auth system:
```python
from auth import get_current_user, require_role

@router.post("/{live_match_id}/update-score")
async def update_score(
    live_match_id: str,
    home_score: int,
    away_score: int,
    current_user: dict = Depends(require_role(["admin", "team_manager"]))
):
    # Implementation
```

#### Step 2.4: Test with Bruno/Curl
```bash
# Create Bruno collection or test with curl
curl -X POST http://localhost:8000/api/live-matches/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"match_id": "..."}'
```

**Deliverables**:
- ✅ `LiveMatchDAO` class with CRUD operations
- ✅ API endpoints for start, update, end match
- ✅ Permission checks using existing auth
- ✅ API tests (Bruno collection or pytest)

**Testing**:
```bash
cd backend
uv run pytest tests/test_live_match_api.py -v
```

---

### Phase 3: Frontend - Admin Controls (Week 2)
**Difficulty**: 🟡 Intermediate

**Goal**: Add UI for admins to control live matches

#### Step 3.1: Create LiveMatchControl Component
```bash
cd frontend/src/components
touch LiveMatchControl.vue
```

**Features**:
- Button to set match as "live"
- Start/stop clock controls
- Score update controls (increment/decrement)
- End match button

#### Step 3.2: Integrate with AdminPanel
Update `AdminPanel.vue` to include live match controls for each match.

#### Step 3.3: Add API Service
```bash
cd frontend/src/services
touch liveMatchService.js
```

```javascript
import apiClient from './api';

export default {
  async startLiveMatch(matchId) {
    return apiClient.post('/live-matches/start', { match_id: matchId });
  },

  async updateScore(liveMatchId, homeScore, awayScore) {
    return apiClient.post(`/live-matches/${liveMatchId}/update-score`, {
      home_score: homeScore,
      away_score: awayScore
    });
  },

  async toggleClock(liveMatchId, running) {
    return apiClient.post(`/live-matches/${liveMatchId}/toggle-clock`, {
      running
    });
  },

  async endMatch(liveMatchId) {
    return apiClient.post(`/live-matches/${liveMatchId}/end`);
  }
};
```

**Deliverables**:
- ✅ `LiveMatchControl.vue` component
- ✅ `liveMatchService.js` API client
- ✅ Integration with AdminPanel
- ✅ Manual testing of all controls

**Testing**:
```bash
cd frontend
npm run serve
# Manually test each button/control
```

---

### Phase 4: Real-time - Postgres Changes (Week 2)
**Difficulty**: 🔴 Advanced

**Goal**: Implement real-time score updates using Supabase Postgres Changes

#### Step 4.1: Enable Realtime on Tables
```sql
-- In Supabase dashboard or migration
ALTER PUBLICATION supabase_realtime ADD TABLE live_matches;
ALTER PUBLICATION supabase_realtime ADD TABLE match_chat_messages;
```

#### Step 4.2: Create Realtime Composable
```bash
cd frontend/src/composables
touch useLiveMatch.js
```

```javascript
import { ref, onMounted, onUnmounted } from 'vue';
import { supabase } from '@/services/supabase';

export function useLiveMatch(matchId) {
  const liveMatch = ref(null);
  const chatMessages = ref([]);
  let channel = null;

  const subscribeToLiveMatch = () => {
    channel = supabase.channel(`live_match_${matchId}`)
      .on('postgres_changes', {
        event: '*',
        schema: 'public',
        table: 'live_matches',
        filter: `match_id=eq.${matchId}`
      }, (payload) => {
        console.log('Live match updated:', payload);
        liveMatch.value = payload.new;
      })
      .on('postgres_changes', {
        event: 'INSERT',
        schema: 'public',
        table: 'match_chat_messages',
        filter: `match_id=eq.${matchId}`
      }, (payload) => {
        console.log('New chat message:', payload);
        chatMessages.value.push(payload.new);
      })
      .subscribe();
  };

  onMounted(() => {
    subscribeToLiveMatch();
  });

  onUnmounted(() => {
    if (channel) {
      supabase.removeChannel(channel);
    }
  });

  return {
    liveMatch,
    chatMessages
  };
}
```

#### Step 4.3: Create LiveMatchViewer Component
```bash
cd frontend/src/components
touch LiveMatchViewer.vue
```

**Features**:
- Display live scores (auto-updating)
- Display match status
- Display clock (will add broadcast in next phase)
- Chat interface

#### Step 4.4: Add Route
```javascript
// frontend/src/router/index.js
{
  path: '/live/:matchId',
  name: 'LiveMatch',
  component: () => import('@/components/LiveMatchViewer.vue'),
  meta: { requiresAuth: true }
}
```

**Deliverables**:
- ✅ Realtime enabled on tables
- ✅ `useLiveMatch` composable
- ✅ `LiveMatchViewer` component
- ✅ Real-time score updates working

**Testing**:
```bash
# Terminal 1: Start backend
./missing-table.sh dev

# Terminal 2: Open two browser windows
# Window 1: Admin view (update score)
# Window 2: Fan view (see updates in real-time)
```

---

### Phase 5: Real-time - Broadcast (Week 3)
**Difficulty**: 🔴 Advanced

**Goal**: Implement live match clock using Supabase Broadcast

#### Step 5.1: Backend Clock Broadcaster

Create a background task to broadcast clock ticks:

```python
# backend/services/live_match_clock.py
import asyncio
from datetime import datetime
from supabase import create_client
import os

class LiveMatchClock:
    def __init__(self):
        self.client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")
        )
        self.running_matches = {}

    async def start_clock(self, live_match_id: str, match_id: str):
        """Start broadcasting clock ticks for a match."""
        if live_match_id in self.running_matches:
            return

        self.running_matches[live_match_id] = True
        asyncio.create_task(self._broadcast_clock(live_match_id, match_id))

    async def stop_clock(self, live_match_id: str):
        """Stop broadcasting clock ticks."""
        self.running_matches[live_match_id] = False

    async def _broadcast_clock(self, live_match_id: str, match_id: str):
        """Broadcast clock ticks every second."""
        channel = f"live_match_{match_id}"
        seconds = 0

        while self.running_matches.get(live_match_id):
            # Broadcast tick
            self.client.realtime.channel(channel).send({
                'type': 'broadcast',
                'event': 'clock_tick',
                'payload': {'seconds': seconds}
            })

            # Every 60 seconds, persist to database
            if seconds % 60 == 0:
                self.client.table('live_matches').update({
                    'clock_seconds': seconds
                }).eq('id', live_match_id).execute()

            seconds += 1
            await asyncio.sleep(1)

# Global instance
clock_service = LiveMatchClock()
```

#### Step 5.2: Update API to Use Clock Service
```python
@router.post("/{live_match_id}/toggle-clock")
async def toggle_clock(
    live_match_id: str,
    running: bool,
    current_user: dict = Depends(require_role(["admin", "team_manager"]))
):
    if running:
        # Get match_id from database
        live_match = dao.get_live_match(live_match_id)
        await clock_service.start_clock(live_match_id, live_match['match_id'])
    else:
        await clock_service.stop_clock(live_match_id)

    # Update database
    dao.update_clock_running(live_match_id, running)
    return {"status": "success"}
```

#### Step 5.3: Frontend - Subscribe to Clock Ticks
Update `useLiveMatch.js`:

```javascript
export function useLiveMatch(matchId) {
  const liveMatch = ref(null);
  const chatMessages = ref([]);
  const clockSeconds = ref(0);
  let channel = null;

  const subscribeToLiveMatch = () => {
    channel = supabase.channel(`live_match_${matchId}`)
      .on('postgres_changes', {
        // ... (existing postgres changes)
      })
      .on('broadcast', { event: 'clock_tick' }, (payload) => {
        clockSeconds.value = payload.payload.seconds;
      })
      .subscribe();
  };

  // ... rest of code

  return {
    liveMatch,
    chatMessages,
    clockSeconds
  };
}
```

#### Step 5.4: Display Clock in UI
```vue
<!-- LiveMatchViewer.vue -->
<template>
  <div class="live-match-clock">
    <h2>{{ formatTime(clockSeconds) }}</h2>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useLiveMatch } from '@/composables/useLiveMatch';

const props = defineProps(['matchId']);
const { clockSeconds } = useLiveMatch(props.matchId);

const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};
</script>
```

**Deliverables**:
- ✅ Backend clock broadcaster service
- ✅ API integration with clock service
- ✅ Frontend clock display
- ✅ Clock synced across all viewers

**Testing**:
```bash
# Test clock synchronization
# 1. Admin starts clock
# 2. Open fan view in multiple browsers
# 3. Verify all clocks are in sync (within 1 second)
# 4. Admin stops clock
# 5. Verify all clocks stop
```

---

### Phase 6: Real-time - Presence (Week 3)
**Difficulty**: 🟡 Intermediate

**Goal**: Track and display viewer count using Supabase Presence

#### Step 6.1: Update Frontend Composable
```javascript
// useLiveMatch.js
import { ref, computed } from 'vue';

export function useLiveMatch(matchId) {
  // ... existing code
  const viewers = ref([]);

  const viewerCount = computed(() => {
    return Object.keys(viewers.value).length;
  });

  const subscribeToLiveMatch = () => {
    channel = supabase.channel(`live_match_${matchId}`)
      // ... existing subscriptions
      .on('presence', { event: 'sync' }, () => {
        viewers.value = channel.presenceState();
      })
      .on('presence', { event: 'join' }, ({ key, newPresences }) => {
        console.log('User joined:', key);
      })
      .on('presence', { event: 'leave' }, ({ key, leftPresences }) => {
        console.log('User left:', key);
      })
      .subscribe(async (status) => {
        if (status === 'SUBSCRIBED') {
          // Track this user's presence
          await channel.track({
            user_id: currentUser.value?.id,
            username: currentUser.value?.username,
            online_at: new Date().toISOString()
          });
        }
      });
  };

  return {
    liveMatch,
    chatMessages,
    clockSeconds,
    viewerCount
  };
}
```

#### Step 6.2: Display Viewer Count
```vue
<!-- LiveMatchViewer.vue -->
<template>
  <div class="live-match-header">
    <span class="viewer-count">
      👁️ {{ viewerCount }} watching
    </span>
  </div>
</template>

<script setup>
const { viewerCount } = useLiveMatch(props.matchId);
</script>
```

**Deliverables**:
- ✅ Presence tracking implemented
- ✅ Viewer count displayed
- ✅ Join/leave events logged

**Testing**:
```bash
# Open multiple browser tabs/windows
# Verify viewer count increments/decrements correctly
```

---

### Phase 7: Chat Implementation (Week 3)
**Difficulty**: 🟡 Intermediate

**Goal**: Implement real-time chat for live matches

#### Step 7.1: Backend Chat API
```python
@router.post("/{match_id}/chat")
async def send_chat_message(
    match_id: str,
    message: str,
    current_user: dict = Depends(get_current_user)
):
    # Insert into database (will trigger postgres_changes)
    result = dao.add_chat_message(
        match_id=match_id,
        user_id=current_user['id'],
        username=current_user['username'],
        message=message
    )
    return result
```

#### Step 7.2: Chat Component
```bash
cd frontend/src/components
touch LiveMatchChat.vue
```

```vue
<template>
  <div class="live-chat">
    <div class="chat-messages">
      <div
        v-for="msg in chatMessages"
        :key="msg.id"
        class="chat-message"
      >
        <span class="username">{{ msg.username }}:</span>
        <span class="message">{{ msg.message }}</span>
        <span class="timestamp">{{ formatTime(msg.created_at) }}</span>
      </div>
    </div>

    <form @submit.prevent="sendMessage">
      <input
        v-model="newMessage"
        placeholder="Type a message..."
        maxlength="200"
      />
      <button type="submit">Send</button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import liveMatchService from '@/services/liveMatchService';

const props = defineProps(['matchId', 'chatMessages']);
const newMessage = ref('');

const sendMessage = async () => {
  if (!newMessage.value.trim()) return;

  await liveMatchService.sendChatMessage(props.matchId, newMessage.value);
  newMessage.value = '';
};
</script>
```

#### Step 7.3: Add Chat to LiveMatchViewer
```vue
<!-- LiveMatchViewer.vue -->
<template>
  <div class="live-match-container">
    <!-- Score and clock -->
    <div class="match-info">
      <!-- ... -->
    </div>

    <!-- Chat -->
    <LiveMatchChat
      :match-id="matchId"
      :chat-messages="chatMessages"
    />
  </div>
</template>
```

**Deliverables**:
- ✅ Chat API endpoint
- ✅ Chat component
- ✅ Real-time message delivery
- ✅ Message history on load

**Testing**:
```bash
# Open two browser windows
# Send messages from each
# Verify messages appear instantly in both
```

---

### Phase 8: Integration & Polish (Week 4)
**Difficulty**: 🟡 Intermediate

**Goal**: Integrate live matches into main app and polish UX

#### Step 8.1: Add "Live Now" Indicator
Update `MatchesView.vue` to show which matches are live:

```vue
<template>
  <div class="match-card">
    <span v-if="match.isLive" class="live-badge">
      🔴 LIVE
    </span>
    <!-- ... rest of match card -->
  </div>
</template>
```

#### Step 8.2: Create Live Matches Landing Page
```bash
cd frontend/src/components
touch LiveMatchesList.vue
```

Show all currently live matches with viewer counts.

#### Step 8.3: Add Navigation Link
```vue
<!-- Navigation component -->
<router-link to="/live">
  Live Matches
  <span v-if="liveMatchCount > 0" class="badge">
    {{ liveMatchCount }}
  </span>
</router-link>
```

#### Step 8.4: Notifications
Add browser notification when a match goes live (optional):

```javascript
// services/notificationService.js
export async function notifyMatchLive(matchName) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('Match is Live!', {
      body: `${matchName} is now live`,
      icon: '/logo.png'
    });
  }
}
```

**Deliverables**:
- ✅ Live badge on match cards
- ✅ Live matches list page
- ✅ Navigation integration
- ✅ (Optional) Browser notifications

---

### Phase 9: Testing (Week 4)
**Difficulty**: 🟡 Intermediate

**Goal**: Comprehensive testing of all live match features

See [Testing Strategy](#-testing-strategy) section below for details.

**Deliverables**:
- ✅ Unit tests for backend API
- ✅ Integration tests for real-time
- ✅ E2E tests for user flows
- ✅ Load testing for concurrent viewers
- ✅ Manual QA checklist completed

---

### Phase 10: Deployment (Week 4)
**Difficulty**: 🔴 Advanced

**Goal**: Deploy to production

See [Deployment Plan](#-deployment-plan) section below.

**Deliverables**:
- ✅ Feature deployed to dev environment
- ✅ Smoke tests passed
- ✅ Feature deployed to production
- ✅ Monitoring in place

---

## 🗄️ Database Schema

### Migration File: `020_add_live_match_tables.sql`

```sql
-- ============================================================================
-- Migration: 020_add_live_match_tables.sql
-- Description: Add tables for live match functionality with real-time support
-- Author: [Your Name]
-- Date: [Date]
-- ============================================================================

-- Live Matches Table
-- Stores the current state of live matches
CREATE TABLE live_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,

    -- Match Status
    status TEXT NOT NULL CHECK (status IN ('pre_match', 'first_half', 'halftime', 'second_half', 'ended')),

    -- Live Scores (denormalized for performance)
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    home_team_name TEXT NOT NULL,
    away_team_name TEXT NOT NULL,
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,

    -- Clock
    clock_seconds INTEGER DEFAULT 0,
    clock_running BOOLEAN DEFAULT FALSE,

    -- Metadata
    started_by UUID REFERENCES auth.users(id),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_live_match UNIQUE(match_id),
    CONSTRAINT different_teams CHECK (home_team_id != away_team_id)
);

-- Match Chat Messages Table
-- Stores chat messages for live matches
CREATE TABLE match_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,

    -- User Info
    user_id UUID NOT NULL REFERENCES auth.users(id),
    username TEXT NOT NULL,

    -- Message
    message TEXT NOT NULL CHECK (length(message) <= 500),

    -- Moderation
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_by UUID REFERENCES auth.users(id),
    deleted_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for Performance
CREATE INDEX idx_live_matches_match_id ON live_matches(match_id);
CREATE INDEX idx_live_matches_status ON live_matches(status);
CREATE INDEX idx_live_matches_started_at ON live_matches(started_at);

CREATE INDEX idx_chat_messages_match_id ON match_chat_messages(match_id);
CREATE INDEX idx_chat_messages_created_at ON match_chat_messages(created_at);
CREATE INDEX idx_chat_messages_user_id ON match_chat_messages(user_id);

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS
ALTER TABLE live_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_chat_messages ENABLE ROW LEVEL SECURITY;

-- Live Matches Policies

-- Anyone can view live matches
CREATE POLICY "Anyone can view live matches"
    ON live_matches FOR SELECT
    USING (true);

-- Only admins and team managers can create live matches
CREATE POLICY "Admins and team managers can create live matches"
    ON live_matches FOR INSERT
    WITH CHECK (
        auth.uid() IN (
            SELECT user_id FROM user_profiles
            WHERE role IN ('admin', 'team_manager')
        )
    );

-- Only admins and team managers can update live matches
CREATE POLICY "Admins and team managers can update live matches"
    ON live_matches FOR UPDATE
    USING (
        auth.uid() IN (
            SELECT user_id FROM user_profiles
            WHERE role IN ('admin', 'team_manager')
        )
    );

-- Only admins can delete live matches
CREATE POLICY "Admins can delete live matches"
    ON live_matches FOR DELETE
    USING (
        auth.uid() IN (
            SELECT user_id FROM user_profiles
            WHERE role = 'admin'
        )
    );

-- Chat Message Policies

-- Anyone can view chat messages
CREATE POLICY "Anyone can view chat messages"
    ON match_chat_messages FOR SELECT
    USING (true);

-- Authenticated users can send chat messages
CREATE POLICY "Authenticated users can send chat messages"
    ON match_chat_messages FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own messages (for editing)
CREATE POLICY "Users can update their own messages"
    ON match_chat_messages FOR UPDATE
    USING (auth.uid() = user_id);

-- Admins can delete any message (moderation)
CREATE POLICY "Admins can delete any message"
    ON match_chat_messages FOR DELETE
    USING (
        auth.uid() IN (
            SELECT user_id FROM user_profiles
            WHERE role = 'admin'
        )
    );

-- ============================================================================
-- Enable Realtime
-- ============================================================================

-- Enable realtime for live matches and chat
ALTER PUBLICATION supabase_realtime ADD TABLE live_matches;
ALTER PUBLICATION supabase_realtime ADD TABLE match_chat_messages;

-- ============================================================================
-- Functions and Triggers
-- ============================================================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER live_matches_updated_at
    BEFORE UPDATE ON live_matches
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- Sample Data (for development only)
-- ============================================================================

-- Uncomment for local development testing
/*
INSERT INTO live_matches (
    match_id,
    status,
    home_team_id,
    away_team_id,
    home_team_name,
    away_team_name,
    home_score,
    away_score,
    clock_seconds,
    clock_running
)
SELECT
    m.id,
    'first_half',
    m.home_team_id,
    m.away_team_id,
    ht.name,
    at.name,
    2,
    1,
    1230,
    true
FROM matches m
JOIN teams ht ON m.home_team_id = ht.id
JOIN teams at ON m.away_team_id = at.id
LIMIT 1;
*/
```

---

## 🔌 Backend API

### DAO Layer: `backend/dao/live_match_dao.py`

```python
"""
Data Access Object for live match operations.
"""
from typing import Optional
from datetime import datetime
from supabase import Client


class LiveMatchDAO:
    """DAO for live match operations."""

    def __init__(self, client: Client):
        """Initialize with Supabase client."""
        self.client = client

    def create_live_match(
        self,
        match_id: str,
        home_team_id: int,
        away_team_id: int,
        home_team_name: str,
        away_team_name: str,
        started_by: str
    ) -> dict:
        """Create a new live match."""
        data = {
            "match_id": match_id,
            "status": "pre_match",
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "home_team_name": home_team_name,
            "away_team_name": away_team_name,
            "home_score": 0,
            "away_score": 0,
            "clock_seconds": 0,
            "clock_running": False,
            "started_by": started_by,
        }

        response = self.client.table("live_matches").insert(data).execute()
        return response.data[0] if response.data else None

    def get_live_match_by_id(self, live_match_id: str) -> Optional[dict]:
        """Get a live match by ID."""
        response = (
            self.client.table("live_matches")
            .select("*")
            .eq("id", live_match_id)
            .single()
            .execute()
        )
        return response.data if response.data else None

    def get_live_match_by_match_id(self, match_id: str) -> Optional[dict]:
        """Get a live match by match ID."""
        response = (
            self.client.table("live_matches")
            .select("*")
            .eq("match_id", match_id)
            .single()
            .execute()
        )
        return response.data if response.data else None

    def get_active_live_matches(self) -> list[dict]:
        """Get all active live matches (not ended)."""
        response = (
            self.client.table("live_matches")
            .select("*")
            .neq("status", "ended")
            .order("started_at", desc=True)
            .execute()
        )
        return response.data

    def update_score(
        self,
        live_match_id: str,
        home_score: int,
        away_score: int
    ) -> dict:
        """Update the score for a live match."""
        data = {
            "home_score": home_score,
            "away_score": away_score,
        }

        response = (
            self.client.table("live_matches")
            .update(data)
            .eq("id", live_match_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def update_status(self, live_match_id: str, status: str) -> dict:
        """Update the status of a live match."""
        data = {"status": status}

        if status == "ended":
            data["ended_at"] = datetime.utcnow().isoformat()
            data["clock_running"] = False

        response = (
            self.client.table("live_matches")
            .update(data)
            .eq("id", live_match_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def update_clock(
        self,
        live_match_id: str,
        clock_seconds: int,
        clock_running: bool
    ) -> dict:
        """Update the clock for a live match."""
        data = {
            "clock_seconds": clock_seconds,
            "clock_running": clock_running,
        }

        response = (
            self.client.table("live_matches")
            .update(data)
            .eq("id", live_match_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def end_live_match(self, live_match_id: str) -> dict:
        """End a live match and update the main matches table."""
        # Get the live match
        live_match = self.get_live_match_by_id(live_match_id)
        if not live_match:
            return None

        # Update the main matches table with final scores
        self.client.table("matches").update({
            "home_score": live_match["home_score"],
            "away_score": live_match["away_score"],
            "match_status": "completed",
        }).eq("id", live_match["match_id"]).execute()

        # Mark live match as ended
        return self.update_status(live_match_id, "ended")

    # Chat Methods

    def add_chat_message(
        self,
        match_id: str,
        user_id: str,
        username: str,
        message: str
    ) -> dict:
        """Add a chat message."""
        data = {
            "match_id": match_id,
            "user_id": user_id,
            "username": username,
            "message": message,
        }

        response = self.client.table("match_chat_messages").insert(data).execute()
        return response.data[0] if response.data else None

    def get_chat_messages(self, match_id: str, limit: int = 100) -> list[dict]:
        """Get chat messages for a match."""
        response = (
            self.client.table("match_chat_messages")
            .select("*")
            .eq("match_id", match_id)
            .eq("is_deleted", False)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(reversed(response.data))  # Newest first -> oldest first

    def delete_chat_message(self, message_id: str, deleted_by: str) -> dict:
        """Soft delete a chat message (admin moderation)."""
        data = {
            "is_deleted": True,
            "deleted_by": deleted_by,
            "deleted_at": datetime.utcnow().isoformat(),
        }

        response = (
            self.client.table("match_chat_messages")
            .update(data)
            .eq("id", message_id)
            .execute()
        )
        return response.data[0] if response.data else None
```

### API Router: `backend/routers/live_matches.py`

```python
"""
API endpoints for live match functionality.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from auth import get_current_user, require_role
from dao.supabase_data_access import SupabaseConnection
from dao.live_match_dao import LiveMatchDAO


router = APIRouter(prefix="/api/live-matches", tags=["live-matches"])


# ============================================================================
# Pydantic Models
# ============================================================================

class StartLiveMatchRequest(BaseModel):
    match_id: str


class UpdateScoreRequest(BaseModel):
    home_score: int
    away_score: int


class UpdateStatusRequest(BaseModel):
    status: str  # pre_match, first_half, halftime, second_half, ended


class ToggleClockRequest(BaseModel):
    running: bool


class SendChatMessageRequest(BaseModel):
    message: str


# ============================================================================
# Dependency Injection
# ============================================================================

def get_dao() -> LiveMatchDAO:
    """Get LiveMatchDAO instance."""
    conn = SupabaseConnection()
    return LiveMatchDAO(conn.get_client())


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_live_match(
    request: StartLiveMatchRequest,
    current_user: dict = Depends(require_role(["admin", "team_manager"])),
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    Start a live match.

    **Permissions**: admin, team_manager
    """
    # Check if match already has a live instance
    existing = dao.get_live_match_by_match_id(request.match_id)
    if existing and existing["status"] != "ended":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Match is already live"
        )

    # Get match details from main matches table
    conn = SupabaseConnection()
    match = (
        conn.get_client()
        .table("matches")
        .select("id, home_team_id, away_team_id, teams!matches_home_team_id_fkey(name), teams!matches_away_team_id_fkey(name)")
        .eq("id", request.match_id)
        .single()
        .execute()
    )

    if not match.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found"
        )

    # Create live match
    live_match = dao.create_live_match(
        match_id=request.match_id,
        home_team_id=match.data["home_team_id"],
        away_team_id=match.data["away_team_id"],
        home_team_name=match.data["teams"]["name"],  # Adjust based on Supabase join syntax
        away_team_name=match.data["teams"]["name"],
        started_by=current_user["id"]
    )

    return live_match


@router.get("/active")
async def get_active_live_matches(
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    Get all active live matches.

    **Permissions**: Public
    """
    matches = dao.get_active_live_matches()
    return {"matches": matches}


@router.get("/{live_match_id}")
async def get_live_match(
    live_match_id: str,
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    Get a specific live match by ID.

    **Permissions**: Public
    """
    match = dao.get_live_match_by_id(live_match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live match not found"
        )
    return match


@router.post("/{live_match_id}/update-score")
async def update_score(
    live_match_id: str,
    request: UpdateScoreRequest,
    current_user: dict = Depends(require_role(["admin", "team_manager"])),
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    Update the score for a live match.

    **Permissions**: admin, team_manager
    """
    updated = dao.update_score(
        live_match_id,
        request.home_score,
        request.away_score
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live match not found"
        )

    return updated


@router.post("/{live_match_id}/update-status")
async def update_status(
    live_match_id: str,
    request: UpdateStatusRequest,
    current_user: dict = Depends(require_role(["admin", "team_manager"])),
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    Update the status of a live match.

    **Permissions**: admin, team_manager
    """
    updated = dao.update_status(live_match_id, request.status)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live match not found"
        )

    return updated


@router.post("/{live_match_id}/toggle-clock")
async def toggle_clock(
    live_match_id: str,
    request: ToggleClockRequest,
    current_user: dict = Depends(require_role(["admin", "team_manager"])),
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    Start or stop the match clock.

    **Permissions**: admin, team_manager
    """
    # Get current live match
    live_match = dao.get_live_match_by_id(live_match_id)
    if not live_match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live match not found"
        )

    # Update clock running status
    updated = dao.update_clock(
        live_match_id,
        live_match["clock_seconds"],
        request.running
    )

    # TODO: Integrate with LiveMatchClock service (Phase 5)

    return updated


@router.post("/{live_match_id}/end")
async def end_live_match(
    live_match_id: str,
    current_user: dict = Depends(require_role(["admin", "team_manager"])),
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    End a live match and save final scores to main matches table.

    **Permissions**: admin, team_manager
    """
    result = dao.end_live_match(live_match_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live match not found"
        )

    return {"status": "success", "message": "Match ended successfully"}


# ============================================================================
# Chat Endpoints
# ============================================================================

@router.get("/{match_id}/chat")
async def get_chat_messages(
    match_id: str,
    limit: int = 100,
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    Get chat messages for a match.

    **Permissions**: Public
    """
    messages = dao.get_chat_messages(match_id, limit)
    return {"messages": messages}


@router.post("/{match_id}/chat")
async def send_chat_message(
    match_id: str,
    request: SendChatMessageRequest,
    current_user: dict = Depends(get_current_user),
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    Send a chat message.

    **Permissions**: authenticated users
    """
    message = dao.add_chat_message(
        match_id=match_id,
        user_id=current_user["id"],
        username=current_user["username"],
        message=request.message
    )

    return message


@router.delete("/chat/{message_id}")
async def delete_chat_message(
    message_id: str,
    current_user: dict = Depends(require_role(["admin"])),
    dao: LiveMatchDAO = Depends(get_dao)
):
    """
    Delete a chat message (admin moderation).

    **Permissions**: admin
    """
    deleted = dao.delete_chat_message(message_id, current_user["id"])

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    return {"status": "success", "message": "Message deleted"}
```

### Register Router in `backend/app.py`

```python
# app.py
from routers import live_matches

app.include_router(live_matches.router)
```

---

## 🎨 Frontend Components

### Composable: `frontend/src/composables/useLiveMatch.js`

```javascript
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { supabase } from '@/services/supabase';
import { useAuthStore } from '@/stores/auth';

/**
 * Composable for live match real-time functionality
 *
 * @param {string} matchId - The match ID to subscribe to
 * @returns {object} - Live match state and methods
 */
export function useLiveMatch(matchId) {
  const authStore = useAuthStore();

  const liveMatch = ref(null);
  const chatMessages = ref([]);
  const clockSeconds = ref(0);
  const viewers = ref({});
  const loading = ref(true);
  const error = ref(null);

  let channel = null;

  const viewerCount = computed(() => {
    return Object.keys(viewers.value).length;
  });

  const formatTime = computed(() => {
    if (!clockSeconds.value) return '0:00';
    const mins = Math.floor(clockSeconds.value / 60);
    const secs = clockSeconds.value % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  });

  /**
   * Load initial live match data
   */
  const loadLiveMatch = async () => {
    try {
      loading.value = true;

      const { data, error: fetchError } = await supabase
        .from('live_matches')
        .select('*')
        .eq('match_id', matchId)
        .single();

      if (fetchError) throw fetchError;

      liveMatch.value = data;
      clockSeconds.value = data?.clock_seconds || 0;

    } catch (err) {
      console.error('Error loading live match:', err);
      error.value = err.message;
    } finally {
      loading.value = false;
    }
  };

  /**
   * Load chat history
   */
  const loadChatHistory = async () => {
    try {
      const { data, error: fetchError } = await supabase
        .from('match_chat_messages')
        .select('*')
        .eq('match_id', matchId)
        .eq('is_deleted', false)
        .order('created_at', { ascending: true })
        .limit(100);

      if (fetchError) throw fetchError;

      chatMessages.value = data || [];

    } catch (err) {
      console.error('Error loading chat history:', err);
    }
  };

  /**
   * Subscribe to real-time updates
   */
  const subscribeToLiveMatch = () => {
    channel = supabase.channel(`live_match_${matchId}`)
      // Postgres Changes - Live Match Updates
      .on('postgres_changes', {
        event: '*',
        schema: 'public',
        table: 'live_matches',
        filter: `match_id=eq.${matchId}`
      }, (payload) => {
        console.log('Live match updated:', payload);
        liveMatch.value = payload.new;

        // Update clock from database (fallback)
        if (payload.new?.clock_seconds !== undefined) {
          clockSeconds.value = payload.new.clock_seconds;
        }
      })
      // Postgres Changes - Chat Messages
      .on('postgres_changes', {
        event: 'INSERT',
        schema: 'public',
        table: 'match_chat_messages',
        filter: `match_id=eq.${matchId}`
      }, (payload) => {
        console.log('New chat message:', payload);
        chatMessages.value.push(payload.new);

        // Auto-scroll to bottom (implement in component)
      })
      // Broadcast - Clock Ticks
      .on('broadcast', { event: 'clock_tick' }, (payload) => {
        clockSeconds.value = payload.payload.seconds;
      })
      // Presence - Viewer Tracking
      .on('presence', { event: 'sync' }, () => {
        viewers.value = channel.presenceState();
      })
      .on('presence', { event: 'join' }, ({ key, newPresences }) => {
        console.log('User joined:', key, newPresences);
      })
      .on('presence', { event: 'leave' }, ({ key, leftPresences }) => {
        console.log('User left:', key, leftPresences);
      })
      .subscribe(async (status) => {
        if (status === 'SUBSCRIBED') {
          console.log('Subscribed to live match channel');

          // Track this user's presence
          if (authStore.user) {
            await channel.track({
              user_id: authStore.user.id,
              username: authStore.user.username,
              online_at: new Date().toISOString()
            });
          }
        }
      });
  };

  /**
   * Unsubscribe from real-time updates
   */
  const unsubscribe = () => {
    if (channel) {
      supabase.removeChannel(channel);
      channel = null;
    }
  };

  // Lifecycle hooks
  onMounted(async () => {
    await loadLiveMatch();
    await loadChatHistory();
    subscribeToLiveMatch();
  });

  onUnmounted(() => {
    unsubscribe();
  });

  return {
    // State
    liveMatch,
    chatMessages,
    clockSeconds,
    viewerCount,
    loading,
    error,

    // Computed
    formatTime,

    // Methods
    loadLiveMatch,
    loadChatHistory
  };
}
```

### Component: `frontend/src/components/LiveMatchViewer.vue`

```vue
<template>
  <div class="live-match-viewer">
    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <p>Loading live match...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      <p>Error: {{ error }}</p>
    </div>

    <!-- Live Match Content -->
    <div v-else-if="liveMatch" class="live-match-content">
      <!-- Header -->
      <div class="live-match-header">
        <span class="live-badge">🔴 LIVE</span>
        <span class="viewer-count">👁️ {{ viewerCount }} watching</span>
        <span class="match-status">{{ liveMatch.status }}</span>
      </div>

      <!-- Scoreboard -->
      <div class="scoreboard">
        <div class="team home-team">
          <h2>{{ liveMatch.home_team_name }}</h2>
          <div class="score">{{ liveMatch.home_score }}</div>
        </div>

        <div class="match-clock">
          <div class="clock-time">{{ formatTime }}</div>
          <div v-if="liveMatch.clock_running" class="clock-running">
            ⏱️ Running
          </div>
          <div v-else class="clock-paused">
            ⏸️ Paused
          </div>
        </div>

        <div class="team away-team">
          <h2>{{ liveMatch.away_team_name }}</h2>
          <div class="score">{{ liveMatch.away_score }}</div>
        </div>
      </div>

      <!-- Chat Section -->
      <LiveMatchChat
        :match-id="matchId"
        :chat-messages="chatMessages"
      />
    </div>

    <!-- No Live Match -->
    <div v-else class="no-live-match">
      <p>This match is not currently live.</p>
      <router-link to="/">Return to Home</router-link>
    </div>
  </div>
</template>

<script setup>
import { useLiveMatch } from '@/composables/useLiveMatch';
import LiveMatchChat from './LiveMatchChat.vue';

const props = defineProps({
  matchId: {
    type: String,
    required: true
  }
});

const {
  liveMatch,
  chatMessages,
  viewerCount,
  formatTime,
  loading,
  error
} = useLiveMatch(props.matchId);
</script>

<style scoped>
.live-match-viewer {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.live-match-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #1a1a1a;
  border-radius: 8px;
  margin-bottom: 20px;
}

.live-badge {
  background: #dc2626;
  color: white;
  padding: 5px 15px;
  border-radius: 20px;
  font-weight: bold;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.viewer-count {
  color: #9ca3af;
  font-size: 14px;
}

.match-status {
  color: #60a5fa;
  text-transform: uppercase;
  font-size: 12px;
  font-weight: bold;
}

.scoreboard {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 40px;
  align-items: center;
  padding: 40px;
  background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
  border-radius: 12px;
  margin-bottom: 30px;
  color: white;
}

.team {
  text-align: center;
}

.team h2 {
  font-size: 24px;
  margin-bottom: 15px;
  font-weight: 600;
}

.score {
  font-size: 72px;
  font-weight: bold;
  line-height: 1;
}

.match-clock {
  text-align: center;
  border-left: 2px solid rgba(255, 255, 255, 0.2);
  border-right: 2px solid rgba(255, 255, 255, 0.2);
  padding: 0 40px;
}

.clock-time {
  font-size: 48px;
  font-weight: bold;
  margin-bottom: 10px;
  font-variant-numeric: tabular-nums;
}

.clock-running,
.clock-paused {
  font-size: 14px;
  opacity: 0.8;
}

.loading-state,
.error-state,
.no-live-match {
  text-align: center;
  padding: 60px 20px;
}

/* Responsive */
@media (max-width: 768px) {
  .scoreboard {
    grid-template-columns: 1fr;
    gap: 20px;
  }

  .match-clock {
    border: none;
    border-top: 2px solid rgba(255, 255, 255, 0.2);
    border-bottom: 2px solid rgba(255, 255, 255, 0.2);
    padding: 20px 0;
  }

  .score {
    font-size: 48px;
  }

  .clock-time {
    font-size: 36px;
  }
}
</style>
```

### Component: `frontend/src/components/LiveMatchChat.vue`

```vue
<template>
  <div class="live-match-chat">
    <div class="chat-header">
      <h3>Live Chat</h3>
      <span class="message-count">{{ chatMessages.length }} messages</span>
    </div>

    <div ref="messageContainer" class="chat-messages">
      <div
        v-for="msg in chatMessages"
        :key="msg.id"
        class="chat-message"
        :class="{ 'own-message': isOwnMessage(msg) }"
      >
        <div class="message-header">
          <span class="username">{{ msg.username }}</span>
          <span class="timestamp">{{ formatTimestamp(msg.created_at) }}</span>
        </div>
        <div class="message-text">{{ msg.message }}</div>
      </div>

      <div v-if="chatMessages.length === 0" class="empty-state">
        No messages yet. Start the conversation!
      </div>
    </div>

    <form class="chat-input" @submit.prevent="sendMessage">
      <input
        v-model="newMessage"
        type="text"
        placeholder="Type a message..."
        maxlength="500"
        :disabled="!isAuthenticated"
      />
      <button
        type="submit"
        :disabled="!canSend"
      >
        Send
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue';
import { useAuthStore } from '@/stores/auth';
import liveMatchService from '@/services/liveMatchService';

const props = defineProps({
  matchId: {
    type: String,
    required: true
  },
  chatMessages: {
    type: Array,
    default: () => []
  }
});

const authStore = useAuthStore();
const newMessage = ref('');
const messageContainer = ref(null);

const isAuthenticated = computed(() => !!authStore.user);

const canSend = computed(() => {
  return isAuthenticated.value && newMessage.value.trim().length > 0;
});

const isOwnMessage = (msg) => {
  return authStore.user?.id === msg.user_id;
};

const formatTimestamp = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit'
  });
};

const sendMessage = async () => {
  if (!canSend.value) return;

  try {
    await liveMatchService.sendChatMessage(props.matchId, newMessage.value);
    newMessage.value = '';
  } catch (err) {
    console.error('Error sending message:', err);
    alert('Failed to send message. Please try again.');
  }
};

const scrollToBottom = () => {
  nextTick(() => {
    if (messageContainer.value) {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight;
    }
  });
};

// Auto-scroll when new messages arrive
watch(() => props.chatMessages.length, () => {
  scrollToBottom();
});
</script>

<style scoped>
.live-match-chat {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background: #f3f4f6;
  border-bottom: 1px solid #e5e7eb;
}

.chat-header h3 {
  margin: 0;
  font-size: 18px;
}

.message-count {
  color: #6b7280;
  font-size: 14px;
}

.chat-messages {
  height: 400px;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.chat-message {
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
  max-width: 80%;
}

.chat-message.own-message {
  background: #dbeafe;
  align-self: flex-end;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
  font-size: 12px;
}

.username {
  font-weight: 600;
  color: #1f2937;
}

.timestamp {
  color: #9ca3af;
}

.message-text {
  color: #374151;
  line-height: 1.5;
  word-wrap: break-word;
}

.empty-state {
  text-align: center;
  color: #9ca3af;
  padding: 40px 20px;
}

.chat-input {
  display: flex;
  gap: 10px;
  padding: 15px 20px;
  background: #f9fafb;
  border-top: 1px solid #e5e7eb;
}

.chat-input input {
  flex: 1;
  padding: 10px 15px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
}

.chat-input input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.chat-input button {
  padding: 10px 24px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.chat-input button:hover:not(:disabled) {
  background: #2563eb;
}

.chat-input button:disabled {
  background: #9ca3af;
  cursor: not-allowed;
}

/* Custom scrollbar */
.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track {
  background: #f3f4f6;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 4px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
```

---

## 🔐 Security & Permissions

### Row Level Security (RLS) Policies

Already defined in the migration above. Key points:

**Live Matches**:
- ✅ Anyone can **view** live matches
- ✅ Only admin/team_manager can **create**, **update**, or **end** live matches
- ✅ Only admins can **delete** live matches

**Chat Messages**:
- ✅ Anyone can **view** messages
- ✅ Authenticated users can **send** messages
- ✅ Users can **edit** their own messages
- ✅ Admins can **delete** any message (moderation)

### Rate Limiting (Future Enhancement)

Consider adding rate limiting for chat messages:

```python
# backend/middleware/rate_limit.py
from fastapi import HTTPException, Request
from datetime import datetime, timedelta
from collections import defaultdict

class RateLimiter:
    def __init__(self, requests_per_minute=10):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)

    def check_rate_limit(self, user_id: str):
        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # Clean old requests
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if req_time > cutoff
        ]

        # Check limit
        if len(self.requests[user_id]) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down."
            )

        self.requests[user_id].append(now)

# Usage in chat endpoint
rate_limiter = RateLimiter(requests_per_minute=10)

@router.post("/{match_id}/chat")
async def send_chat_message(...):
    rate_limiter.check_rate_limit(current_user["id"])
    # ... rest of endpoint
```

---

## 🧪 Testing Strategy

### Unit Tests

#### Backend Tests: `backend/tests/test_live_match_dao.py`

```python
import pytest
from dao.live_match_dao import LiveMatchDAO
from dao.supabase_data_access import SupabaseConnection


@pytest.fixture
def dao():
    """Create DAO instance."""
    conn = SupabaseConnection()
    return LiveMatchDAO(conn.get_client())


def test_create_live_match(dao):
    """Test creating a live match."""
    live_match = dao.create_live_match(
        match_id="test-match-id",
        home_team_id=1,
        away_team_id=2,
        home_team_name="Team A",
        away_team_name="Team B",
        started_by="admin-user-id"
    )

    assert live_match is not None
    assert live_match["match_id"] == "test-match-id"
    assert live_match["status"] == "pre_match"
    assert live_match["home_score"] == 0
    assert live_match["away_score"] == 0


def test_update_score(dao):
    """Test updating score."""
    # Create match first
    live_match = dao.create_live_match(...)

    # Update score
    updated = dao.update_score(live_match["id"], 2, 1)

    assert updated["home_score"] == 2
    assert updated["away_score"] == 1


# Add more tests...
```

#### Frontend Tests: `frontend/tests/components/LiveMatchViewer.spec.js`

```javascript
import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import LiveMatchViewer from '@/components/LiveMatchViewer.vue';
import { useLiveMatch } from '@/composables/useLiveMatch';

vi.mock('@/composables/useLiveMatch');

describe('LiveMatchViewer', () => {
  it('displays live match data', () => {
    useLiveMatch.mockReturnValue({
      liveMatch: {
        home_team_name: 'Team A',
        away_team_name: 'Team B',
        home_score: 2,
        away_score: 1,
        status: 'first_half'
      },
      chatMessages: [],
      viewerCount: 42,
      formatTime: '15:30',
      loading: false,
      error: null
    });

    const wrapper = mount(LiveMatchViewer, {
      props: { matchId: 'test-id' }
    });

    expect(wrapper.text()).toContain('Team A');
    expect(wrapper.text()).toContain('Team B');
    expect(wrapper.text()).toContain('2');
    expect(wrapper.text()).toContain('1');
    expect(wrapper.text()).toContain('42 watching');
  });
});
```

### Integration Tests

Test real-time functionality with actual Supabase:

```javascript
// frontend/tests/integration/liveMatch.spec.js
import { describe, it, expect } from 'vitest';
import { createClient } from '@supabase/supabase-js';

describe('Live Match Integration', () => {
  it('receives real-time score updates', async () => {
    const supabase = createClient(/* ... */);
    let receivedUpdate = false;

    const channel = supabase
      .channel('test-channel')
      .on('postgres_changes', {
        event: 'UPDATE',
        schema: 'public',
        table: 'live_matches'
      }, () => {
        receivedUpdate = true;
      })
      .subscribe();

    // Trigger update
    await supabase
      .from('live_matches')
      .update({ home_score: 3 })
      .eq('id', 'test-id');

    // Wait for event
    await new Promise(resolve => setTimeout(resolve, 1000));

    expect(receivedUpdate).toBe(true);

    supabase.removeChannel(channel);
  });
});
```

### E2E Tests (Playwright)

```javascript
// tests/e2e/liveMatch.spec.js
import { test, expect } from '@playwright/test';

test.describe('Live Match Feature', () => {
  test('admin can start and control a live match', async ({ page, context }) => {
    // Login as admin
    await page.goto('/login');
    await page.fill('[name="username"]', 'admin');
    await page.fill('[name="password"]', 'password');
    await page.click('button[type="submit"]');

    // Navigate to admin panel
    await page.goto('/admin');

    // Start a live match
    await page.click('[data-test="start-live-match-1"]');

    // Verify match is live
    await expect(page.locator('.live-badge')).toBeVisible();

    // Update score
    await page.click('[data-test="increment-home-score"]');
    await expect(page.locator('.home-score')).toHaveText('1');

    // Open fan view in new tab
    const fanPage = await context.newPage();
    await fanPage.goto('/live/test-match-id');

    // Verify score is synced
    await expect(fanPage.locator('.home-score')).toHaveText('1');

    // Update score again
    await page.click('[data-test="increment-home-score"]');

    // Verify fan view updates automatically
    await expect(fanPage.locator('.home-score')).toHaveText('2');
  });
});
```

### Load Testing

Test concurrent viewers using k6:

```javascript
// tests/load/liveMatch.js
import ws from 'k6/ws';
import { check } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },   // Ramp to 50 users
    { duration: '1m', target: 100 },   // Ramp to 100 users
    { duration: '30s', target: 0 },    // Ramp down
  ],
};

export default function () {
  const url = 'wss://your-supabase-url/realtime/v1/websocket';

  const response = ws.connect(url, {}, function (socket) {
    socket.on('open', function () {
      // Subscribe to live match channel
      socket.send(JSON.stringify({
        topic: 'realtime:live_match_test-id',
        event: 'phx_join',
        payload: {},
        ref: '1'
      }));
    });

    socket.on('message', function (message) {
      check(message, {
        'message received': (msg) => msg !== null,
      });
    });

    socket.setTimeout(function () {
      socket.close();
    }, 60000); // Keep connection for 60s
  });
}
```

Run load test:
```bash
k6 run tests/load/liveMatch.js
```

---

## 🚀 Deployment Plan

### Pre-Deployment Checklist

- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Database migrations tested in dev
- [ ] Real-time features tested with multiple clients
- [ ] Performance tested (load test)
- [ ] Documentation updated
- [ ] Rollback plan prepared

### Deployment Steps

#### Step 1: Deploy to Dev Environment

```bash
# 1. Switch to dev environment
./switch-env.sh dev

# 2. Run database migration
npx supabase db push

# 3. Build and push Docker images
./build-and-push.sh all dev

# 4. Deploy to GKE dev cluster
kubectl config use-context gke_missing-table_us-central1_missing-table-dev
kubectl rollout restart deployment/missing-table-backend -n missing-table-dev
kubectl rollout restart deployment/missing-table-frontend -n missing-table-dev

# 5. Wait for rollout
kubectl rollout status deployment/missing-table-backend -n missing-table-dev
kubectl rollout status deployment/missing-table-frontend -n missing-table-dev

# 6. Verify deployment
./scripts/health-check.sh dev
```

#### Step 2: Smoke Testing in Dev

```bash
# Test basic functionality
# 1. Login as admin
# 2. Start a live match
# 3. Open fan view
# 4. Update score (verify real-time)
# 5. Send chat message (verify real-time)
# 6. End match
```

#### Step 3: Deploy to Production

```bash
# 1. Create PR from feature branch to main
gh pr create --title "Add Live Match Feature" --body "..."

# 2. Get approval and merge
# (This triggers automated production deployment via GitHub Actions)

# 3. Monitor deployment
gh run list --workflow=deploy-prod.yml

# 4. Verify health
./scripts/health-check.sh prod

# 5. Test production
# - Login as admin
# - Start test match
# - Verify functionality
# - End test match
```

### Rollback Plan

If issues arise in production:

```bash
# Option 1: Rollback deployment
kubectl rollout undo deployment/missing-table-backend -n missing-table-prod
kubectl rollout undo deployment/missing-table-frontend -n missing-table-prod

# Option 2: Rollback database migration
# (Only if schema changes cause issues)
cd supabase/migrations
# Create rollback migration
touch 021_rollback_live_match.sql
# Apply rollback
npx supabase db push

# Option 3: Full Helm rollback
helm rollback missing-table -n missing-table-prod
```

---

## ⚡ Performance Considerations

### Database Optimization

**Indexes** (already in migration):
- `idx_live_matches_match_id` - Fast lookup by match ID
- `idx_live_matches_status` - Fast filtering by status
- `idx_chat_messages_match_id` - Fast chat message retrieval

**Query Optimization**:
```sql
-- Use selective queries
SELECT id, match_id, home_score, away_score, clock_seconds
FROM live_matches
WHERE status != 'ended'
ORDER BY started_at DESC;

-- Limit chat history
SELECT * FROM match_chat_messages
WHERE match_id = 'xyz'
AND is_deleted = false
ORDER BY created_at DESC
LIMIT 100;
```

### Real-time Optimization

**Broadcast vs Postgres Changes**:
- Use **Broadcast** for high-frequency updates (clock ticks)
- Use **Postgres Changes** for important state (scores, status)

**Channel Management**:
```javascript
// One channel per match (good)
const channel = supabase.channel(`live_match_${matchId}`);

// Don't create multiple channels (bad)
// const scoreChannel = supabase.channel('scores');
// const chatChannel = supabase.channel('chat');
// const clockChannel = supabase.channel('clock');
```

### Frontend Optimization

**Lazy Loading**:
```javascript
// Only load live match components when needed
const LiveMatchViewer = () => import('@/components/LiveMatchViewer.vue');
```

**Debouncing**:
```javascript
// Debounce chat input
import { debounce } from 'lodash-es';

const sendMessage = debounce(async () => {
  // ...
}, 300);
```

### Monitoring

Add monitoring for:
- Active live matches count
- Concurrent viewer count
- Message throughput
- WebSocket connection errors
- Database query performance

---

## 🚀 Future Enhancements

### Phase 2 Features (After Initial Launch)

1. **Video Streaming Integration**
   - Embed live video stream alongside match data
   - Sync video with match clock

2. **Enhanced Statistics**
   - Live possession percentage
   - Shot charts
   - Player substitutions

3. **Push Notifications**
   - Notify users when followed teams go live
   - Goal notifications

4. **Match Highlights**
   - Timestamp important events (goals, cards)
   - Auto-generate highlight reel

5. **Advanced Moderation**
   - AI-powered chat moderation
   - User reporting
   - Timeout/ban system

6. **Social Features**
   - Reactions to goals
   - Fan polls during match
   - Match predictions

7. **Analytics Dashboard**
   - Viewer engagement metrics
   - Chat activity heatmap
   - Popular matches tracking

---

## 📖 Related Documentation

- **[Architecture Overview](../03-architecture/README.md)** - System design principles
- **[Backend Structure](../03-architecture/backend-structure.md)** - FastAPI patterns
- **[Authentication](../03-architecture/authentication.md)** - Auth flow and roles
- **[Testing Strategy](../04-testing/testing-strategy.md)** - Testing approach
- **[Deployment Guide](../05-deployment/README.md)** - Deployment processes
- **[Database Operations](../02-development/database-operations.md)** - Database management

---

## 🆘 Troubleshooting

### Common Issues

**Issue**: Real-time updates not working
**Solution**:
1. Check Realtime is enabled: `ALTER PUBLICATION supabase_realtime ADD TABLE live_matches;`
2. Verify RLS policies allow SELECT
3. Check browser console for WebSocket errors

**Issue**: Clock not syncing
**Solution**:
1. Verify broadcast messages are being sent (backend logs)
2. Check channel subscription status
3. Ensure clock service is running

**Issue**: Chat messages delayed
**Solution**:
1. Check Supabase rate limits
2. Verify database connection pool
3. Check for slow queries

---

## 📝 Notes

- This plan assumes 3-4 weeks of part-time development
- Each phase can be done incrementally
- Test thoroughly in dev before deploying to prod
- Get user feedback early and often
- Monitor Supabase usage and upgrade plan if needed

---

**Last Updated**: 2025-01-16
**Author**: Claude Code
**Status**: 📝 Planning Phase

---

<div align="center">

[⬆ Back to Documentation Hub](../README.md)

</div>
