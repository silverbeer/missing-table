-- Add audit trail fields to games table
-- Track who created/updated games and the source (manual, match-scraper, import)

-- Add audit columns
ALTER TABLE games
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'manual';

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_games_updated_by ON games(updated_by);
CREATE INDEX IF NOT EXISTS idx_games_created_by ON games(created_by);
CREATE INDEX IF NOT EXISTS idx_games_source ON games(source);

-- Add comments for documentation
COMMENT ON COLUMN games.created_by IS 'User ID who created the game (match-scraper service account for legacy data)';
COMMENT ON COLUMN games.updated_by IS 'User ID who last updated the game';
COMMENT ON COLUMN games.source IS 'Source of game data: manual, match-scraper, import, etc.';

-- Create a service account user for match-scraper if it doesn't exist
-- This ensures we have a valid user_id to attribute legacy games to
DO $$
DECLARE
  scraper_user_id UUID;
BEGIN
  -- Try to find existing match-scraper service account
  SELECT id INTO scraper_user_id
  FROM auth.users
  WHERE email = 'match-scraper@service.missingtable.com'
  LIMIT 1;

  -- If not found, create it
  IF scraper_user_id IS NULL THEN
    -- Insert into auth.users (Supabase auth table)
    INSERT INTO auth.users (
      instance_id,
      id,
      aud,
      role,
      email,
      encrypted_password,
      email_confirmed_at,
      recovery_sent_at,
      last_sign_in_at,
      raw_app_meta_data,
      raw_user_meta_data,
      created_at,
      updated_at,
      confirmation_token,
      email_change,
      email_change_token_new,
      recovery_token
    ) VALUES (
      '00000000-0000-0000-0000-000000000000',
      gen_random_uuid(),
      'authenticated',
      'authenticated',
      'match-scraper@service.missingtable.com',
      crypt('service-account-no-password', gen_salt('bf')),
      NOW(),
      NOW(),
      NOW(),
      '{"provider":"email","providers":["email"],"service_account":true}',
      '{"display_name":"Match Scraper Service","service_account":true}',
      NOW(),
      NOW(),
      '',
      '',
      '',
      ''
    )
    RETURNING id INTO scraper_user_id;

    -- Create corresponding user profile with service_account role
    INSERT INTO user_profiles (id, role, display_name)
    VALUES (scraper_user_id, 'service_account', 'Match Scraper Service')
    ON CONFLICT (id) DO NOTHING;
  END IF;

  -- Backfill existing games with match-scraper as creator
  -- Set source based on whether game has external match_id
  UPDATE games
  SET
    source = CASE
      WHEN match_id IS NOT NULL THEN 'match-scraper'
      ELSE 'import'
    END,
    created_by = scraper_user_id,
    updated_by = scraper_user_id
  WHERE created_by IS NULL;

END $$;
