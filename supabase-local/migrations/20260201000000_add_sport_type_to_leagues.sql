-- Add sport_type column to leagues table
-- Allows distinguishing between soccer and futsal leagues
-- so the UI can adapt (e.g., hide Fall/Spring segments for futsal)

ALTER TABLE public.leagues
ADD COLUMN IF NOT EXISTS sport_type character varying(20) DEFAULT 'soccer' NOT NULL;

-- Mark existing futsal leagues
UPDATE public.leagues SET sport_type = 'futsal' WHERE LOWER(name) LIKE '%futsal%';
