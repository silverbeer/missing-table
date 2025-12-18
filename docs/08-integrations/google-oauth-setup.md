# Google OAuth Setup Guide

This guide explains how to enable "Sign in with Google" for Missing Table.

## Overview

Missing Table supports social login via Google OAuth. Users can sign in with their Google account instead of creating a username/password.

**Flow:**
```
User clicks "Continue with Google"
    → Redirect to Google consent screen
    → User approves
    → Google redirects to Supabase
    → Supabase creates/links user
    → Redirect back to Missing Table with tokens
    → Backend verifies and creates profile
    → User is logged in
```

## Prerequisites

- Google Cloud Platform account
- Access to Supabase Dashboard
- Admin access to Missing Table deployment

## Step 1: Google Cloud Console Setup

### 1.1 Create OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. Select **Web application**

### 1.2 Configure OAuth Client

**Name:** `Missing Table OAuth`

**Authorized JavaScript origins:**
```
# Local development
http://localhost:8080
http://localhost:54321

# Production (add your domains)
https://missingtable.com
https://www.missingtable.com
https://dev.missingtable.com
```

**Authorized redirect URIs:**
```
# Supabase callback URLs (REQUIRED)
# Replace YOUR_PROJECT_REF with your Supabase project reference

# For local Supabase
http://localhost:54321/auth/v1/callback

# For cloud Supabase (dev)
https://ppgxasqgqbnauvxozmjw.supabase.co/auth/v1/callback

# For production Supabase
https://YOUR_PROD_PROJECT_REF.supabase.co/auth/v1/callback
```

### 1.3 Save Credentials

After creating, you'll get:
- **Client ID:** `xxxxx.apps.googleusercontent.com`
- **Client Secret:** `GOCSPX-xxxxx`

Save these securely - you'll need them for Supabase.

## Step 2: Supabase Dashboard Setup

### 2.1 Enable Google Provider

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project
3. Navigate to **Authentication** → **Providers**
4. Find **Google** and click to expand
5. Toggle **Enable Sign in with Google**

### 2.2 Configure Provider

Enter the credentials from Google Cloud Console:

| Field | Value |
|-------|-------|
| Client ID | Your Google OAuth Client ID |
| Client Secret | Your Google OAuth Client Secret |

**Authorized Client IDs (optional):**
Leave empty unless you have specific requirements.

### 2.3 Configure Redirect URLs

Supabase will show you the callback URL. Make sure this matches what you configured in Google Cloud Console.

## Step 3: Environment Configuration

### Local Development

No changes needed - the app uses local Supabase URL by default.

Make sure local Supabase is running:
```bash
cd supabase-local && npx supabase start
```

### Cloud Development

Update `frontend/.env.dev`:
```bash
# These should already be set
VUE_APP_SUPABASE_URL=https://ppgxasqgqbnauvxozmjw.supabase.co
VUE_APP_SUPABASE_ANON_KEY=your_anon_key
```

### Production

Update `frontend/.env.prod`:
```bash
VUE_APP_SUPABASE_URL=https://YOUR_PROD_PROJECT.supabase.co
VUE_APP_SUPABASE_ANON_KEY=your_prod_anon_key
```

## Step 4: Database Migration

Run the OAuth support migration to add required columns:

```bash
# Local
cd supabase-local && npx supabase db reset

# Cloud (after testing locally)
./switch-env.sh dev
cd supabase-local && npx supabase db push --linked
```

The migration adds:
- `auth_provider` column (tracks: password, google, github, etc.)
- `profile_photo_url` column (stores OAuth avatar URL)

## Testing

### Local Testing

1. Start the app:
   ```bash
   ./missing-table.sh dev
   ```

2. Go to http://localhost:8080
3. Click **Log In**
4. Click **Continue with Google**
5. Complete Google sign-in
6. Verify you're logged in

### Verify in Database

```sql
SELECT id, username, email, auth_provider, profile_photo_url
FROM user_profiles
WHERE auth_provider = 'google';
```

## Troubleshooting

### "redirect_uri_mismatch" Error

The redirect URI in Google Cloud Console doesn't match Supabase.

**Fix:** Ensure the Supabase callback URL is in Google's authorized redirect URIs:
```
https://YOUR_PROJECT.supabase.co/auth/v1/callback
```

### "OAuth callback failed" Error

The backend couldn't verify the token or create the profile.

**Check:**
1. Supabase URL and Anon Key are correct in backend `.env`
2. Database migration was applied
3. Backend logs for specific error

### User Profile Not Created

The OAuth callback endpoint might be failing silently.

**Check:**
1. Backend logs: `docker logs missing-table-backend`
2. Browser console for errors
3. Network tab for `/api/auth/oauth/callback` response

### Google Button Not Showing

Only shows on login form, not on invite signup form.

**Expected behavior:** OAuth is only available for login, not invite-based signup.

## Security Considerations

1. **Never commit secrets** - Google Client Secret should only be in Supabase Dashboard
2. **Use HTTPS in production** - OAuth requires secure redirects
3. **Restrict origins** - Only add domains you control to Google Console
4. **Monitor OAuth users** - New users get `team-fan` role by default

## Related Documentation

- [Supabase Google OAuth Docs](https://supabase.com/docs/guides/auth/social-login/auth-google)
- [Google OAuth 2.0 Docs](https://developers.google.com/identity/protocols/oauth2)
- [Authentication Architecture](../03-architecture/authentication.md)
