-- Merge a duplicate team into its canonical row, and a duplicate club into its
-- canonical club (SB-1822)
--
-- A feed spelling a team differently has, more than once, created a second
-- team: 'City SC San Diego' (581, club 247) beside 'City SC - San Diego'
-- (937, club 446); PDA 318 beside 911; Columbus Crew (SB-1789). Merging by
-- hand means remembering every table that holds a team id. These two
-- functions know them, so the next duplicate is one call, not a session.
--
-- Both run as one transaction and default to a dry run: the same work is done
-- inside a subtransaction that is then rolled back, so the per-table counts a
-- dry run reports are the counts a real run produces. The source row is locked
-- FOR UPDATE and the target FOR KEY SHARE, so a concurrent edit or merge of
-- either waits rather than racing.
--
-- What a merge refuses rather than guesses (returned as `blockers`; a real run
-- raises while any exist). Merges are rare and admin-run: when in doubt, block.
--   * a match between the two teams — after the merge it would be a team
--     playing itself (matches_check);
--   * a same-day fixture of the target on the same key (unique_manual_match)
--     that is a *different* fixture: another external match_id, tournament,
--     round or side age group;
--   * a duplicate fixture whose source row carries anything the target's does
--     not: user data (events, lineups, player stats, MOTW/MOTD, bracket slot,
--     notification threads),
--     a differing score, penalty score or status, a score lock, or a photo —
--     dropping it would lose attribution (rule 5). A dropped copy hands its
--     external match_id to a target that has none; if that id has more than
--     one place to go, that is a blocker too;
--   * two active players with the same jersey on the same team/season/age
--     group — a roster conflict a person has to settle;
--   * a notification channel the target already has — its members and
--     delivery history would go with a dropped row;
--   * a league-agnostic alias of the source's name pointing at a third team —
--     the feed would resolve the name ambiguously;
--   * (clubs) two teams of the same name and league, one in each club — merge
--     those teams first;
--   * any row still referencing the source after every listed table moved — a
--     table added since this was written; extend the function first.
--
-- Derived rows (power ratings, rating deltas) are deleted, not moved: they are
-- recomputed by the next rating run.
--
-- The functions' own refusals carry their own SQLSTATE, so callers classify
-- them without reading message text: MTSAM (same/missing id), MTNF1 (not
-- found), MTBLK (blocked).
--
-- Functions only: no table, no column, so nothing for the backup registries.

-- ---------------------------------------------------------------------------
-- _merge_rows: repoint one FK column, dropping source rows that would collide
-- with a row the target already has on `p_key` (the other columns of the
-- table's unique key). Key columns compare with IS NOT DISTINCT FROM, so a
-- NULL-keyed duplicate is a duplicate. Returns {moved, dropped}.
--
-- Internal to merge_team/merge_club: invoker rights, no EXECUTE for any API
-- role, and only the (table, column) pairs those two functions move.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public._merge_rows(regclass, text, integer, integer, text[]);
CREATE FUNCTION public._merge_rows(
    p_table regclass,
    p_col text,
    p_from integer,
    p_into integer,
    p_key text[] DEFAULT '{}'
) RETURNS jsonb
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_dropped integer := 0;
    v_moved integer := 0;
    v_match text;
BEGIN
    IF p_from IS NULL OR p_into IS NULL OR p_from = p_into THEN
        RAISE EXCEPTION USING ERRCODE = 'MTSAM', MESSAGE = '_merge_rows: source and target must differ';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM (VALUES
                ('public.team_mappings'::regclass, 'team_id'),
                ('public.team_match_types'::regclass, 'team_id'),
                ('public.team_aliases'::regclass, 'team_id'),
                ('public.players'::regclass, 'team_id'),
                ('public.player_team_history'::regclass, 'team_id'),
                ('public.match_lineups'::regclass, 'team_id'),
                ('public.match_events'::regclass, 'team_id'),
                ('public.team_manager_assignments'::regclass, 'team_id'),
                ('public.user_profiles'::regclass, 'team_id'),
                ('public.invitations'::regclass, 'team_id'),
                ('public.user_team_follows'::regclass, 'team_id'),
                ('public.channel_access_requests'::regclass, 'team_id'),
                ('public.notification_channels'::regclass, 'team_id'),
                ('public.division_guests'::regclass, 'team_id'),
                ('public.qop_rankings'::regclass, 'team_id'),
                ('public.teams'::regclass, 'club_id'),
                ('public.user_profiles'::regclass, 'club_id'),
                ('public.invitations'::regclass, 'club_id'),
                ('public.match_events'::regclass, 'chat_club_id'),
                ('public.notification_channels'::regclass, 'club_id'),
                ('public.club_notification_channels'::regclass, 'club_id')
               ) AS allowed(tbl, col)
         WHERE allowed.tbl = p_table AND allowed.col = p_col
    ) THEN
        RAISE EXCEPTION '_merge_rows: %.% is not a merge column', p_table, p_col;
    END IF;

    IF coalesce(array_length(p_key, 1), 0) > 0 THEN
        SELECT string_agg(format('t.%1$I IS NOT DISTINCT FROM s.%1$I', k), ' AND ')
          INTO v_match
          FROM unnest(p_key) AS k;
        EXECUTE format(
            'DELETE FROM %1$s s WHERE s.%2$I = $1 AND EXISTS '
            '(SELECT 1 FROM %1$s t WHERE t.%2$I = $2 AND %3$s)',
            p_table, p_col, v_match
        ) USING p_from, p_into;
        GET DIAGNOSTICS v_dropped = ROW_COUNT;
    END IF;

    EXECUTE format('UPDATE %1$s SET %2$I = $2 WHERE %2$I = $1', p_table, p_col)
        USING p_from, p_into;
    GET DIAGNOSTICS v_moved = ROW_COUNT;

    RETURN jsonb_build_object('moved', v_moved, 'dropped', v_dropped);
