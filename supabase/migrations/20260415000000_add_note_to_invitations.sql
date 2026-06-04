-- Add note column to invitations table
-- Allows admins/managers to record who they sent the invite to (e.g., "John Smith - U13 coach")

ALTER TABLE public.invitations ADD COLUMN IF NOT EXISTS note VARCHAR(500);
