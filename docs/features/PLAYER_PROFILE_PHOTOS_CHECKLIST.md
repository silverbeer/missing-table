# Player Profile Photos & Customization - Implementation Checklist

> **Feature Branch:** `feature/player-profile-photos`
> **Started:** 2025-11-29
> **Status:** ✅ Implementation Complete - Ready for PR

## Overview

Allow players to upload up to 3 profile photos with customizable overlays showing their number and position. Players can personalize colors and preview changes before publishing.

---

## Phase 1: Database & Storage Setup ✅ COMPLETE

### 1.1 Create Migration File
- [x] Create `supabase/migrations/20251129000001_add_player_photos.sql`
- [x] Add columns to user_profiles:
  - [x] `photo_1_url TEXT`
  - [x] `photo_2_url TEXT`
  - [x] `photo_3_url TEXT`
  - [x] `profile_photo_slot INTEGER CHECK (1,2,3)`
  - [x] `overlay_style VARCHAR(20) DEFAULT 'badge'`
  - [x] `primary_color VARCHAR(7) DEFAULT '#3B82F6'`
  - [x] `text_color VARCHAR(7) DEFAULT '#FFFFFF'`
  - [x] `accent_color VARCHAR(7) DEFAULT '#1D4ED8'`
- [x] Create `player-photos` storage bucket (with public flag, size/type limits)
- [x] Add RLS policies for storage bucket
- [x] Add service_role policy for backend access

### 1.2 Apply Migration
- [x] Apply to local: `psql` + manual bucket setup
- [x] Verify columns exist in local database
- [ ] Apply to dev (after local testing)

### 1.3 Testing - Phase 1
- [x] Verify new columns in database
- [x] Verify `player-photos` bucket exists in Storage
- [x] Test RLS: can upload file to bucket with service role
- [x] Created test player user: `tom_player` / `player123`

---

## Phase 2: Backend API Endpoints ✅ COMPLETE

### 2.1 Update Pydantic Models
- [x] Edit `backend/models/auth.py`
- [x] Added `ProfilePhotoSlot` model with slot validation
- [x] Added `PlayerCustomization` model with color/style validation
- [x] Updated `UserProfile` model with photo and customization fields

### 2.2 Create Photo Upload Endpoint
- [x] `POST /api/auth/profile/photo/{slot}` in `backend/app.py`
- [x] Validate slot (1, 2, or 3)
- [x] Validate file type (image/jpeg, image/png, image/webp)
- [x] Validate file size (500KB max)
- [x] Upload to `player-photos/{user_id}/photo_{slot}.{ext}`
- [x] Update user_profiles with URL
- [x] Auto-set profile_photo_slot on first upload
- [x] Return updated profile
- [x] Uses direct HTTP API (StorageHelper) to bypass RLS issues

### 2.3 Create Photo Delete Endpoint
- [x] `DELETE /api/auth/profile/photo/{slot}` in `backend/app.py`
- [x] Delete from storage
- [x] Set `photo_{slot}_url` to NULL
- [x] Handle profile_photo_slot reassignment if needed
- [x] Return updated profile

### 2.4 Create Set Profile Photo Endpoint
- [x] `PUT /api/auth/profile/photo/profile-slot` in `backend/app.py`
- [x] Validate slot (1, 2, or 3)
- [x] Update `profile_photo_slot`
- [x] Return updated profile

