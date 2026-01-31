-- =============================================================================
-- Consolidated baseline schema for Missing Table
-- =============================================================================
-- Generated: 2026-01-30
-- Source: pg_dump of local Supabase database (port 54332) after all 43 migrations
--
-- This single file replaces the previous 43 individual migration files.
-- It captures the complete public schema including:
--   - Tables, types, sequences
--   - Functions and triggers
--   - Indexes and constraints
--   - Row Level Security (RLS) policies
--
-- To add new schema changes, create a new timestamped migration file alongside
-- this baseline (e.g., 20260201000000_add_foo.sql).
-- =============================================================================

--
-- PostgreSQL database dump
--


-- Dumped from database version 17.4
-- Dumped by pg_dump version 18.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--



--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: invite_request_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.invite_request_status AS ENUM (
    'pending',
    'approved',
    'rejected'
);


--
-- Name: match_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.match_status AS ENUM (
    'scheduled',
    'completed',
    'postponed',
    'cancelled',
    'tbd',
    'live'
);


--
-- Name: add_schema_version(character varying, character varying, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.add_schema_version(p_version character varying, p_migration_name character varying, p_description text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    INSERT INTO schema_version (version, migration_name, description)
    VALUES (p_version, p_migration_name, p_description);
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: player_team_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.player_team_history (
    id integer NOT NULL,
    player_id uuid NOT NULL,
    team_id integer NOT NULL,
    season_id integer NOT NULL,
    age_group_id integer,
    league_id integer,
    division_id integer,
    jersey_number integer,
    positions text[],
    is_current boolean DEFAULT false,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: create_player_history_entry(uuid, integer, integer, integer, text[]); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.create_player_history_entry(p_player_id uuid, p_team_id integer, p_season_id integer, p_jersey_number integer DEFAULT NULL::integer, p_positions text[] DEFAULT NULL::text[]) RETURNS public.player_team_history
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_team RECORD;
    v_result player_team_history;
BEGIN
    -- Get team details
    SELECT age_group_id, league_id, division_id INTO v_team
    FROM teams WHERE id = p_team_id;

    -- Mark any existing current entries as not current
    UPDATE player_team_history
    SET is_current = false, updated_at = NOW()
    WHERE player_id = p_player_id AND is_current = true;

    -- Insert new history entry
    INSERT INTO player_team_history (
        player_id, team_id, season_id,
        age_group_id, league_id, division_id,
        jersey_number, positions, is_current
    ) VALUES (
        p_player_id, p_team_id, p_season_id,
        v_team.age_group_id, v_team.league_id, v_team.division_id,
        p_jersey_number, p_positions, true
    )
    ON CONFLICT (player_id, team_id, season_id)
    DO UPDATE SET
        jersey_number = COALESCE(EXCLUDED.jersey_number, player_team_history.jersey_number),
        positions = COALESCE(EXCLUDED.positions, player_team_history.positions),
        is_current = true,
        updated_at = NOW()
    RETURNING * INTO v_result;

    RETURN v_result;
END;
$$;


--
-- Name: get_club_league_teams(integer, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_club_league_teams(p_club_id integer, p_league_id integer) RETURNS TABLE(id integer, name character varying, club_id integer, league_id integer, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id,
        t.name,
        t.club_id,
        t.league_id,
        t.created_at
    FROM teams t
    WHERE t.club_id = p_club_id
      AND t.league_id = p_league_id
    ORDER BY t.name;
END;
$$;


--
-- Name: FUNCTION get_club_league_teams(p_club_id integer, p_league_id integer); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.get_club_league_teams(p_club_id integer, p_league_id integer) IS 'Returns teams for a club in a specific league';


--
-- Name: get_club_teams(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_club_teams(p_club_id integer) RETURNS TABLE(id integer, name character varying, club_id integer, league_id integer, league_name character varying, created_at timestamp with time zone)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id,
        t.name,
        t.club_id,
        t.league_id,
        l.name AS league_name,
        t.created_at
    FROM teams t
    JOIN leagues l ON t.league_id = l.id
    WHERE t.club_id = p_club_id
    ORDER BY l.name, t.name;
END;
$$;


--
-- Name: FUNCTION get_club_teams(p_club_id integer); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.get_club_teams(p_club_id integer) IS 'Returns all teams for a club across all leagues';


--
-- Name: get_schema_version(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_schema_version() RETURNS TABLE(version character varying, applied_at timestamp with time zone, description text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    RETURN QUERY
    SELECT sv.version, sv.applied_at, sv.description
    FROM schema_version sv
    ORDER BY sv.applied_at DESC
    LIMIT 1;
END;
$$;


--
-- Name: get_team_game_counts(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_team_game_counts() RETURNS TABLE(team_id integer, game_count bigint)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN QUERY
    WITH home_games AS (
        SELECT home_team_id AS tid, COUNT(*) AS count
        FROM matches
        GROUP BY home_team_id
    ),
    away_games AS (
        SELECT away_team_id AS tid, COUNT(*) AS count
        FROM matches
        GROUP BY away_team_id
    ),
    combined AS (
        SELECT tid, count FROM home_games
        UNION ALL
        SELECT tid, count FROM away_games
    )
    SELECT
        combined.tid::INT AS team_id,
        SUM(combined.count) AS game_count
    FROM combined
    GROUP BY combined.tid;
END;
$$;


--
-- Name: FUNCTION get_team_game_counts(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.get_team_game_counts() IS 'Efficiently counts total games (home + away) for all teams.
Used by Admin Teams page to avoid fetching all 100k+ games to the client.
Performance: Scans matches table once and aggregates in database.';


--
-- Name: is_admin(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.is_admin() RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM user_profiles
        WHERE id = auth.uid()
        AND role = 'admin'
    );
END;
$$;


--
-- Name: is_team_manager(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.is_team_manager() RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM user_profiles
        WHERE id = auth.uid()
        AND role = 'team_manager'
    );
END;
$$;


--
-- Name: manages_team(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.manages_team(team_id_param integer) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM team_manager_assignments
        WHERE user_id = auth.uid()
        AND team_id = team_id_param
    );
END;
$$;


--
-- Name: reset_all_sequences(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.reset_all_sequences() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    seq_record RECORD;
    sequences_reset INTEGER := 0;
    max_value BIGINT;
    current_value BIGINT;
BEGIN
    -- Loop through all columns that use sequences (SERIAL/BIGSERIAL)
    FOR seq_record IN
        SELECT
            c.table_name::text,
            c.column_name::text,
            pg_get_serial_sequence(c.table_name::text, c.column_name::text) as sequence_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
        AND c.column_default LIKE 'nextval%'
        AND pg_get_serial_sequence(c.table_name::text, c.column_name::text) IS NOT NULL
        ORDER BY c.table_name, c.column_name
    LOOP
        -- Get the maximum ID value from the table
        EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I',
            seq_record.column_name,
            seq_record.table_name)
        INTO max_value;

        -- Get the current sequence value
        EXECUTE format('SELECT last_value FROM %s', seq_record.sequence_name)
        INTO current_value;

        -- Only reset if the max value is greater than current sequence value
        IF max_value > current_value THEN
            -- Reset the sequence to max_value + 1
            EXECUTE format('SELECT setval(%L, %s, true)',
                seq_record.sequence_name,
                max_value
            );

            sequences_reset := sequences_reset + 1;

            RAISE NOTICE 'Reset sequence for %.%: % → %',
                seq_record.table_name,
                seq_record.column_name,
                current_value,
                max_value;
        ELSE
            RAISE NOTICE 'Skipped %.%: sequence (%s) already ahead of max (%s)',
                seq_record.table_name,
                seq_record.column_name,
                current_value,
                max_value;
        END IF;
    END LOOP;

    RETURN sequences_reset;
END;
$$;


--
-- Name: FUNCTION reset_all_sequences(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.reset_all_sequences() IS 'Resets all PostgreSQL sequences to match the maximum ID values in their tables.
Run this after restoring data from backups to prevent duplicate key violations.';


--
-- Name: set_match_event_message_expiry(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_match_event_message_expiry() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    -- Only set expiry for message events (goals and status_change are permanent)
    IF NEW.event_type = 'message' THEN
        NEW.expires_at := NEW.created_at + INTERVAL '10 days';
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: update_invite_requests_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_invite_requests_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_match_lineups_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_match_lineups_updated_at() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_player_match_stats_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_player_match_stats_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_players_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_players_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


--
-- Name: age_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.age_groups (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: age_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.age_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: age_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.age_groups_id_seq OWNED BY public.age_groups.id;


--
-- Name: clubs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clubs (
    id integer NOT NULL,
    name character varying(200) NOT NULL,
    city character varying(100),
    website character varying(255),
    description text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    logo_url text,
    primary_color text DEFAULT '#6B7280'::text,
    secondary_color text DEFAULT '#374151'::text,
    pro_academy boolean DEFAULT false
);


--
-- Name: TABLE clubs; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.clubs IS 'Organizations that field teams in one or more leagues (e.g., IFA, New England Revolution)';


--
-- Name: COLUMN clubs.logo_url; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.clubs.logo_url IS 'URL to club logo image stored in Supabase Storage (club-logos bucket)';


--
-- Name: COLUMN clubs.primary_color; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.clubs.primary_color IS 'Primary brand color as hex code (e.g., #FFD700 for gold)';


--
-- Name: COLUMN clubs.secondary_color; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.clubs.secondary_color IS 'Secondary brand color as hex code (e.g., #1E3A5F for dark blue)';


--
-- Name: COLUMN clubs.pro_academy; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.clubs.pro_academy IS 'Indicates if this club is a professional academy';


--
-- Name: clubs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clubs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clubs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clubs_id_seq OWNED BY public.clubs.id;


--
-- Name: divisions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.divisions (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    league_id integer NOT NULL
);


--
-- Name: divisions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.divisions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: divisions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.divisions_id_seq OWNED BY public.divisions.id;


--
-- Name: invitations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invitations (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    invite_code character varying(12) NOT NULL,
    invited_by_user_id uuid,
    invite_type character varying(50) NOT NULL,
    team_id integer,
    age_group_id integer,
    email character varying(255),
    status character varying(20) DEFAULT 'pending'::character varying,
    expires_at timestamp with time zone,
    used_at timestamp with time zone,
    used_by_user_id uuid,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    club_id integer,
    player_id integer,
    jersey_number integer,
    CONSTRAINT invitations_invite_type_check CHECK (((invite_type)::text = ANY ((ARRAY['club_manager'::character varying, 'club_fan'::character varying, 'team_manager'::character varying, 'team_player'::character varying, 'team_fan'::character varying])::text[]))),
    CONSTRAINT invitations_jersey_number_check CHECK (((jersey_number IS NULL) OR ((jersey_number >= 1) AND (jersey_number <= 99))))
);


--
-- Name: COLUMN invitations.club_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invitations.club_id IS 'Club ID for club_manager and club_fan invites';


--
-- Name: COLUMN invitations.player_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invitations.player_id IS 'Links to roster entry (for team_player invites) - user account linked on redemption';


--
-- Name: COLUMN invitations.jersey_number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invitations.jersey_number IS 'Jersey number for team_player invites - creates roster entry on redemption';


--
-- Name: invite_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invite_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    team character varying(255),
    reason text,
    status public.invite_request_status DEFAULT 'pending'::public.invite_request_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    admin_notes text
);


--
-- Name: TABLE invite_requests; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.invite_requests IS 'Stores invite requests from potential users wanting to join the platform';


--
-- Name: COLUMN invite_requests.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invite_requests.status IS 'Request status: pending, approved, or rejected';


--
-- Name: COLUMN invite_requests.reviewed_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invite_requests.reviewed_by IS 'Admin user who reviewed the request';


--
-- Name: COLUMN invite_requests.admin_notes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invite_requests.admin_notes IS 'Internal notes from admin about the request';


--
-- Name: leagues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.leagues (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: leagues_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.leagues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: leagues_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.leagues_id_seq OWNED BY public.leagues.id;


--
-- Name: match_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.match_events (
    id integer NOT NULL,
    match_id integer NOT NULL,
    event_type character varying(20) NOT NULL,
    team_id integer,
    player_name character varying(200),
    message text NOT NULL,
    created_by uuid,
    created_by_username character varying(100),
    is_deleted boolean DEFAULT false,
    deleted_by uuid,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    expires_at timestamp with time zone,
    match_minute integer,
    extra_time integer DEFAULT 0,
    player_id integer,
    CONSTRAINT match_events_event_type_check CHECK (((event_type)::text = ANY ((ARRAY['goal'::character varying, 'message'::character varying, 'status_change'::character varying])::text[])))
);


--
-- Name: TABLE match_events; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.match_events IS 'Activity stream for live matches: goals, chat messages, status changes';


--
-- Name: COLUMN match_events.event_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_events.event_type IS 'Type of event: goal, message, or status_change';


--
-- Name: COLUMN match_events.expires_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_events.expires_at IS 'Auto-set to 10 days from created_at for messages (cleanup target)';


--
-- Name: COLUMN match_events.match_minute; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_events.match_minute IS 'Minute when event occurred (e.g., 22 for 22nd minute)';


--
-- Name: COLUMN match_events.extra_time; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_events.extra_time IS 'Stoppage/injury time minutes (e.g., 5 for 90+5)';


--
-- Name: COLUMN match_events.player_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_events.player_id IS 'Links to roster entry for goal tracking - enables player stats aggregation';


--
-- Name: match_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.match_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: match_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.match_events_id_seq OWNED BY public.match_events.id;


--
-- Name: match_lineups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.match_lineups (
    id integer NOT NULL,
    match_id integer NOT NULL,
    team_id integer NOT NULL,
    formation_name character varying(20) DEFAULT '4-3-3'::character varying NOT NULL,
    positions jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by uuid,
    updated_by uuid
);


--
-- Name: TABLE match_lineups; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.match_lineups IS 'Team lineups for matches - stores formation and player-position assignments';


--
-- Name: COLUMN match_lineups.formation_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_lineups.formation_name IS 'Formation preset name (e.g., 4-3-3, 4-4-2, 3-5-2)';


--
-- Name: COLUMN match_lineups.positions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_lineups.positions IS 'JSONB array of {player_id, position} objects';


--
-- Name: match_lineups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.match_lineups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: match_lineups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.match_lineups_id_seq OWNED BY public.match_lineups.id;


--
-- Name: match_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.match_types (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: match_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.match_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: match_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.match_types_id_seq OWNED BY public.match_types.id;


--
-- Name: matches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.matches (
    id integer NOT NULL,
    match_date date NOT NULL,
    home_team_id integer NOT NULL,
    away_team_id integer NOT NULL,
    home_score integer,
    away_score integer,
    season_id integer NOT NULL,
    age_group_id integer NOT NULL,
    match_type_id integer NOT NULL,
    division_id integer,
    data_source character varying(50) DEFAULT 'manual'::character varying,
    last_scraped_at timestamp with time zone,
    score_locked boolean DEFAULT false,
    match_id character varying(255),
    match_status public.match_status DEFAULT 'scheduled'::public.match_status,
    created_by uuid,
    updated_by uuid,
    source character varying(50) DEFAULT 'manual'::character varying,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    kickoff_time timestamp with time zone,
    halftime_start timestamp with time zone,
    second_half_start timestamp with time zone,
    match_end_time timestamp with time zone,
    half_duration integer DEFAULT 45,
    scheduled_kickoff timestamp with time zone,
    CONSTRAINT matches_check CHECK ((home_team_id <> away_team_id))
);


--
-- Name: COLUMN matches.match_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.matches.match_id IS 'External match ID from match-scraper service (e.g., MLS match ID). This is the primary external identifier.';


--
-- Name: COLUMN matches.kickoff_time; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.matches.kickoff_time IS 'Timestamp when the match kicked off (1st half started)';


--
-- Name: COLUMN matches.halftime_start; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.matches.halftime_start IS 'Timestamp when halftime began';


--
-- Name: COLUMN matches.second_half_start; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.matches.second_half_start IS 'Timestamp when 2nd half kicked off';


--
-- Name: COLUMN matches.match_end_time; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.matches.match_end_time IS 'Timestamp when the match ended';


--
-- Name: COLUMN matches.half_duration; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.matches.half_duration IS 'Duration of each half in minutes (e.g., 45 for 90-min game, 40 for 80-min game)';


--
-- Name: COLUMN matches.scheduled_kickoff; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.matches.scheduled_kickoff IS 'Scheduled kickoff datetime in UTC. Different from kickoff_time which tracks when live match actually started.';


--
-- Name: matches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.matches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: matches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.matches_id_seq OWNED BY public.matches.id;


--
-- Name: player_match_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.player_match_stats (
    id integer NOT NULL,
    player_id integer NOT NULL,
    match_id integer NOT NULL,
    started boolean DEFAULT false,
    minutes_played integer DEFAULT 0,
    goals integer DEFAULT 0,
    assists integer DEFAULT 0,
    yellow_cards integer DEFAULT 0,
    red_cards integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT player_match_stats_assists_check CHECK ((assists >= 0)),
    CONSTRAINT player_match_stats_goals_check CHECK ((goals >= 0)),
    CONSTRAINT player_match_stats_minutes_played_check CHECK ((minutes_played >= 0)),
    CONSTRAINT player_match_stats_red_cards_check CHECK (((red_cards >= 0) AND (red_cards <= 1))),
    CONSTRAINT player_match_stats_yellow_cards_check CHECK (((yellow_cards >= 0) AND (yellow_cards <= 2)))
);


--
-- Name: TABLE player_match_stats; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.player_match_stats IS 'Per-match statistics for players';


--
-- Name: COLUMN player_match_stats.started; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.player_match_stats.started IS 'Whether player was in starting lineup';


--
-- Name: COLUMN player_match_stats.minutes_played; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.player_match_stats.minutes_played IS 'Total minutes played in match';


--
-- Name: COLUMN player_match_stats.goals; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.player_match_stats.goals IS 'Goals scored in match';


--
-- Name: player_match_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.player_match_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: player_match_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.player_match_stats_id_seq OWNED BY public.player_match_stats.id;


--
-- Name: player_team_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.player_team_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: player_team_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.player_team_history_id_seq OWNED BY public.player_team_history.id;


--
-- Name: players; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.players (
    id integer NOT NULL,
    team_id integer NOT NULL,
    season_id integer NOT NULL,
    jersey_number integer NOT NULL,
    first_name character varying(100),
    last_name character varying(100),
    user_profile_id uuid,
    positions text[],
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by uuid,
    CONSTRAINT players_jersey_number_check CHECK (((jersey_number >= 1) AND (jersey_number <= 99)))
);


--
-- Name: TABLE players; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.players IS 'Roster entries for teams - independent of MT accounts';


--
-- Name: COLUMN players.jersey_number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.players.jersey_number IS 'Jersey number (1-99), unique per team per season';


--
-- Name: COLUMN players.first_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.players.first_name IS 'Player first name (optional, for display when no account)';


--
-- Name: COLUMN players.last_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.players.last_name IS 'Player last name (optional, for display when no account)';


--
-- Name: COLUMN players.user_profile_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.players.user_profile_id IS 'Link to MT account (NULL if player has no account)';


--
-- Name: players_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.players_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: players_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.players_id_seq OWNED BY public.players.id;


--
-- Name: schema_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_version (
    id integer NOT NULL,
    version character varying(20) NOT NULL,
    migration_name character varying(255) NOT NULL,
    description text,
    applied_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    applied_by character varying(100) DEFAULT CURRENT_USER
);


--
-- Name: schema_version_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.schema_version_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: schema_version_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.schema_version_id_seq OWNED BY public.schema_version.id;


--
-- Name: seasons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seasons (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: seasons_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seasons_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: seasons_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.seasons_id_seq OWNED BY public.seasons.id;


--
-- Name: service_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.service_accounts (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    service_name character varying(100) NOT NULL,
    permissions text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    is_active boolean DEFAULT true
);


--
-- Name: team_manager_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_manager_assignments (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    team_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: team_manager_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.team_manager_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: team_manager_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.team_manager_assignments_id_seq OWNED BY public.team_manager_assignments.id;


--
-- Name: team_mappings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_mappings (
    id integer NOT NULL,
    team_id integer NOT NULL,
    age_group_id integer NOT NULL,
    division_id integer,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: team_mappings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.team_mappings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: team_mappings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.team_mappings_id_seq OWNED BY public.team_mappings.id;


--
-- Name: team_match_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_match_types (
    id integer NOT NULL,
    team_id integer NOT NULL,
    match_type_id integer NOT NULL,
    age_group_id integer NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: team_match_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.team_match_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: team_match_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.team_match_types_id_seq OWNED BY public.team_match_types.id;


--
-- Name: teams; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teams (
    id integer NOT NULL,
    name character varying(200) NOT NULL,
    city character varying(100),
    academy_team boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    club_id integer,
    league_id integer,
    division_id integer,
    age_group_id integer
);


--
-- Name: COLUMN teams.club_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.teams.club_id IS 'The club/organization this team belongs to (e.g., IFA). NULL for independent teams.';


--
-- Name: COLUMN teams.league_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.teams.league_id IS 'League ID - required for league teams, optional for guest/tournament teams';


--
-- Name: COLUMN teams.division_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.teams.division_id IS 'Division ID - required for league teams, optional for guest/tournament teams';


--
-- Name: COLUMN teams.age_group_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.teams.age_group_id IS 'The age group this team competes in (e.g., U14, U15). Each team in youth soccer is age-group specific.';


--
-- Name: teams_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.teams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: teams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.teams_id_seq OWNED BY public.teams.id;


--
-- Name: teams_with_details; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.teams_with_details WITH (security_invoker='true') AS
 SELECT t.id,
    t.name AS team_name,
    t.city,
    t.academy_team,
    c.id AS club_id,
    c.name AS club_name,
    c.city AS club_city,
    l.id AS league_id,
    l.name AS league_name,
    l.description AS league_description,
    t.created_at,
    t.updated_at
   FROM ((public.teams t
     LEFT JOIN public.clubs c ON ((t.club_id = c.id)))
     JOIN public.leagues l ON ((t.league_id = l.id)));


--
-- Name: VIEW teams_with_details; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.teams_with_details IS 'Convenient view showing teams with their club and league information. Uses SECURITY INVOKER to respect RLS.';


--
-- Name: teams_with_league_badges; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.teams_with_league_badges AS
 SELECT t.id,
    t.name,
    t.club_id,
    t.league_id,
    l.name AS league_name,
    array_remove(array_agg(DISTINCT dl.name), NULL::character varying) AS mapping_league_names
   FROM ((((public.teams t
     LEFT JOIN public.leagues l ON ((l.id = t.league_id)))
     LEFT JOIN public.team_mappings tm ON ((tm.team_id = t.id)))
     LEFT JOIN public.divisions d ON ((d.id = tm.division_id)))
     LEFT JOIN public.leagues dl ON ((dl.id = d.league_id)))
  GROUP BY t.id, t.name, t.club_id, t.league_id, l.name;


--
-- Name: user_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_profiles (
    id uuid NOT NULL,
    role character varying(50) DEFAULT 'user'::character varying NOT NULL,
    team_id integer,
    display_name character varying(200),
    username character varying(100),
    email character varying(255),
    phone_number character varying(20),
    player_number character varying(10),
    positions text DEFAULT '[]'::text,
    assigned_age_group_id integer,
    invited_via_code character varying(50),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    club_id integer,
    photo_1_url text,
    photo_2_url text,
    photo_3_url text,
    profile_photo_slot integer,
    overlay_style character varying(20) DEFAULT 'badge'::character varying,
    primary_color character varying(7) DEFAULT '#3B82F6'::character varying,
    text_color character varying(7) DEFAULT '#FFFFFF'::character varying,
    accent_color character varying(7) DEFAULT '#1D4ED8'::character varying,
    instagram_handle character varying(30),
    snapchat_handle character varying(30),
    tiktok_handle character varying(30),
    first_name character varying(100),
    last_name character varying(100),
    hometown character varying(200),
    auth_provider character varying(50) DEFAULT 'password'::character varying,
    profile_photo_url text,
    CONSTRAINT user_profiles_overlay_style_check CHECK (((overlay_style)::text = ANY ((ARRAY['badge'::character varying, 'jersey'::character varying, 'caption'::character varying, 'none'::character varying])::text[]))),
    CONSTRAINT user_profiles_profile_photo_slot_check CHECK (((profile_photo_slot IS NULL) OR (profile_photo_slot = ANY (ARRAY[1, 2, 3])))),
    CONSTRAINT user_profiles_role_check CHECK (((role)::text = ANY ((ARRAY['admin'::character varying, 'club_manager'::character varying, 'club-fan'::character varying, 'club_fan'::character varying, 'team-manager'::character varying, 'team_manager'::character varying, 'team-player'::character varying, 'team_player'::character varying, 'team-fan'::character varying, 'team_fan'::character varying])::text[])))
);


--
-- Name: COLUMN user_profiles.role; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.role IS 'User role: admin > club_manager > team-manager > team-player > club-fan/team-fan. Club fans can view all teams in their assigned club.';


--
-- Name: COLUMN user_profiles.display_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.display_name IS 'Creative display name for fun - can include emojis, numbers, nicknames';


--
-- Name: COLUMN user_profiles.club_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.club_id IS 'Club ID derived from the user''s team, or set directly for club-level roles. Users with a team_id will typically also have club_id set to the team''s parent club.';


--
-- Name: COLUMN user_profiles.instagram_handle; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.instagram_handle IS 'Instagram username (without @)';


--
-- Name: COLUMN user_profiles.snapchat_handle; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.snapchat_handle IS 'Snapchat username';


--
-- Name: COLUMN user_profiles.tiktok_handle; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.tiktok_handle IS 'TikTok username (without @)';


--
-- Name: COLUMN user_profiles.first_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.first_name IS 'Player real first name';


--
-- Name: COLUMN user_profiles.last_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.last_name IS 'Player real last name';


--
-- Name: COLUMN user_profiles.hometown; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.hometown IS 'Player hometown/city';


--
-- Name: COLUMN user_profiles.auth_provider; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.auth_provider IS 'Authentication provider: password, google, github, etc.';


--
-- Name: COLUMN user_profiles.profile_photo_url; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.user_profiles.profile_photo_url IS 'URL to user profile photo (from OAuth provider or uploaded)';


--
-- Name: age_groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.age_groups ALTER COLUMN id SET DEFAULT nextval('public.age_groups_id_seq'::regclass);


--
-- Name: clubs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clubs ALTER COLUMN id SET DEFAULT nextval('public.clubs_id_seq'::regclass);


--
-- Name: divisions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.divisions ALTER COLUMN id SET DEFAULT nextval('public.divisions_id_seq'::regclass);


--
-- Name: leagues id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leagues ALTER COLUMN id SET DEFAULT nextval('public.leagues_id_seq'::regclass);


--
-- Name: match_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_events ALTER COLUMN id SET DEFAULT nextval('public.match_events_id_seq'::regclass);


--
-- Name: match_lineups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_lineups ALTER COLUMN id SET DEFAULT nextval('public.match_lineups_id_seq'::regclass);


--
-- Name: match_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_types ALTER COLUMN id SET DEFAULT nextval('public.match_types_id_seq'::regclass);


--
-- Name: matches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches ALTER COLUMN id SET DEFAULT nextval('public.matches_id_seq'::regclass);


--
-- Name: player_match_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_match_stats ALTER COLUMN id SET DEFAULT nextval('public.player_match_stats_id_seq'::regclass);


--
-- Name: player_team_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_team_history ALTER COLUMN id SET DEFAULT nextval('public.player_team_history_id_seq'::regclass);


--
-- Name: players id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.players ALTER COLUMN id SET DEFAULT nextval('public.players_id_seq'::regclass);


--
-- Name: schema_version id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_version ALTER COLUMN id SET DEFAULT nextval('public.schema_version_id_seq'::regclass);


--
-- Name: seasons id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seasons ALTER COLUMN id SET DEFAULT nextval('public.seasons_id_seq'::regclass);


--
-- Name: team_manager_assignments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_manager_assignments ALTER COLUMN id SET DEFAULT nextval('public.team_manager_assignments_id_seq'::regclass);


--
-- Name: team_mappings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_mappings ALTER COLUMN id SET DEFAULT nextval('public.team_mappings_id_seq'::regclass);


--
-- Name: team_match_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_match_types ALTER COLUMN id SET DEFAULT nextval('public.team_match_types_id_seq'::regclass);


--
-- Name: teams id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams ALTER COLUMN id SET DEFAULT nextval('public.teams_id_seq'::regclass);


--
-- Name: age_groups age_groups_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.age_groups
    ADD CONSTRAINT age_groups_name_key UNIQUE (name);


--
-- Name: age_groups age_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.age_groups
    ADD CONSTRAINT age_groups_pkey PRIMARY KEY (id);


--
-- Name: clubs clubs_name_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clubs
    ADD CONSTRAINT clubs_name_unique UNIQUE (name);


--
-- Name: clubs clubs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clubs
    ADD CONSTRAINT clubs_pkey PRIMARY KEY (id);


--
-- Name: divisions divisions_name_league_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.divisions
    ADD CONSTRAINT divisions_name_league_id_key UNIQUE (name, league_id);


--
-- Name: divisions divisions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.divisions
    ADD CONSTRAINT divisions_pkey PRIMARY KEY (id);


--
-- Name: invitations invitations_invite_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitations
    ADD CONSTRAINT invitations_invite_code_key UNIQUE (invite_code);


--
-- Name: invitations invitations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitations
    ADD CONSTRAINT invitations_pkey PRIMARY KEY (id);


--
-- Name: invite_requests invite_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invite_requests
    ADD CONSTRAINT invite_requests_pkey PRIMARY KEY (id);


--
-- Name: leagues leagues_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leagues
    ADD CONSTRAINT leagues_name_key UNIQUE (name);


--
-- Name: leagues leagues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.leagues
    ADD CONSTRAINT leagues_pkey PRIMARY KEY (id);


--
-- Name: match_events match_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_events
    ADD CONSTRAINT match_events_pkey PRIMARY KEY (id);


--
-- Name: match_lineups match_lineups_match_id_team_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_lineups
    ADD CONSTRAINT match_lineups_match_id_team_id_key UNIQUE (match_id, team_id);


--
-- Name: match_lineups match_lineups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_lineups
    ADD CONSTRAINT match_lineups_pkey PRIMARY KEY (id);


--
-- Name: match_types match_types_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_types
    ADD CONSTRAINT match_types_name_key UNIQUE (name);


--
-- Name: match_types match_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_types
    ADD CONSTRAINT match_types_pkey PRIMARY KEY (id);


--
-- Name: matches matches_match_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_match_id_key UNIQUE (match_id);


--
-- Name: matches matches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_pkey PRIMARY KEY (id);


--
-- Name: player_match_stats player_match_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_match_stats
    ADD CONSTRAINT player_match_stats_pkey PRIMARY KEY (id);


--
-- Name: player_match_stats player_match_stats_player_id_match_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_match_stats
    ADD CONSTRAINT player_match_stats_player_id_match_id_key UNIQUE (player_id, match_id);


--
-- Name: player_team_history player_team_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_team_history
    ADD CONSTRAINT player_team_history_pkey PRIMARY KEY (id);


--
-- Name: player_team_history player_team_history_player_id_team_id_season_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_team_history
    ADD CONSTRAINT player_team_history_player_id_team_id_season_id_key UNIQUE (player_id, team_id, season_id);


--
-- Name: players players_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.players
    ADD CONSTRAINT players_pkey PRIMARY KEY (id);


--
-- Name: players players_team_id_season_id_jersey_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.players
    ADD CONSTRAINT players_team_id_season_id_jersey_number_key UNIQUE (team_id, season_id, jersey_number);


--
-- Name: schema_version schema_version_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_version
    ADD CONSTRAINT schema_version_pkey PRIMARY KEY (id);


--
-- Name: seasons seasons_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seasons
    ADD CONSTRAINT seasons_name_key UNIQUE (name);


--
-- Name: seasons seasons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seasons
    ADD CONSTRAINT seasons_pkey PRIMARY KEY (id);


--
-- Name: service_accounts service_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_accounts
    ADD CONSTRAINT service_accounts_pkey PRIMARY KEY (id);


--
-- Name: service_accounts service_accounts_service_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.service_accounts
    ADD CONSTRAINT service_accounts_service_name_key UNIQUE (service_name);


--
-- Name: team_manager_assignments team_manager_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_manager_assignments
    ADD CONSTRAINT team_manager_assignments_pkey PRIMARY KEY (id);


--
-- Name: team_manager_assignments team_manager_assignments_user_id_team_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_manager_assignments
    ADD CONSTRAINT team_manager_assignments_user_id_team_id_key UNIQUE (user_id, team_id);


--
-- Name: team_mappings team_mappings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_mappings
    ADD CONSTRAINT team_mappings_pkey PRIMARY KEY (id);


--
-- Name: team_mappings team_mappings_team_age_group_division_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_mappings
    ADD CONSTRAINT team_mappings_team_age_group_division_unique UNIQUE (team_id, age_group_id, division_id);


--
-- Name: CONSTRAINT team_mappings_team_age_group_division_unique ON team_mappings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON CONSTRAINT team_mappings_team_age_group_division_unique ON public.team_mappings IS 'Teams can participate in multiple divisions per age group (e.g., MLS NEXT and Futsal)';


--
-- Name: team_mappings team_mappings_team_id_age_group_id_division_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_mappings
    ADD CONSTRAINT team_mappings_team_id_age_group_id_division_id_key UNIQUE (team_id, age_group_id, division_id);


--
-- Name: team_match_types team_match_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_match_types
    ADD CONSTRAINT team_match_types_pkey PRIMARY KEY (id);


--
-- Name: team_match_types team_match_types_team_id_match_type_id_age_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_match_types
    ADD CONSTRAINT team_match_types_team_id_match_type_id_age_group_id_key UNIQUE (team_id, match_type_id, age_group_id);


--
-- Name: teams teams_name_club_league_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_name_club_league_unique UNIQUE (name, club_id, league_id);


--
-- Name: teams teams_name_division_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_name_division_unique UNIQUE (name, division_id);


--
-- Name: CONSTRAINT teams_name_division_unique ON teams; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON CONSTRAINT teams_name_division_unique ON public.teams IS 'Team names must be unique within a division. Teams in different divisions can have the same name.';


--
-- Name: teams teams_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_pkey PRIMARY KEY (id);


--
-- Name: matches unique_manual_match; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT unique_manual_match UNIQUE (home_team_id, away_team_id, match_date, season_id, age_group_id, match_type_id, division_id);


--
-- Name: user_profiles user_profiles_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_email_key UNIQUE (email);


--
-- Name: user_profiles user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_pkey PRIMARY KEY (id);


--
-- Name: user_profiles user_profiles_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_username_key UNIQUE (username);


--
-- Name: idx_clubs_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clubs_is_active ON public.clubs USING btree (is_active);


--
-- Name: idx_clubs_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clubs_name ON public.clubs USING btree (name);


--
-- Name: idx_divisions_league_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_divisions_league_id ON public.divisions USING btree (league_id);


--
-- Name: idx_invitations_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invitations_player ON public.invitations USING btree (player_id) WHERE (player_id IS NOT NULL);


--
-- Name: idx_invite_requests_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invite_requests_created_at ON public.invite_requests USING btree (created_at DESC);


--
-- Name: idx_invite_requests_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invite_requests_email ON public.invite_requests USING btree (email);


--
-- Name: idx_invite_requests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invite_requests_status ON public.invite_requests USING btree (status);


--
-- Name: idx_leagues_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_leagues_name ON public.leagues USING btree (name);


--
-- Name: idx_match_events_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_match_events_created_at ON public.match_events USING btree (created_at DESC);


--
-- Name: idx_match_events_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_match_events_expires ON public.match_events USING btree (expires_at) WHERE ((expires_at IS NOT NULL) AND (is_deleted = false));


--
-- Name: idx_match_events_match_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_match_events_match_id ON public.match_events USING btree (match_id);


--
-- Name: idx_match_events_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_match_events_player ON public.match_events USING btree (player_id) WHERE (player_id IS NOT NULL);


--
-- Name: idx_match_events_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_match_events_type ON public.match_events USING btree (event_type);


--
-- Name: idx_match_lineups_match_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_match_lineups_match_id ON public.match_lineups USING btree (match_id);


--
-- Name: idx_matches_age_group; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matches_age_group ON public.matches USING btree (age_group_id);


--
-- Name: idx_matches_away_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matches_away_team ON public.matches USING btree (away_team_id);


--
-- Name: idx_matches_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matches_date ON public.matches USING btree (match_date);


--
-- Name: idx_matches_division; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matches_division ON public.matches USING btree (division_id);


--
-- Name: idx_matches_home_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matches_home_team ON public.matches USING btree (home_team_id);


--
-- Name: idx_matches_live_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matches_live_status ON public.matches USING btree (match_status) WHERE (match_status = 'live'::public.match_status);


--
-- Name: idx_matches_match_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matches_match_status ON public.matches USING btree (match_status);


--
-- Name: idx_matches_match_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matches_match_type ON public.matches USING btree (match_type_id);


--
-- Name: idx_matches_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matches_season ON public.matches USING btree (season_id);


--
-- Name: idx_player_match_stats_match; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_match_stats_match ON public.player_match_stats USING btree (match_id);


--
-- Name: idx_player_match_stats_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_match_stats_player ON public.player_match_stats USING btree (player_id);


--
-- Name: idx_player_team_history_current; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_team_history_current ON public.player_team_history USING btree (player_id, is_current) WHERE (is_current = true);


--
-- Name: idx_player_team_history_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_team_history_player ON public.player_team_history USING btree (player_id);


--
-- Name: idx_player_team_history_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_team_history_season ON public.player_team_history USING btree (season_id);


--
-- Name: idx_players_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_players_active ON public.players USING btree (team_id, is_active) WHERE (is_active = true);


--
-- Name: idx_players_team_season; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_players_team_season ON public.players USING btree (team_id, season_id);


--
-- Name: idx_players_user_profile; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_players_user_profile ON public.players USING btree (user_profile_id) WHERE (user_profile_id IS NOT NULL);


--
-- Name: idx_team_manager_assignments_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_manager_assignments_team ON public.team_manager_assignments USING btree (team_id);


--
-- Name: idx_team_manager_assignments_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_manager_assignments_user ON public.team_manager_assignments USING btree (user_id);


--
-- Name: idx_team_mappings_age_group; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_mappings_age_group ON public.team_mappings USING btree (age_group_id);


--
-- Name: idx_team_mappings_division; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_mappings_division ON public.team_mappings USING btree (division_id);


--
-- Name: idx_team_mappings_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_mappings_team ON public.team_mappings USING btree (team_id);


--
-- Name: idx_teams_age_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teams_age_group_id ON public.teams USING btree (age_group_id);


--
-- Name: idx_teams_club_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teams_club_id ON public.teams USING btree (club_id);


--
-- Name: idx_teams_club_league; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teams_club_league ON public.teams USING btree (club_id, league_id);


--
-- Name: idx_teams_club_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teams_club_name ON public.teams USING btree (club_id, name);


--
-- Name: idx_teams_division_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teams_division_id ON public.teams USING btree (division_id);


--
-- Name: idx_teams_league_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teams_league_id ON public.teams USING btree (league_id);


--
-- Name: idx_teams_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teams_name ON public.teams USING btree (name);


--
-- Name: idx_user_profiles_club_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_profiles_club_id ON public.user_profiles USING btree (club_id);


--
-- Name: match_events match_event_set_expiry; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER match_event_set_expiry BEFORE INSERT ON public.match_events FOR EACH ROW EXECUTE FUNCTION public.set_match_event_message_expiry();


--
-- Name: match_lineups match_lineups_update_timestamp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER match_lineups_update_timestamp BEFORE UPDATE ON public.match_lineups FOR EACH ROW EXECUTE FUNCTION public.update_match_lineups_updated_at();


--
-- Name: player_match_stats player_match_stats_updated_at_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER player_match_stats_updated_at_trigger BEFORE UPDATE ON public.player_match_stats FOR EACH ROW EXECUTE FUNCTION public.update_player_match_stats_updated_at();


--
-- Name: players players_updated_at_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER players_updated_at_trigger BEFORE UPDATE ON public.players FOR EACH ROW EXECUTE FUNCTION public.update_players_updated_at();


--
-- Name: invite_requests trigger_update_invite_requests_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trigger_update_invite_requests_updated_at BEFORE UPDATE ON public.invite_requests FOR EACH ROW EXECUTE FUNCTION public.update_invite_requests_updated_at();


--
-- Name: clubs update_clubs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_clubs_updated_at BEFORE UPDATE ON public.clubs FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: leagues update_leagues_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_leagues_updated_at BEFORE UPDATE ON public.leagues FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: divisions divisions_league_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.divisions
    ADD CONSTRAINT divisions_league_id_fkey FOREIGN KEY (league_id) REFERENCES public.leagues(id) ON DELETE RESTRICT;


--
-- Name: invitations invitations_age_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitations
    ADD CONSTRAINT invitations_age_group_id_fkey FOREIGN KEY (age_group_id) REFERENCES public.age_groups(id) ON DELETE SET NULL;


--
-- Name: invitations invitations_club_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitations
    ADD CONSTRAINT invitations_club_id_fkey FOREIGN KEY (club_id) REFERENCES public.clubs(id);


--
-- Name: invitations invitations_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitations
    ADD CONSTRAINT invitations_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id) ON DELETE SET NULL;


--
-- Name: invitations invitations_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invitations
    ADD CONSTRAINT invitations_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE SET NULL;


--
-- Name: invite_requests invite_requests_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invite_requests
    ADD CONSTRAINT invite_requests_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES auth.users(id);


--
-- Name: match_events match_events_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_events
    ADD CONSTRAINT match_events_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.user_profiles(id) ON DELETE SET NULL;


--
-- Name: match_events match_events_deleted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_events
    ADD CONSTRAINT match_events_deleted_by_fkey FOREIGN KEY (deleted_by) REFERENCES public.user_profiles(id) ON DELETE SET NULL;


--
-- Name: match_events match_events_match_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_events
    ADD CONSTRAINT match_events_match_id_fkey FOREIGN KEY (match_id) REFERENCES public.matches(id) ON DELETE CASCADE;


--
-- Name: match_events match_events_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_events
    ADD CONSTRAINT match_events_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id) ON DELETE SET NULL;


--
-- Name: match_events match_events_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_events
    ADD CONSTRAINT match_events_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE SET NULL;


--
-- Name: match_lineups match_lineups_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_lineups
    ADD CONSTRAINT match_lineups_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.user_profiles(id) ON DELETE SET NULL;


--
-- Name: match_lineups match_lineups_match_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_lineups
    ADD CONSTRAINT match_lineups_match_id_fkey FOREIGN KEY (match_id) REFERENCES public.matches(id) ON DELETE CASCADE;


--
-- Name: match_lineups match_lineups_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_lineups
    ADD CONSTRAINT match_lineups_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE;


--
-- Name: match_lineups match_lineups_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_lineups
    ADD CONSTRAINT match_lineups_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.user_profiles(id) ON DELETE SET NULL;


--
-- Name: matches matches_age_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_age_group_id_fkey FOREIGN KEY (age_group_id) REFERENCES public.age_groups(id) ON DELETE CASCADE;


--
-- Name: matches matches_away_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_away_team_id_fkey FOREIGN KEY (away_team_id) REFERENCES public.teams(id) ON DELETE CASCADE;


--
-- Name: matches matches_division_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_division_id_fkey FOREIGN KEY (division_id) REFERENCES public.divisions(id) ON DELETE SET NULL;


--
-- Name: matches matches_home_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_home_team_id_fkey FOREIGN KEY (home_team_id) REFERENCES public.teams(id) ON DELETE CASCADE;


--
-- Name: matches matches_match_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_match_type_id_fkey FOREIGN KEY (match_type_id) REFERENCES public.match_types(id) ON DELETE CASCADE;


--
-- Name: matches matches_season_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matches
    ADD CONSTRAINT matches_season_id_fkey FOREIGN KEY (season_id) REFERENCES public.seasons(id) ON DELETE CASCADE;


--
-- Name: player_match_stats player_match_stats_match_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_match_stats
    ADD CONSTRAINT player_match_stats_match_id_fkey FOREIGN KEY (match_id) REFERENCES public.matches(id) ON DELETE CASCADE;


--
-- Name: player_match_stats player_match_stats_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_match_stats
    ADD CONSTRAINT player_match_stats_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.players(id) ON DELETE CASCADE;


--
-- Name: player_team_history player_team_history_age_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_team_history
    ADD CONSTRAINT player_team_history_age_group_id_fkey FOREIGN KEY (age_group_id) REFERENCES public.age_groups(id);


--
-- Name: player_team_history player_team_history_division_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_team_history
    ADD CONSTRAINT player_team_history_division_id_fkey FOREIGN KEY (division_id) REFERENCES public.divisions(id);


--
-- Name: player_team_history player_team_history_league_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_team_history
    ADD CONSTRAINT player_team_history_league_id_fkey FOREIGN KEY (league_id) REFERENCES public.leagues(id);


--
-- Name: player_team_history player_team_history_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_team_history
    ADD CONSTRAINT player_team_history_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.user_profiles(id) ON DELETE CASCADE;


--
-- Name: player_team_history player_team_history_season_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_team_history
    ADD CONSTRAINT player_team_history_season_id_fkey FOREIGN KEY (season_id) REFERENCES public.seasons(id) ON DELETE CASCADE;


--
-- Name: player_team_history player_team_history_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_team_history
    ADD CONSTRAINT player_team_history_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE;


--
-- Name: players players_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.players
    ADD CONSTRAINT players_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.user_profiles(id) ON DELETE SET NULL;


--
-- Name: players players_season_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.players
    ADD CONSTRAINT players_season_id_fkey FOREIGN KEY (season_id) REFERENCES public.seasons(id) ON DELETE CASCADE;


--
-- Name: players players_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.players
    ADD CONSTRAINT players_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE;


--
-- Name: players players_user_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.players
    ADD CONSTRAINT players_user_profile_id_fkey FOREIGN KEY (user_profile_id) REFERENCES public.user_profiles(id) ON DELETE SET NULL;


--
-- Name: team_manager_assignments team_manager_assignments_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_manager_assignments
    ADD CONSTRAINT team_manager_assignments_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE;


--
-- Name: team_mappings team_mappings_age_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_mappings
    ADD CONSTRAINT team_mappings_age_group_id_fkey FOREIGN KEY (age_group_id) REFERENCES public.age_groups(id) ON DELETE CASCADE;


--
-- Name: team_mappings team_mappings_division_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_mappings
    ADD CONSTRAINT team_mappings_division_id_fkey FOREIGN KEY (division_id) REFERENCES public.divisions(id) ON DELETE SET NULL;


--
-- Name: team_mappings team_mappings_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_mappings
    ADD CONSTRAINT team_mappings_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE;


--
-- Name: team_match_types team_match_types_age_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_match_types
    ADD CONSTRAINT team_match_types_age_group_id_fkey FOREIGN KEY (age_group_id) REFERENCES public.age_groups(id) ON DELETE CASCADE;


--
-- Name: team_match_types team_match_types_match_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_match_types
    ADD CONSTRAINT team_match_types_match_type_id_fkey FOREIGN KEY (match_type_id) REFERENCES public.match_types(id) ON DELETE CASCADE;


--
-- Name: team_match_types team_match_types_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_match_types
    ADD CONSTRAINT team_match_types_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE;


--
-- Name: teams teams_age_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_age_group_id_fkey FOREIGN KEY (age_group_id) REFERENCES public.age_groups(id);


--
-- Name: teams teams_club_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_club_id_fkey FOREIGN KEY (club_id) REFERENCES public.clubs(id) ON DELETE RESTRICT;


--
-- Name: teams teams_division_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_division_id_fkey FOREIGN KEY (division_id) REFERENCES public.divisions(id) ON DELETE RESTRICT;


--
-- Name: teams teams_league_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teams
    ADD CONSTRAINT teams_league_id_fkey FOREIGN KEY (league_id) REFERENCES public.leagues(id) ON DELETE RESTRICT;


--
-- Name: user_profiles user_profiles_assigned_age_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_assigned_age_group_id_fkey FOREIGN KEY (assigned_age_group_id) REFERENCES public.age_groups(id) ON DELETE SET NULL;


--
-- Name: user_profiles user_profiles_club_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_club_id_fkey FOREIGN KEY (club_id) REFERENCES public.clubs(id) ON DELETE SET NULL;


--
-- Name: user_profiles user_profiles_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profiles
    ADD CONSTRAINT user_profiles_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE SET NULL;


--
-- Name: player_team_history Admins can manage all history; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Admins can manage all history" ON public.player_team_history TO authenticated USING (public.is_admin()) WITH CHECK (public.is_admin());


--
-- Name: invite_requests Admins can update invite requests; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Admins can update invite requests" ON public.invite_requests FOR UPDATE USING ((EXISTS ( SELECT 1
   FROM public.user_profiles
  WHERE ((user_profiles.id = auth.uid()) AND ((user_profiles.role)::text = 'admin'::text)))));


--
-- Name: invite_requests Admins can view all invite requests; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Admins can view all invite requests" ON public.invite_requests FOR SELECT USING ((EXISTS ( SELECT 1
   FROM public.user_profiles
  WHERE ((user_profiles.id = auth.uid()) AND ((user_profiles.role)::text = 'admin'::text)))));


--
-- Name: invite_requests Anyone can submit invite requests; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Anyone can submit invite requests" ON public.invite_requests FOR INSERT WITH CHECK (true);


--
-- Name: player_team_history Players can view own history; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Players can view own history" ON public.player_team_history FOR SELECT TO authenticated USING ((player_id = auth.uid()));


--
-- Name: player_team_history Service role can manage history; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY "Service role can manage history" ON public.player_team_history TO service_role USING (true) WITH CHECK (true);


--
-- Name: age_groups; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.age_groups ENABLE ROW LEVEL SECURITY;

--
-- Name: age_groups age_groups_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY age_groups_admin_all ON public.age_groups USING (public.is_admin());


--
-- Name: age_groups age_groups_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY age_groups_select_all ON public.age_groups FOR SELECT USING (true);


--
-- Name: schema_version anon_read_schema_version; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY anon_read_schema_version ON public.schema_version FOR SELECT TO anon USING (true);


--
-- Name: schema_version authenticated_read_schema_version; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY authenticated_read_schema_version ON public.schema_version FOR SELECT TO authenticated USING (true);


--
-- Name: clubs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clubs ENABLE ROW LEVEL SECURITY;

--
-- Name: clubs clubs_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY clubs_admin_all ON public.clubs USING (public.is_admin());


--
-- Name: clubs clubs_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY clubs_select_all ON public.clubs FOR SELECT USING (true);


--
-- Name: divisions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.divisions ENABLE ROW LEVEL SECURITY;

--
-- Name: divisions divisions_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY divisions_admin_all ON public.divisions USING (public.is_admin());


--
-- Name: divisions divisions_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY divisions_select_all ON public.divisions FOR SELECT USING (true);


--
-- Name: invitations; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.invitations ENABLE ROW LEVEL SECURITY;

--
-- Name: invitations invitations_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY invitations_admin_all ON public.invitations USING (public.is_admin());


--
-- Name: invitations invitations_select_own; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY invitations_select_own ON public.invitations FOR SELECT USING ((auth.uid() = used_by_user_id));


--
-- Name: invite_requests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.invite_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: leagues; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.leagues ENABLE ROW LEVEL SECURITY;

--
-- Name: leagues leagues_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY leagues_admin_all ON public.leagues USING (public.is_admin());


--
-- Name: leagues leagues_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY leagues_select_all ON public.leagues FOR SELECT USING (true);


--
-- Name: match_events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.match_events ENABLE ROW LEVEL SECURITY;

--
-- Name: match_events match_events_insert_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY match_events_insert_policy ON public.match_events FOR INSERT WITH CHECK (true);


--
-- Name: match_events match_events_select_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY match_events_select_policy ON public.match_events FOR SELECT USING ((is_deleted = false));


--
-- Name: match_events match_events_update_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY match_events_update_policy ON public.match_events FOR UPDATE USING (true);


--
-- Name: match_lineups; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.match_lineups ENABLE ROW LEVEL SECURITY;

--
-- Name: match_lineups match_lineups_insert_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY match_lineups_insert_policy ON public.match_lineups FOR INSERT WITH CHECK (true);


--
-- Name: match_lineups match_lineups_select_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY match_lineups_select_policy ON public.match_lineups FOR SELECT USING (true);


--
-- Name: match_lineups match_lineups_update_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY match_lineups_update_policy ON public.match_lineups FOR UPDATE USING (true);


--
-- Name: match_types; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.match_types ENABLE ROW LEVEL SECURITY;

--
-- Name: match_types match_types_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY match_types_admin_all ON public.match_types USING (public.is_admin());


--
-- Name: match_types match_types_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY match_types_select_all ON public.match_types FOR SELECT USING (true);


--
-- Name: matches; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.matches ENABLE ROW LEVEL SECURITY;

--
-- Name: matches matches_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY matches_admin_all ON public.matches USING (public.is_admin());


--
-- Name: matches matches_manager_delete; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY matches_manager_delete ON public.matches FOR DELETE USING ((public.is_team_manager() AND (public.manages_team(home_team_id) OR public.manages_team(away_team_id))));


--
-- Name: matches matches_manager_insert; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY matches_manager_insert ON public.matches FOR INSERT WITH CHECK ((public.is_team_manager() AND (public.manages_team(home_team_id) OR public.manages_team(away_team_id))));


--
-- Name: matches matches_manager_update; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY matches_manager_update ON public.matches FOR UPDATE USING ((public.is_team_manager() AND (public.manages_team(home_team_id) OR public.manages_team(away_team_id))));


--
-- Name: matches matches_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY matches_select_all ON public.matches FOR SELECT USING (true);


--
-- Name: player_match_stats; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.player_match_stats ENABLE ROW LEVEL SECURITY;

--
-- Name: player_match_stats player_match_stats_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY player_match_stats_select_all ON public.player_match_stats FOR SELECT USING (true);


--
-- Name: player_match_stats player_match_stats_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY player_match_stats_service_all ON public.player_match_stats TO service_role USING (true) WITH CHECK (true);


--
-- Name: player_team_history; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.player_team_history ENABLE ROW LEVEL SECURITY;

--
-- Name: players; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.players ENABLE ROW LEVEL SECURITY;

--
-- Name: players players_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY players_select_all ON public.players FOR SELECT USING (true);


--
-- Name: players players_service_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY players_service_all ON public.players TO service_role USING (true) WITH CHECK (true);


--
-- Name: schema_version; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.schema_version ENABLE ROW LEVEL SECURITY;

--
-- Name: seasons; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.seasons ENABLE ROW LEVEL SECURITY;

--
-- Name: seasons seasons_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY seasons_admin_all ON public.seasons USING (public.is_admin());


--
-- Name: seasons seasons_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY seasons_select_all ON public.seasons FOR SELECT USING (true);


--
-- Name: service_accounts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.service_accounts ENABLE ROW LEVEL SECURITY;

--
-- Name: service_accounts service_accounts_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY service_accounts_admin_all ON public.service_accounts USING (public.is_admin());


--
-- Name: user_profiles service_role_insert_profiles; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY service_role_insert_profiles ON public.user_profiles FOR INSERT TO service_role WITH CHECK (true);


--
-- Name: user_profiles service_role_manage_profiles; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY service_role_manage_profiles ON public.user_profiles TO service_role USING (true) WITH CHECK (true);


--
-- Name: schema_version service_role_manage_schema_version; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY service_role_manage_schema_version ON public.schema_version TO service_role USING (true) WITH CHECK (true);


--
-- Name: team_manager_assignments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.team_manager_assignments ENABLE ROW LEVEL SECURITY;

--
-- Name: team_manager_assignments team_manager_assignments_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY team_manager_assignments_admin_all ON public.team_manager_assignments USING (public.is_admin());


--
-- Name: team_manager_assignments team_manager_assignments_select_authenticated; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY team_manager_assignments_select_authenticated ON public.team_manager_assignments FOR SELECT USING ((auth.role() = 'authenticated'::text));


--
-- Name: team_mappings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.team_mappings ENABLE ROW LEVEL SECURITY;

--
-- Name: team_mappings team_mappings_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY team_mappings_admin_all ON public.team_mappings USING (public.is_admin());


--
-- Name: team_mappings team_mappings_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY team_mappings_select_all ON public.team_mappings FOR SELECT USING (true);


--
-- Name: team_match_types; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.team_match_types ENABLE ROW LEVEL SECURITY;

--
-- Name: team_match_types team_match_types_admin_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY team_match_types_admin_all ON public.team_match_types USING (public.is_admin());


--
-- Name: team_match_types team_match_types_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY team_match_types_select_all ON public.team_match_types FOR SELECT USING (true);


--
-- Name: teams; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;

--
-- Name: teams teams_delete_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY teams_delete_policy ON public.teams FOR DELETE USING ((EXISTS ( SELECT 1
   FROM public.user_profiles
  WHERE ((user_profiles.id = auth.uid()) AND ((user_profiles.role)::text = 'admin'::text)))));


--
-- Name: teams teams_insert_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY teams_insert_policy ON public.teams FOR INSERT WITH CHECK (((EXISTS ( SELECT 1
   FROM public.user_profiles
  WHERE ((user_profiles.id = auth.uid()) AND ((user_profiles.role)::text = 'admin'::text)))) OR ((EXISTS ( SELECT 1
   FROM public.user_profiles
  WHERE ((user_profiles.id = auth.uid()) AND ((user_profiles.role)::text = 'club_manager'::text)))) AND (club_id = ( SELECT user_profiles.club_id
   FROM public.user_profiles
  WHERE (user_profiles.id = auth.uid()))))));


--
-- Name: teams teams_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY teams_select_all ON public.teams FOR SELECT USING (true);


--
-- Name: teams teams_update_policy; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY teams_update_policy ON public.teams FOR UPDATE USING (((EXISTS ( SELECT 1
   FROM public.user_profiles
  WHERE ((user_profiles.id = auth.uid()) AND ((user_profiles.role)::text = 'admin'::text)))) OR ((EXISTS ( SELECT 1
   FROM public.user_profiles
  WHERE ((user_profiles.id = auth.uid()) AND ((user_profiles.role)::text = 'club_manager'::text)))) AND (club_id = ( SELECT user_profiles.club_id
   FROM public.user_profiles
  WHERE (user_profiles.id = auth.uid()))))));


--
-- Name: user_profiles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--