END;
$$;

REVOKE ALL ON FUNCTION public._merge_rows(regclass, text, integer, integer, text[])
    FROM PUBLIC, anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- _merge_leftover_refs: every FK into p_parent whose table still holds a row
-- referencing p_id. Called just before the source row is deleted, after every
-- listed table has moved, so anything found is a table the merge does not know.
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public._merge_leftover_refs(regclass, integer);
CREATE FUNCTION public._merge_leftover_refs(
    p_parent regclass,
    p_id integer
) RETURNS jsonb
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    r record;
    v_found boolean;
    v_out jsonb := '[]'::jsonb;
BEGIN
    FOR r IN
        SELECT c.conrelid::regclass AS tbl, c.conname, c.conkey,
               (SELECT a.attname FROM pg_attribute a
                 WHERE a.attrelid = c.conrelid AND a.attnum = c.conkey[1]) AS col
          FROM pg_constraint c
         WHERE c.contype = 'f' AND c.confrelid = p_parent
         ORDER BY 1, 2
    LOOP
        IF cardinality(r.conkey) <> 1 THEN
            -- Not a shape this function moves; a person decides.
            v_out := v_out || jsonb_build_object('table', r.tbl::text, 'constraint', r.conname);
            CONTINUE;
        END IF;
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM %s WHERE %I = $1)', r.tbl, r.col)
           INTO v_found USING p_id;
        IF v_found THEN
            v_out := v_out || jsonb_build_object('table', r.tbl::text, 'column', r.col);
        END IF;
    END LOOP;
    RETURN v_out;
END;
$$;

