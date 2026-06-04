-- Add 'played' boolean to player_match_stats
-- Tracks whether a player participated in a match (started or came off bench).
-- Players who started obviously played, but this allows recording participation
-- for matches where a full starting lineup wasn't set.

ALTER TABLE public.player_match_stats
    ADD COLUMN played boolean DEFAULT false NOT NULL;

COMMENT ON COLUMN public.player_match_stats.played IS 'Whether player participated in the match (started or came off bench)';

-- Backfill: any existing row with started=true or goals>0 or minutes_played>0 should be marked as played
UPDATE public.player_match_stats
SET played = true
WHERE started = true OR goals > 0 OR minutes_played > 0;