### 2.5 Create Customization Endpoint
- [x] `PUT /api/auth/profile/customization` in `backend/app.py`
- [x] Accepts overlay_style, colors, player_number, positions
- [x] Validates overlay_style enum (badge, jersey, caption, none)
- [x] Validates color format (hex #RRGGBB)
- [x] Players only (require_player_role dependency)

### 2.6 Testing - Phase 2
- [x] Test upload with valid image < 500KB ✓
- [x] Test upload with image > 500KB (rejected with 400) ✓
- [x] Test upload with non-image file (rejected with 400) ✓
- [x] Test upload to slots 1, 2, 3 ✓
- [x] Test upload as non-player role (rejected with 403) ✓
- [x] Test delete photo ✓
- [x] Test set profile slot ✓
- [x] Test update customization (colors, style, number, positions) ✓
- [x] Test invalid slot (rejected with 400) ✓

---

## Phase 3: Frontend - Core Components ✅ COMPLETE

### 3.1 ColorPalette Component
- [x] Create `frontend/src/components/profiles/ColorPalette.vue`
- [x] 16 preset color swatches
- [x] Props: `modelValue`, `label`
- [x] Emit: `update:modelValue`
- [x] Visual: selected state, hover state

### 3.2 Testing - ColorPalette
- [x] Component renders 16 colors
- [x] Clicking color emits value
- [x] Selected color shows indicator
- [x] Works in isolation (Storybook/test page)

### 3.3 PlayerPhotoOverlay Component
- [x] Create `frontend/src/components/profiles/PlayerPhotoOverlay.vue`
- [x] Props: `photoUrl`, `number`, `position`, `style`, `primaryColor`, `textColor`, `accentColor`
- [x] Implement 3 overlay styles:
  - [x] `badge` - corner circle with number, position pill
  - [x] `jersey` - centered large number, position below
  - [x] `caption` - colored bar below with #number | position
- [x] Implement `none` style (no overlay)
- [x] Use CSS for all overlay rendering

### 3.4 Testing - PlayerPhotoOverlay
- [x] Badge style renders correctly
- [x] Jersey style renders correctly
- [x] Caption style renders correctly
- [x] None style shows photo only
- [x] Colors apply correctly to each style
- [x] Handles missing number/position gracefully

---

## Phase 4: Frontend - Photo Upload ✅ COMPLETE

### 4.1 PlayerPhotoUpload Component
- [x] Create `frontend/src/components/profiles/PlayerPhotoUpload.vue`
- [x] Display 3 photo slots (grid layout)
- [x] Empty slot shows "+" upload button
- [x] Filled slot shows:
  - [x] Photo with overlay preview
  - [x] Delete (X) button
  - [x] "Set as Profile" button (if not current)
  - [x] Star indicator on profile photo
- [x] Hidden file input per slot
- [x] File validation (size, type) with error messages
- [x] Upload progress indicator
- [x] Inline help tooltip with iPhone instructions

### 4.2 Testing - PlayerPhotoUpload
- [x] Can upload photo to empty slot
- [x] Shows error for file > 500KB
- [x] Shows error for non-image file
- [x] Can delete uploaded photo
- [x] Can set photo as profile
- [x] Deleting profile photo reassigns correctly
- [x] Help tooltip displays iPhone instructions
- [x] Upload shows progress/loading state

---

## Phase 5: Frontend - Profile Editor Page ✅ COMPLETE

### 5.1 PlayerProfileEditor Component
- [x] Create `frontend/src/components/profiles/PlayerProfileEditor.vue`
- [x] Two-column layout: Preview | Settings
- [x] Left side: Live preview using PlayerPhotoOverlay
- [x] Right side:
  - [x] "Use Team Colors" button
  - [x] Style selector (radio: badge/jersey/caption/none)
  - [x] Primary color palette
  - [x] Text color palette
  - [x] Accent color palette
  - [x] Number input
  - [x] Position dropdown
- [x] Header: Cancel and Publish buttons
- [x] Local state management (no API calls until Publish)
- [x] Unsaved changes warning on navigation

### 5.2 Preview/Publish Logic
- [x] Initialize local state from current profile
- [x] All changes update local state only
- [x] Preview component reads from local state
- [x] "Use Team Colors" applies team.club colors
- [x] Cancel reverts to saved values
- [x] Publish sends all changes in one API call
- [x] Success: show confirmation, update saved state
- [x] Error: show error message, keep local state

### 5.3 Testing - PlayerProfileEditor
- [x] Preview updates live as settings change
- [x] Style changes reflect in preview
- [x] Color changes reflect in preview
- [x] Number/position changes reflect in preview
- [x] "Use Team Colors" applies correct colors
- [x] Cancel discards changes
- [x] Publish saves all changes
- [x] Navigation shows unsaved warning if changes exist

---

## Phase 6: Integration ✅ COMPLETE

### 6.1 Update PlayerProfile.vue
- [x] Add "Edit Profile" button (visible only to profile owner)
- [x] Button opens PlayerProfileEditor
- [x] Display profile photo with overlay on main profile
- [x] Show player's customized colors/style

### 6.2 Router/Navigation
- [x] Decide: modal vs separate route for editor (modal chosen)
- [x] Implement navigation to/from editor
- [x] Handle unsaved changes on back navigation

### 6.3 Testing - Integration
- [x] "Edit Profile" button appears for player viewing own profile
- [x] "Edit Profile" button hidden for others viewing profile
- [x] Editor opens correctly
- [x] Changes save and reflect on main profile
- [x] Profile displays with correct overlay style/colors

---

## Phase 7: Final Testing & Polish

### 7.1 End-to-End Testing
- [ ] Full flow: Login as player → Edit Profile → Upload photo → Customize → Publish
- [ ] Verify changes persist after logout/login
- [ ] Test on mobile viewport (responsive)
- [ ] Test with slow network (loading states)

### 7.2 Edge Cases
- [ ] Player with no photos
- [ ] Player with 1, 2, 3 photos
- [ ] Player with no team (no team colors)
- [ ] Player with no number/position set
- [ ] Very long position name
- [ ] Special characters in number field

### 7.3 Error Handling
- [ ] Network error during upload
- [ ] Network error during publish
- [ ] Session expired during edit
- [ ] Storage quota exceeded

### 7.4 Polish
- [ ] Loading spinners/skeletons
- [ ] Success toast messages
- [ ] Error toast messages
- [ ] Smooth transitions/animations
- [ ] Accessibility (keyboard nav, screen readers)

---

## Phase 8: Documentation & Deployment

### 8.1 Documentation
- [ ] Update CLAUDE.md with new feature
- [ ] Add inline code comments where needed
- [ ] Document API endpoints in OpenAPI/Swagger

### 8.2 Deployment
- [ ] Create feature branch PR
- [ ] Code review
- [ ] Merge to main
- [ ] Apply migration to dev environment
- [ ] Verify in dev environment
- [ ] Apply migration to prod (when ready)

---

## Quick Reference

### File Locations
| File | Purpose |
|------|---------|
| `supabase/migrations/20251129000001_*.sql` | Database migration |
| `backend/models/auth.py` | Pydantic models |
| `backend/app.py` | API endpoints |
| `frontend/src/components/profiles/ColorPalette.vue` | Color picker |
| `frontend/src/components/profiles/PlayerPhotoOverlay.vue` | Overlay rendering |
| `frontend/src/components/profiles/PlayerPhotoUpload.vue` | Photo management |
| `frontend/src/components/profiles/PlayerProfileEditor.vue` | Edit page |
| `frontend/src/components/profiles/PlayerProfile.vue` | Main profile (update) |

### Test Users
- `tom` / `admin123` - Admin (cannot use feature)
- `tom_ifa` / `team123` - Team Manager (cannot use feature)
- `tom_ifa_fan` / `fan123` - Fan (cannot use feature)
- `tom_player` / `player123` - **Team Player** (can use feature) ✅

### Color Palette
```
Blues:    #3B82F6  #1D4ED8  #0EA5E9  #06B6D4
Greens:   #22C55E  #10B981  #14B8A6
Reds:     #EF4444  #DC2626  #F97316
Purples:  #8B5CF6  #A855F7  #EC4899
Neutrals: #FFFFFF  #1F2937  #374151  #000000
```

### Overlay Styles
- `badge` - Corner circle badge (default)
- `jersey` - Large centered number
- `caption` - Bar below photo
- `none` - No overlay

---

**Last Updated:** 2025-11-29