REVOKE ALL ON FUNCTION public._merge_leftover_refs(regclass, integer)
    FROM PUBLIC, anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- merge_team
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.merge_team(integer, integer, boolean);
CREATE FUNCTION public.merge_team(
    p_from integer,
    p_into integer,
    p_dry_run boolean DEFAULT true
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_from public.teams%ROWTYPE;
    v_into public.teams%ROWTYPE;
    v_blockers jsonb := '[]'::jsonb;
    v_tables jsonb := '{}'::jsonb;
    v_alias text := 'skipped';
    v_copied text[] := '{}';
    v_dups jsonb;
    v_dup_ids integer[];
    v_leftover jsonb;
    v_error jsonb;
    v_state text;
    v_tab text;
    v_con text;
    v_msg text;
    v_n integer;
    v_d integer;
BEGIN
    p_dry_run := coalesce(p_dry_run, true);
    IF p_from IS NULL OR p_into IS NULL OR p_from = p_into THEN
        RAISE EXCEPTION USING ERRCODE = 'MTSAM',
            MESSAGE = 'merge_team: source and target must be two different teams';
    END IF;
    SELECT * INTO v_from FROM public.teams WHERE id = p_from FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'MTNF1', MESSAGE = format('merge_team: team %s does not exist', p_from);
    END IF;
    SELECT * INTO v_into FROM public.teams WHERE id = p_into FOR KEY SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'MTNF1', MESSAGE = format('merge_team: team %s does not exist', p_into);
    END IF;

    -- What the target takes from the source: only gaps, never an overwrite.
    IF v_into.club_id IS NULL AND v_from.club_id IS NOT NULL THEN
        v_copied := v_copied || 'club_id'::text;
    END IF;
    IF nullif(btrim(v_into.city), '') IS NULL AND nullif(btrim(v_from.city), '') IS NOT NULL THEN
        v_copied := v_copied || 'city'::text;
    END IF;

    -- Blockers -------------------------------------------------------------
    SELECT v_blockers || coalesce(jsonb_agg(jsonb_build_object(
               'kind', 'self_match', 'match_id', m.id,
               'detail', 'the two teams play each other in this match')), '[]'::jsonb)
      INTO v_blockers
      FROM public.matches m
     WHERE (m.home_team_id = p_from AND m.away_team_id = p_into)
        OR (m.home_team_id = p_into AND m.away_team_id = p_from);

    -- A target match on the same unique_manual_match key as a source match is
    -- either the same fixture (dropped, if the source copy adds nothing) or a
    -- different one that would collide (blocked).
    -- `ext`: the source's external match_id when the target has none, so a
    -- dropped copy hands it over rather than losing the feed's link.
    SELECT coalesce(jsonb_agg(jsonb_build_object('src', x.src, 'tgt', x.tgt, 'same', x.same_fixture, 'data', x.has_data,
                                                 'ext', x.ext)
                              ORDER BY x.src, x.tgt), '[]'::jsonb)
      INTO v_dups
      FROM (
        SELECT s.id AS src, t.id AS tgt,
               CASE WHEN t.match_id IS NULL THEN s.match_id END AS ext,
               (s.match_id IS NULL OR t.match_id IS NULL OR s.match_id = t.match_id)
               AND s.tournament_id IS NOT DISTINCT FROM t.tournament_id
               AND s.tournament_round IS NOT DISTINCT FROM t.tournament_round
               AND s.home_age_group_id IS NOT DISTINCT FROM t.home_age_group_id
               AND s.away_age_group_id IS NOT DISTINCT FROM t.away_age_group_id AS same_fixture,
               (s.home_score IS NOT NULL AND (s.home_score, s.away_score) IS DISTINCT FROM (t.home_score, t.away_score))
               OR (s.home_penalty_score IS NOT NULL
                   AND (s.home_penalty_score, s.away_penalty_score) IS DISTINCT FROM (t.home_penalty_score, t.away_penalty_score))
               OR coalesce(s.score_locked, false)
               OR nullif(btrim(s.photo_url), '') IS NOT NULL
               OR nullif(btrim(s.photo_key), '') IS NOT NULL
               OR s.match_status IS DISTINCT FROM t.match_status
               OR EXISTS (SELECT 1 FROM public.match_events e WHERE e.match_id = s.id)
               OR EXISTS (SELECT 1 FROM public.match_lineups l WHERE l.match_id = s.id)
               OR EXISTS (SELECT 1 FROM public.player_match_stats p WHERE p.match_id = s.id)
               OR EXISTS (SELECT 1 FROM public.match_of_the_week w WHERE w.match_id = s.id)
               OR EXISTS (SELECT 1 FROM public.tournament_match_of_the_day o WHERE o.match_id = s.id)
               OR EXISTS (SELECT 1 FROM public.playoff_bracket_slots b WHERE b.match_id = s.id)
               OR EXISTS (SELECT 1 FROM public.notification_threads n WHERE n.match_id = s.id) AS has_data
          FROM public.matches s
          JOIN public.matches t
            ON t.id <> s.id
           AND t.home_team_id = CASE WHEN s.home_team_id = p_from THEN p_into ELSE s.home_team_id END
           AND t.away_team_id = CASE WHEN s.away_team_id = p_from THEN p_into ELSE s.away_team_id END
           AND t.match_date = s.match_date
           AND t.season_id = s.season_id
           AND t.age_group_id = s.age_group_id
           AND t.match_type_id = s.match_type_id
           AND t.division_id IS NOT DISTINCT FROM s.division_id
         WHERE p_from IN (s.home_team_id, s.away_team_id)
      ) x;

    SELECT v_blockers || coalesce(jsonb_agg(jsonb_build_object(
               'kind', CASE WHEN (d->>'same')::boolean THEN 'duplicate_fixture_has_data' ELSE 'fixture_collision' END,
               'match_id', (d->>'src')::integer, 'duplicate_of', (d->>'tgt')::integer,
               'detail', CASE WHEN (d->>'same')::boolean
                              THEN 'duplicate fixture carries a differing score, status, lock, photo or user data'
                              ELSE 'a different fixture of the target has the same date and key (match id, tournament, round or age group differ)'
                         END)), '[]'::jsonb)
      INTO v_blockers
      FROM jsonb_array_elements(v_dups) d
     WHERE NOT (d->>'same')::boolean OR (d->>'data')::boolean;

    SELECT coalesce(array_agg(DISTINCT (d->>'src')::integer), '{}') INTO v_dup_ids
      FROM jsonb_array_elements(v_dups) d
     WHERE (d->>'same')::boolean AND NOT (d->>'data')::boolean;

    -- The external id moves only when it has exactly one place to go:
    -- matches_match_id_key allows one row per id, and a target has one id.
    WITH h AS (
        SELECT (d->>'src')::integer AS src, (d->>'tgt')::integer AS tgt,
               count(*) OVER (PARTITION BY d->>'src') AS per_src,
               count(*) OVER (PARTITION BY d->>'tgt') AS per_tgt
          FROM jsonb_array_elements(v_dups) d
         WHERE (d->>'same')::boolean AND NOT (d->>'data')::boolean AND d->>'ext' IS NOT NULL
    )
    SELECT v_blockers || coalesce(jsonb_agg(jsonb_build_object(
               'kind', 'external_id_conflict', 'match_id', h.src, 'duplicate_of', h.tgt,
               'detail', 'the duplicate''s external match id cannot move to a single target row')
               ORDER BY h.src, h.tgt), '[]'::jsonb)
      INTO v_blockers
      FROM h
     WHERE h.per_src > 1 OR h.per_tgt > 1;

    SELECT v_blockers || coalesce(jsonb_agg(jsonb_build_object(
               'kind', 'jersey_conflict', 'player_id', s.id, 'conflicts_with', t.id,
               'detail', 'both teams have an active player with this jersey number')), '[]'::jsonb)
      INTO v_blockers
      FROM public.players s
      JOIN public.players t
        ON t.team_id = p_into
       AND t.is_active
       AND t.season_id IS NOT DISTINCT FROM s.season_id
       AND t.age_group_id IS NOT DISTINCT FROM s.age_group_id
       AND t.jersey_number IS NOT DISTINCT FROM s.jersey_number
     WHERE s.team_id = p_from AND s.is_active;

    SELECT v_blockers || coalesce(jsonb_agg(jsonb_build_object(
               'kind', 'channel_conflict', 'channel_id', s.id, 'conflicts_with', t.id,
               'detail', 'both teams have this notification channel; merge or remove one first')), '[]'::jsonb)
      INTO v_blockers
      FROM public.notification_channels s
      JOIN public.notification_channels t
        ON t.team_id = p_into
       AND t.scope_type = s.scope_type
       AND t.club_id IS NOT DISTINCT FROM s.club_id
       AND t.age_group_id IS NOT DISTINCT FROM s.age_group_id
       AND t.audience = s.audience
       AND t.platform = s.platform
       AND t.destination = s.destination
     WHERE s.team_id = p_from;

    IF lower(v_from.name) <> lower(v_into.name) THEN
        SELECT v_blockers || coalesce(jsonb_agg(jsonb_build_object(
                   'kind', 'alias_conflict', 'alias_id', a.id, 'team_id', a.team_id,
                   'detail', 'the source name is already a league-agnostic alias of another team')), '[]'::jsonb)
          INTO v_blockers
          FROM public.team_aliases a
         WHERE lower(a.external_name) = lower(v_from.name)
           AND a.league_id IS NULL
           AND a.team_id NOT IN (p_from, p_into);
    END IF;

    -- teams_name_club_league_unique, once the target takes the source's club.
    IF 'club_id' = ANY (v_copied) THEN
        SELECT v_blockers || coalesce(jsonb_agg(jsonb_build_object(
                   'kind', 'club_copy_conflict', 'team_id', x.id,
                   'detail', 'the source''s club already has a team with the target''s name in its league')), '[]'::jsonb)
          INTO v_blockers
          FROM public.teams x
         WHERE x.club_id = v_from.club_id
           AND x.name = v_into.name
           AND x.league_id = v_into.league_id
           AND x.id NOT IN (p_from, p_into);
    END IF;

    IF jsonb_array_length(v_blockers) > 0 AND NOT p_dry_run THEN
        RAISE EXCEPTION USING ERRCODE = 'MTBLK',
            MESSAGE = format('merge_team: %s blocker(s), run a dry run to list them', jsonb_array_length(v_blockers));
    END IF;

    -- The merge, in a subtransaction so a dry run can roll it back -----------
    BEGIN
        -- Members and invitations of the source team that were tied to the
        -- source's club now belong to the target's.
        v_n := 0;
        v_d := 0;
        IF v_from.club_id IS NOT NULL AND v_into.club_id IS NOT NULL AND v_from.club_id <> v_into.club_id THEN
            UPDATE public.user_profiles SET club_id = v_into.club_id
             WHERE team_id = p_from AND club_id = v_from.club_id;
            GET DIAGNOSTICS v_n = ROW_COUNT;
            UPDATE public.invitations SET club_id = v_into.club_id
             WHERE team_id = p_from AND club_id = v_from.club_id;
            GET DIAGNOSTICS v_d = ROW_COUNT;
        END IF;
        v_tables := v_tables
            || jsonb_build_object('user_profiles.club_id', jsonb_build_object('moved', v_n, 'dropped', 0))
            || jsonb_build_object('invitations.club_id', jsonb_build_object('moved', v_d, 'dropped', 0));

        -- Duplicate fixtures: the target already has this match, and the
        -- blockers above guarantee the source copy carries nothing more.
        DELETE FROM public.matches WHERE id = ANY (v_dup_ids);
        GET DIAGNOSTICS v_d = ROW_COUNT;

        -- After the delete: the id was the source's until now (unique).
        UPDATE public.matches t
           SET match_id = d->>'ext'
          FROM jsonb_array_elements(v_dups) d
         WHERE t.id = (d->>'tgt')::integer
           AND (d->>'same')::boolean AND NOT (d->>'data')::boolean
           AND d->>'ext' IS NOT NULL
           AND t.match_id IS NULL;
        GET DIAGNOSTICS v_n = ROW_COUNT;
        v_tables := v_tables || jsonb_build_object('matches.match_id', jsonb_build_object('moved', v_n, 'dropped', 0));

        -- One statement: chk_forfeit_team_consistency requires forfeit_team_id
        -- to equal home or away at every row write.
        UPDATE public.matches
           SET home_team_id    = CASE WHEN home_team_id = p_from THEN p_into ELSE home_team_id END,
               away_team_id    = CASE WHEN away_team_id = p_from THEN p_into ELSE away_team_id END,
               forfeit_team_id = CASE WHEN forfeit_team_id = p_from THEN p_into ELSE forfeit_team_id END
         WHERE p_from IN (home_team_id, away_team_id);
        GET DIAGNOSTICS v_n = ROW_COUNT;
        v_tables := v_tables || jsonb_build_object('matches', jsonb_build_object('moved', v_n, 'dropped', v_d));

        -- Derived: recomputed by the next rating run.
        DELETE FROM public.power_rating_match_deltas WHERE team_id = p_from OR opponent_id = p_from;
        GET DIAGNOSTICS v_d = ROW_COUNT;
        v_tables := v_tables || jsonb_build_object('power_rating_match_deltas', jsonb_build_object('moved', 0, 'dropped', v_d));
        DELETE FROM public.power_ratings WHERE team_id = p_from;
        GET DIAGNOSTICS v_d = ROW_COUNT;
        v_tables := v_tables || jsonb_build_object('power_ratings', jsonb_build_object('moved', 0, 'dropped', v_d));

        -- A history row the target already has for this player and season is
        -- kept, but stays current if either copy was.
        UPDATE public.player_team_history t
           SET is_current = true
          FROM public.player_team_history s
         WHERE t.team_id = p_into
           AND s.team_id = p_from
           AND s.player_id = t.player_id
           AND s.season_id = t.season_id
           AND coalesce(s.is_current, false)
           AND NOT coalesce(t.is_current, false);

        v_tables := v_tables
            || jsonb_build_object('team_mappings',
                   public._merge_rows('public.team_mappings', 'team_id', p_from, p_into, ARRAY['age_group_id', 'division_id']))
            || jsonb_build_object('team_match_types',
                   public._merge_rows('public.team_match_types', 'team_id', p_from, p_into, ARRAY['match_type_id', 'age_group_id']))
            -- unique on (lower(external_name), league_id, source): no team_id,
            -- so a row moving between teams cannot collide.
            || jsonb_build_object('team_aliases',
                   public._merge_rows('public.team_aliases', 'team_id', p_from, p_into))
            -- Jersey collisions are blockers above, so this is a plain move.
            || jsonb_build_object('players',
                   public._merge_rows('public.players', 'team_id', p_from, p_into))
            || jsonb_build_object('player_team_history',
                   public._merge_rows('public.player_team_history', 'team_id', p_from, p_into, ARRAY['player_id', 'season_id']))
            || jsonb_build_object('match_lineups',
                   public._merge_rows('public.match_lineups', 'team_id', p_from, p_into, ARRAY['match_id']))
            || jsonb_build_object('match_events',
                   public._merge_rows('public.match_events', 'team_id', p_from, p_into))
            || jsonb_build_object('team_manager_assignments',
                   public._merge_rows('public.team_manager_assignments', 'team_id', p_from, p_into, ARRAY['user_id']))
            || jsonb_build_object('user_profiles',
                   public._merge_rows('public.user_profiles', 'team_id', p_from, p_into))
            || jsonb_build_object('invitations',
                   public._merge_rows('public.invitations', 'team_id', p_from, p_into))
            || jsonb_build_object('user_team_follows',
                   public._merge_rows('public.user_team_follows', 'team_id', p_from, p_into, ARRAY['user_id', 'age_group_id']))
            || jsonb_build_object('channel_access_requests',
                   public._merge_rows('public.channel_access_requests', 'team_id', p_from, p_into, ARRAY['user_id']))
            -- Collisions are blockers above (a dropped channel takes its
            -- members and deliveries with it), so this is a plain move.
            || jsonb_build_object('notification_channels',
                   public._merge_rows('public.notification_channels', 'team_id', p_from, p_into))
            || jsonb_build_object('division_guests',
                   public._merge_rows('public.division_guests', 'team_id', p_from, p_into, ARRAY['division_id', 'age_group_id', 'season_id']))
            -- A scraped QoP snapshot row is keyed by team_name; the id is only
            -- a link, so it follows the team.
            || jsonb_build_object('qop_rankings',
                   public._merge_rows('public.qop_rankings', 'team_id', p_from, p_into));

        -- Keep the retired spelling resolvable so the feed lands on the
        -- canonical team. League-agnostic, like every former name. One that
        -- points at a third team is a blocker above.
        IF lower(v_from.name) = lower(v_into.name) THEN
            v_alias := 'same_name';
        ELSIF EXISTS (SELECT 1 FROM public.team_aliases
                       WHERE lower(external_name) = lower(v_from.name)
                         AND league_id IS NULL
                         AND team_id = p_into) THEN
            v_alias := 'exists';
        ELSE
            INSERT INTO public.team_aliases (team_id, league_id, external_name, kind)
            VALUES (p_into, NULL, v_from.name, 'former_name');
            v_alias := 'added';
        END IF;

        -- Safety net: a table referencing teams that this function does not
        -- move would lose its rows to ON DELETE CASCADE / SET NULL.
        v_leftover := public._merge_leftover_refs('public.teams', p_from);
        IF jsonb_array_length(v_leftover) > 0 THEN
            IF NOT p_dry_run THEN
                RAISE EXCEPTION USING ERRCODE = 'MTBLK',
                    MESSAGE = format('merge_team: rows in %s still reference team %s',
                                     (SELECT string_agg(e->>'table', ', ') FROM jsonb_array_elements(v_leftover) e), p_from);
            END IF;
            SELECT v_blockers || jsonb_agg(e || jsonb_build_object(
                       'kind', 'unlisted_reference',
                       'detail', 'this table references the team and the merge does not move it'))
              INTO v_blockers
              FROM jsonb_array_elements(v_leftover) e;
        ELSE
            DELETE FROM public.teams WHERE id = p_from;

            -- After the delete: the source may hold the target's name in the
            -- club the target is about to take.
            UPDATE public.teams
               SET club_id = CASE WHEN 'club_id' = ANY (v_copied) THEN v_from.club_id ELSE club_id END,
                   city    = CASE WHEN 'city' = ANY (v_copied) THEN v_from.city ELSE city END
             WHERE id = p_into AND cardinality(v_copied) > 0;
        END IF;

        IF p_dry_run THEN
            RAISE EXCEPTION USING ERRCODE = 'MTDRY', MESSAGE = 'dry run';
        END IF;
    EXCEPTION
        WHEN SQLSTATE 'MTDRY' THEN
            NULL;
        WHEN OTHERS THEN
            IF NOT p_dry_run THEN
                RAISE;
            END IF;
            -- A dry run with blockers can trip the constraint a blocker names;
            -- report what was counted before it did, as a code, not a message.
            GET STACKED DIAGNOSTICS v_state = RETURNED_SQLSTATE, v_tab = TABLE_NAME,
                                    v_con = CONSTRAINT_NAME, v_msg = MESSAGE_TEXT;
            v_error := jsonb_strip_nulls(jsonb_build_object(
                'sqlstate', v_state, 'table', nullif(v_tab, ''), 'constraint', nullif(v_con, '')));
            RAISE WARNING 'merge_team(%, %) dry run stopped early: % (SQLSTATE %)', p_from, p_into, v_msg, v_state;
    END;

    RETURN jsonb_build_object(
        'from', jsonb_build_object('id', v_from.id, 'name', v_from.name),
        'into', jsonb_build_object('id', v_into.id, 'name', v_into.name),
        'dry_run', p_dry_run,
        'tables', v_tables,
        'alias', v_alias,
        'copied', to_jsonb(v_copied),
        'blockers', v_blockers,
        'error', v_error,
        'complete', v_error IS NULL
    );
END;
$$;

COMMENT ON FUNCTION public.merge_team(integer, integer, boolean) IS
    'SB-1822: repoint every row referencing team p_from to p_into, drop collisions, fill p_into''s empty club/city, record p_from''s name as a former_name alias, delete p_from. Dry run by default.';

REVOKE ALL ON FUNCTION public.merge_team(integer, integer, boolean) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.merge_team(integer, integer, boolean) TO service_role;

-- ---------------------------------------------------------------------------
-- merge_club
-- ---------------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.merge_club(integer, integer, boolean);
CREATE FUNCTION public.merge_club(
    p_from integer,
    p_into integer,
    p_dry_run boolean DEFAULT true
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_from public.clubs%ROWTYPE;
    v_into public.clubs%ROWTYPE;
    v_blockers jsonb := '[]'::jsonb;
    v_tables jsonb := '{}'::jsonb;
    v_copied text[] := '{}';
    v_leftover jsonb;
    v_error jsonb;
    v_state text;
    v_tab text;
    v_con text;
    v_msg text;
BEGIN
    p_dry_run := coalesce(p_dry_run, true);
    IF p_from IS NULL OR p_into IS NULL OR p_from = p_into THEN
        RAISE EXCEPTION USING ERRCODE = 'MTSAM',
            MESSAGE = 'merge_club: source and target must be two different clubs';
    END IF;
    SELECT * INTO v_from FROM public.clubs WHERE id = p_from FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'MTNF1', MESSAGE = format('merge_club: club %s does not exist', p_from);
    END IF;
    SELECT * INTO v_into FROM public.clubs WHERE id = p_into FOR KEY SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'MTNF1', MESSAGE = format('merge_club: club %s does not exist', p_into);
    END IF;

    -- teams_name_club_league_unique: the same team in both clubs is a team
    -- duplicate, and merge_team is the tool for it.
    SELECT coalesce(jsonb_agg(jsonb_build_object(
               'kind', 'team_name_conflict', 'team_id', s.id, 'conflicts_with', t.id,
               'detail', 'both clubs have a team with this name in this league; merge the teams first')), '[]'::jsonb)
      INTO v_blockers
      FROM public.teams s
      JOIN public.teams t
        ON t.club_id = p_into
       AND t.name = s.name
       AND t.league_id IS NOT DISTINCT FROM s.league_id
     WHERE s.club_id = p_from;

    -- A dropped channel takes its members and deliveries with it.
    SELECT v_blockers || coalesce(jsonb_agg(jsonb_build_object(
               'kind', 'channel_conflict', 'channel_id', s.id, 'conflicts_with', t.id,
               'detail', 'both clubs have this notification channel; merge or remove one first')), '[]'::jsonb)
      INTO v_blockers
      FROM public.notification_channels s
      JOIN public.notification_channels t
        ON t.club_id = p_into
       AND t.scope_type = s.scope_type
       AND t.team_id IS NOT DISTINCT FROM s.team_id
       AND t.age_group_id IS NOT DISTINCT FROM s.age_group_id
       AND t.audience = s.audience
       AND t.platform = s.platform
       AND t.destination = s.destination
     WHERE s.club_id = p_from;

    SELECT v_blockers || coalesce(jsonb_agg(jsonb_build_object(
               'kind', 'club_channel_conflict', 'channel_id', s.id, 'conflicts_with', t.id,
               'detail', 'both clubs have a club channel on this platform; remove one first')), '[]'::jsonb)
      INTO v_blockers
      FROM public.club_notification_channels s
      JOIN public.club_notification_channels t
        ON t.club_id = p_into
       AND t.platform = s.platform
     WHERE s.club_id = p_from;

    IF jsonb_array_length(v_blockers) > 0 AND NOT p_dry_run THEN
        RAISE EXCEPTION USING ERRCODE = 'MTBLK',
            MESSAGE = format('merge_club: %s blocker(s), run a dry run to list them', jsonb_array_length(v_blockers));
    END IF;

    BEGIN
        -- Channel collisions are blockers above, so these are plain moves.
        v_tables := v_tables
            || jsonb_build_object('teams',
                   public._merge_rows('public.teams', 'club_id', p_from, p_into))
            || jsonb_build_object('user_profiles',
                   public._merge_rows('public.user_profiles', 'club_id', p_from, p_into))
            || jsonb_build_object('invitations',
                   public._merge_rows('public.invitations', 'club_id', p_from, p_into))
            || jsonb_build_object('match_events',
                   public._merge_rows('public.match_events', 'chat_club_id', p_from, p_into))
            || jsonb_build_object('notification_channels',
                   public._merge_rows('public.notification_channels', 'club_id', p_from, p_into))
            || jsonb_build_object('club_notification_channels',
                   public._merge_rows('public.club_notification_channels', 'club_id', p_from, p_into));

        -- The target keeps whatever it already has; the source only fills
        -- gaps. Stock colours are the column defaults, i.e. never chosen.
        IF nullif(btrim(v_into.logo_url), '') IS NULL AND nullif(btrim(v_from.logo_url), '') IS NOT NULL THEN
            v_copied := v_copied || 'logo_url'::text;
        END IF;
        IF (v_into.primary_color IS NULL OR v_into.primary_color = '#6B7280')
           AND v_from.primary_color IS NOT NULL AND v_from.primary_color <> '#6B7280' THEN
            v_copied := v_copied || 'primary_color'::text;
        END IF;
        IF (v_into.secondary_color IS NULL OR v_into.secondary_color = '#374151')
           AND v_from.secondary_color IS NOT NULL AND v_from.secondary_color <> '#374151' THEN
            v_copied := v_copied || 'secondary_color'::text;
        END IF;
        IF nullif(btrim(v_into.city), '') IS NULL AND nullif(btrim(v_from.city), '') IS NOT NULL THEN
            v_copied := v_copied || 'city'::text;
        END IF;
        IF nullif(btrim(v_into.website), '') IS NULL AND nullif(btrim(v_from.website), '') IS NOT NULL THEN
            v_copied := v_copied || 'website'::text;
        END IF;

        UPDATE public.clubs
           SET logo_url        = CASE WHEN 'logo_url' = ANY (v_copied) THEN v_from.logo_url ELSE logo_url END,
               primary_color   = CASE WHEN 'primary_color' = ANY (v_copied) THEN v_from.primary_color ELSE primary_color END,
               secondary_color = CASE WHEN 'secondary_color' = ANY (v_copied) THEN v_from.secondary_color ELSE secondary_color END,
               city            = CASE WHEN 'city' = ANY (v_copied) THEN v_from.city ELSE city END,
               website         = CASE WHEN 'website' = ANY (v_copied) THEN v_from.website ELSE website END
         WHERE id = p_into AND cardinality(v_copied) > 0;

        -- Safety net: a table referencing clubs that this function does not
        -- move would lose its rows to ON DELETE CASCADE / SET NULL.
        v_leftover := public._merge_leftover_refs('public.clubs', p_from);
        IF jsonb_array_length(v_leftover) > 0 THEN
            IF NOT p_dry_run THEN
                RAISE EXCEPTION USING ERRCODE = 'MTBLK',
                    MESSAGE = format('merge_club: rows in %s still reference club %s',
                                     (SELECT string_agg(e->>'table', ', ') FROM jsonb_array_elements(v_leftover) e), p_from);
            END IF;
            SELECT v_blockers || jsonb_agg(e || jsonb_build_object(
                       'kind', 'unlisted_reference',
                       'detail', 'this table references the club and the merge does not move it'))
              INTO v_blockers
              FROM jsonb_array_elements(v_leftover) e;
        ELSE
            DELETE FROM public.clubs WHERE id = p_from;
        END IF;

        IF p_dry_run THEN
            RAISE EXCEPTION USING ERRCODE = 'MTDRY', MESSAGE = 'dry run';
        END IF;
    EXCEPTION
        WHEN SQLSTATE 'MTDRY' THEN
            NULL;
        WHEN OTHERS THEN
            IF NOT p_dry_run THEN
                RAISE;
            END IF;
            GET STACKED DIAGNOSTICS v_state = RETURNED_SQLSTATE, v_tab = TABLE_NAME,
                                    v_con = CONSTRAINT_NAME, v_msg = MESSAGE_TEXT;
            v_error := jsonb_strip_nulls(jsonb_build_object(
                'sqlstate', v_state, 'table', nullif(v_tab, ''), 'constraint', nullif(v_con, '')));
            RAISE WARNING 'merge_club(%, %) dry run stopped early: % (SQLSTATE %)', p_from, p_into, v_msg, v_state;
    END;

    RETURN jsonb_build_object(
        'from', jsonb_build_object('id', v_from.id, 'name', v_from.name),
        'into', jsonb_build_object('id', v_into.id, 'name', v_into.name),
        'dry_run', p_dry_run,
        'tables', v_tables,
        'copied', to_jsonb(v_copied),
        'blockers', v_blockers,
        'error', v_error,
        'complete', v_error IS NULL
    );
END;
$$;

COMMENT ON FUNCTION public.merge_club(integer, integer, boolean) IS
    'SB-1822: repoint every row referencing club p_from to p_into, fill p_into''s empty logo/colours/city/website from p_from, delete p_from. Dry run by default.';

REVOKE ALL ON FUNCTION public.merge_club(integer, integer, boolean) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.merge_club(integer, integer, boolean) TO service_role;
