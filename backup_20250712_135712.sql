

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


CREATE EXTENSION IF NOT EXISTS "pg_net" WITH SCHEMA "extensions";






COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "public"."get_user_role"() RETURNS "text"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
    RETURN (
        SELECT role FROM user_profiles 
        WHERE id = auth.uid()
    );
END;
$$;


ALTER FUNCTION "public"."get_user_role"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_new_user"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
    INSERT INTO public.user_profiles (id, role, display_name)
    VALUES (
        NEW.id, 
        'team-fan', -- Default role
        COALESCE(NEW.raw_user_meta_data->>'display_name', NEW.email)
    );
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."handle_new_user"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."promote_to_admin"("user_email" "text") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
    user_id UUID;
BEGIN
    -- Get user ID from email
    SELECT id INTO user_id 
    FROM auth.users 
    WHERE email = user_email;
    
    IF user_id IS NULL THEN
        RETURN FALSE;
    END IF;
    
    -- Update role to admin
    UPDATE user_profiles 
    SET role = 'admin', updated_at = NOW()
    WHERE id = user_id;
    
    RETURN TRUE;
END;
$$;


ALTER FUNCTION "public"."promote_to_admin"("user_email" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."promote_user_to_admin"("user_email" "text") RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    user_record RECORD;
BEGIN
    -- Check if user exists in auth.users
    SELECT id, email INTO user_record 
    FROM auth.users 
    WHERE email = user_email;
    
    IF user_record.id IS NULL THEN
        RETURN 'User not found: ' || user_email;
    END IF;
    
    -- Update or insert user profile
    INSERT INTO user_profiles (id, role, display_name)
    VALUES (user_record.id, 'admin', 'Admin User')
    ON CONFLICT (id) 
    DO UPDATE SET role = 'admin', updated_at = NOW();
    
    RETURN 'User promoted to admin: ' || user_email;
END;
$$;


ALTER FUNCTION "public"."promote_user_to_admin"("user_email" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."user_has_role"("required_role" "text") RETURNS boolean
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM user_profiles 
        WHERE id = auth.uid() AND role = required_role
    );
END;
$$;


ALTER FUNCTION "public"."user_has_role"("required_role" "text") OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."age_groups" (
    "id" integer NOT NULL,
    "name" character varying(50) NOT NULL,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "updated_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE "public"."age_groups" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."age_groups_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."age_groups_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."age_groups_id_seq" OWNED BY "public"."age_groups"."id";



CREATE TABLE IF NOT EXISTS "public"."divisions" (
    "id" integer NOT NULL,
    "name" character varying(50) NOT NULL,
    "description" "text",
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "updated_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE "public"."divisions" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."divisions_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."divisions_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."divisions_id_seq" OWNED BY "public"."divisions"."id";



CREATE TABLE IF NOT EXISTS "public"."game_types" (
    "id" integer NOT NULL,
    "name" character varying(50) NOT NULL,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "updated_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE "public"."game_types" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."game_types_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."game_types_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."game_types_id_seq" OWNED BY "public"."game_types"."id";



CREATE TABLE IF NOT EXISTS "public"."games" (
    "id" integer NOT NULL,
    "game_date" "date" NOT NULL,
    "home_team_id" integer,
    "away_team_id" integer,
    "home_score" integer DEFAULT 0,
    "away_score" integer DEFAULT 0,
    "season_id" integer,
    "age_group_id" integer,
    "game_type_id" integer,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "updated_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "division_id" integer,
    CONSTRAINT "different_teams" CHECK (("home_team_id" <> "away_team_id"))
);


ALTER TABLE "public"."games" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."games_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."games_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."games_id_seq" OWNED BY "public"."games"."id";



CREATE TABLE IF NOT EXISTS "public"."seasons" (
    "id" integer NOT NULL,
    "name" character varying(50) NOT NULL,
    "start_date" "date" NOT NULL,
    "end_date" "date" NOT NULL,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "updated_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE "public"."seasons" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."seasons_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."seasons_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."seasons_id_seq" OWNED BY "public"."seasons"."id";



CREATE TABLE IF NOT EXISTS "public"."team_mappings" (
    "id" integer NOT NULL,
    "team_id" integer,
    "age_group_id" integer,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "division_id" integer
);


ALTER TABLE "public"."team_mappings" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."team_mappings_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."team_mappings_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."team_mappings_id_seq" OWNED BY "public"."team_mappings"."id";



CREATE TABLE IF NOT EXISTS "public"."teams" (
    "id" integer NOT NULL,
    "name" character varying(100) NOT NULL,
    "city" character varying(100) DEFAULT 'Unknown City'::character varying,
    "created_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    "updated_at" timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE "public"."teams" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."teams_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."teams_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."teams_id_seq" OWNED BY "public"."teams"."id";



CREATE TABLE IF NOT EXISTS "public"."user_profiles" (
    "id" "uuid" NOT NULL,
    "role" "text" NOT NULL,
    "team_id" integer,
    "display_name" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "user_profiles_role_check" CHECK (("role" = ANY (ARRAY['admin'::"text", 'team-manager'::"text", 'team-fan'::"text", 'team-player'::"text"])))
);


ALTER TABLE "public"."user_profiles" OWNER TO "postgres";


ALTER TABLE ONLY "public"."age_groups" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."age_groups_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."divisions" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."divisions_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."game_types" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."game_types_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."games" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."games_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."seasons" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."seasons_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."team_mappings" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."team_mappings_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."teams" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."teams_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."age_groups"
    ADD CONSTRAINT "age_groups_name_key" UNIQUE ("name");



ALTER TABLE ONLY "public"."age_groups"
    ADD CONSTRAINT "age_groups_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."divisions"
    ADD CONSTRAINT "divisions_name_key" UNIQUE ("name");



ALTER TABLE ONLY "public"."divisions"
    ADD CONSTRAINT "divisions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."game_types"
    ADD CONSTRAINT "game_types_name_key" UNIQUE ("name");



ALTER TABLE ONLY "public"."game_types"
    ADD CONSTRAINT "game_types_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."games"
    ADD CONSTRAINT "games_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."seasons"
    ADD CONSTRAINT "seasons_name_key" UNIQUE ("name");



ALTER TABLE ONLY "public"."seasons"
    ADD CONSTRAINT "seasons_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."team_mappings"
    ADD CONSTRAINT "team_mappings_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."team_mappings"
    ADD CONSTRAINT "team_mappings_team_id_age_group_id_key" UNIQUE ("team_id", "age_group_id");



ALTER TABLE ONLY "public"."teams"
    ADD CONSTRAINT "teams_name_key" UNIQUE ("name");



ALTER TABLE ONLY "public"."teams"
    ADD CONSTRAINT "teams_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_profiles"
    ADD CONSTRAINT "user_profiles_pkey" PRIMARY KEY ("id");



CREATE INDEX "idx_games_age_group" ON "public"."games" USING "btree" ("age_group_id");



CREATE INDEX "idx_games_away_team" ON "public"."games" USING "btree" ("away_team_id");



CREATE INDEX "idx_games_date" ON "public"."games" USING "btree" ("game_date");



CREATE INDEX "idx_games_division" ON "public"."games" USING "btree" ("division_id");



CREATE INDEX "idx_games_home_team" ON "public"."games" USING "btree" ("home_team_id");



CREATE INDEX "idx_games_season" ON "public"."games" USING "btree" ("season_id");



CREATE INDEX "idx_team_mappings_age_group" ON "public"."team_mappings" USING "btree" ("age_group_id");



CREATE INDEX "idx_team_mappings_division" ON "public"."team_mappings" USING "btree" ("division_id");



CREATE INDEX "idx_team_mappings_team" ON "public"."team_mappings" USING "btree" ("team_id");



ALTER TABLE ONLY "public"."games"
    ADD CONSTRAINT "games_age_group_id_fkey" FOREIGN KEY ("age_group_id") REFERENCES "public"."age_groups"("id");



ALTER TABLE ONLY "public"."games"
    ADD CONSTRAINT "games_away_team_id_fkey" FOREIGN KEY ("away_team_id") REFERENCES "public"."teams"("id");



ALTER TABLE ONLY "public"."games"
    ADD CONSTRAINT "games_division_id_fkey" FOREIGN KEY ("division_id") REFERENCES "public"."divisions"("id");



ALTER TABLE ONLY "public"."games"
    ADD CONSTRAINT "games_game_type_id_fkey" FOREIGN KEY ("game_type_id") REFERENCES "public"."game_types"("id");



ALTER TABLE ONLY "public"."games"
    ADD CONSTRAINT "games_home_team_id_fkey" FOREIGN KEY ("home_team_id") REFERENCES "public"."teams"("id");



ALTER TABLE ONLY "public"."games"
    ADD CONSTRAINT "games_season_id_fkey" FOREIGN KEY ("season_id") REFERENCES "public"."seasons"("id");



ALTER TABLE ONLY "public"."team_mappings"
    ADD CONSTRAINT "team_mappings_age_group_id_fkey" FOREIGN KEY ("age_group_id") REFERENCES "public"."age_groups"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."team_mappings"
    ADD CONSTRAINT "team_mappings_division_id_fkey" FOREIGN KEY ("division_id") REFERENCES "public"."divisions"("id");



ALTER TABLE ONLY "public"."team_mappings"
    ADD CONSTRAINT "team_mappings_team_id_fkey" FOREIGN KEY ("team_id") REFERENCES "public"."teams"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_profiles"
    ADD CONSTRAINT "user_profiles_id_fkey" FOREIGN KEY ("id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_profiles"
    ADD CONSTRAINT "user_profiles_team_id_fkey" FOREIGN KEY ("team_id") REFERENCES "public"."teams"("id") ON DELETE SET NULL;



CREATE POLICY "Admins can manage age_groups" ON "public"."age_groups" USING ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'admin'::"text")))));



CREATE POLICY "Admins can manage all games" ON "public"."games" USING ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'admin'::"text")))));



