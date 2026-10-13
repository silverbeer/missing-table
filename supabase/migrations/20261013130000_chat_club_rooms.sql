-- SB-1330: club-scoped live chat. Each club playing in a match has its own room.
--
-- chat_club_id is the room a chat message was posted in: the poster's club,
-- set by the API (or the admin's chosen room). The API is the only reader of
-- chat rows (SB-1329) and shows each viewer only their club's room.
--
-- Messages posted before this column existed have it NULL. They are shown in
-- every room of their match and age out with the 10-day chat cleanup.

ALTER TABLE public.match_events
    ADD COLUMN IF NOT EXISTS chat_club_id integer REFERENCES public.clubs(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.match_events.chat_club_id IS
    'SB-1330: club room a chat message belongs to; NULL for non-chat events and pre-rooms messages.';

CREATE INDEX IF NOT EXISTS idx_match_events_chat_room
    ON public.match_events (match_id, chat_club_id)
    WHERE event_type = 'message';
