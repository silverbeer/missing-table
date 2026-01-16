-- Migration: Enable Supabase Realtime for live match tables
-- This allows clients to subscribe to real-time updates

-- Add matches table to realtime publication (for score/clock updates)
-- Using DO block to handle case where table is already in publication
DO $$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE matches;
EXCEPTION
    WHEN duplicate_object THEN
        RAISE NOTICE 'matches table already in supabase_realtime publication';
END $$;

-- Add match_events table to realtime publication (for activity stream)
DO $$
BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE match_events;
EXCEPTION
    WHEN duplicate_object THEN
        RAISE NOTICE 'match_events table already in supabase_realtime publication';
END $$;