CREATE POLICY "Admins can manage divisions" ON "public"."divisions" USING ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'admin'::"text")))));



CREATE POLICY "Admins can manage game_types" ON "public"."game_types" USING ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'admin'::"text")))));



CREATE POLICY "Admins can manage seasons" ON "public"."seasons" USING ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'admin'::"text")))));



CREATE POLICY "Admins can manage team_mappings" ON "public"."team_mappings" USING ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'admin'::"text")))));



CREATE POLICY "Admins can manage teams" ON "public"."teams" USING ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'admin'::"text")))));



CREATE POLICY "Everyone can view age_groups" ON "public"."age_groups" FOR SELECT USING (true);



CREATE POLICY "Everyone can view divisions" ON "public"."divisions" FOR SELECT USING (true);



CREATE POLICY "Everyone can view game_types" ON "public"."game_types" FOR SELECT USING (true);



CREATE POLICY "Everyone can view games" ON "public"."games" FOR SELECT USING (true);



CREATE POLICY "Everyone can view seasons" ON "public"."seasons" FOR SELECT USING (true);



CREATE POLICY "Everyone can view team_mappings" ON "public"."team_mappings" FOR SELECT USING (true);



CREATE POLICY "Everyone can view teams" ON "public"."teams" FOR SELECT USING (true);



