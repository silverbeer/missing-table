-- Add match-photo storage columns for the Instagram share-image feature (SB-31 / SB-19).
-- Photos live in Cloudflare R2; we store the object key locally so we can re-mint
-- signed URLs on demand and clean up on match delete.

ALTER TABLE public.matches
  ADD COLUMN IF NOT EXISTS photo_url TEXT,
  ADD COLUMN IF NOT EXISTS photo_key TEXT;

COMMENT ON COLUMN public.matches.photo_url IS
  'Signed Cloudflare R2 URL for the match photo (1h TTL). Re-minted from photo_key when expired.';

COMMENT ON COLUMN public.matches.photo_key IS
  'Cloudflare R2 object key (e.g. matches/{match_id}/{uuid}.jpg). Used to re-mint signed URLs and to delete the object on match deletion.';