CREATE POLICY "Team managers can add games for their team" ON "public"."games" FOR INSERT WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'team-manager'::"text") AND (("user_profiles"."team_id" = "games"."home_team_id") OR ("user_profiles"."team_id" = "games"."away_team_id"))))));



CREATE POLICY "Team managers can edit games for their team" ON "public"."games" FOR UPDATE USING ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'team-manager'::"text") AND (("user_profiles"."team_id" = "games"."home_team_id") OR ("user_profiles"."team_id" = "games"."away_team_id"))))));



CREATE POLICY "Team managers can update their team" ON "public"."teams" FOR UPDATE USING ((EXISTS ( SELECT 1
   FROM "public"."user_profiles"
  WHERE (("user_profiles"."id" = "auth"."uid"()) AND ("user_profiles"."role" = 'team-manager'::"text") AND ("user_profiles"."team_id" = "teams"."id")))));





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";





GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";































































































































































GRANT ALL ON FUNCTION "public"."get_user_role"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_user_role"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_user_role"() TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "service_role";



GRANT ALL ON FUNCTION "public"."promote_to_admin"("user_email" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."promote_to_admin"("user_email" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."promote_to_admin"("user_email" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."promote_user_to_admin"("user_email" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."promote_user_to_admin"("user_email" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."promote_user_to_admin"("user_email" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."user_has_role"("required_role" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."user_has_role"("required_role" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."user_has_role"("required_role" "text") TO "service_role";


















GRANT ALL ON TABLE "public"."age_groups" TO "anon";
GRANT ALL ON TABLE "public"."age_groups" TO "authenticated";
GRANT ALL ON TABLE "public"."age_groups" TO "service_role";



GRANT ALL ON SEQUENCE "public"."age_groups_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."age_groups_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."age_groups_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."divisions" TO "anon";
GRANT ALL ON TABLE "public"."divisions" TO "authenticated";
GRANT ALL ON TABLE "public"."divisions" TO "service_role";



GRANT ALL ON SEQUENCE "public"."divisions_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."divisions_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."divisions_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."game_types" TO "anon";
GRANT ALL ON TABLE "public"."game_types" TO "authenticated";
GRANT ALL ON TABLE "public"."game_types" TO "service_role";



GRANT ALL ON SEQUENCE "public"."game_types_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."game_types_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."game_types_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."games" TO "anon";
GRANT ALL ON TABLE "public"."games" TO "authenticated";
GRANT ALL ON TABLE "public"."games" TO "service_role";



GRANT ALL ON SEQUENCE "public"."games_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."games_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."games_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."seasons" TO "anon";
GRANT ALL ON TABLE "public"."seasons" TO "authenticated";
GRANT ALL ON TABLE "public"."seasons" TO "service_role";



GRANT ALL ON SEQUENCE "public"."seasons_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."seasons_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."seasons_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."team_mappings" TO "anon";
GRANT ALL ON TABLE "public"."team_mappings" TO "authenticated";
GRANT ALL ON TABLE "public"."team_mappings" TO "service_role";



GRANT ALL ON SEQUENCE "public"."team_mappings_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."team_mappings_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."team_mappings_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."teams" TO "anon";
GRANT ALL ON TABLE "public"."teams" TO "authenticated";
GRANT ALL ON TABLE "public"."teams" TO "service_role";



GRANT ALL ON SEQUENCE "public"."teams_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."teams_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."teams_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."user_profiles" TO "anon";
GRANT ALL ON TABLE "public"."user_profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."user_profiles" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";






























RESET ALL;
