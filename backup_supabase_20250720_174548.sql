SET session_replication_role = replica;

--
-- PostgreSQL database dump
--

-- Dumped from database version 17.4
-- Dumped by pg_dump version 17.4

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
-- Data for Name: audit_log_entries; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

INSERT INTO "auth"."audit_log_entries" ("instance_id", "id", "payload", "created_at", "ip_address") VALUES
	('00000000-0000-0000-0000-000000000000', '63be03d7-e018-49b0-a0a8-8de189846049', '{"action":"user_signedup","actor_id":"c08e7505-5146-4189-a3b0-8663f59a5f6d","actor_username":"tdrake13@gmail.com","actor_via_sso":false,"log_type":"team","traits":{"provider":"email"}}', '2025-07-20 20:57:06.790795+00', ''),
	('00000000-0000-0000-0000-000000000000', '780ff75c-4ea5-4781-b49c-0893c701e3f5', '{"action":"login","actor_id":"c08e7505-5146-4189-a3b0-8663f59a5f6d","actor_username":"tdrake13@gmail.com","actor_via_sso":false,"log_type":"account","traits":{"provider":"email"}}', '2025-07-20 20:57:06.792943+00', ''),
	('00000000-0000-0000-0000-000000000000', '054c1c49-e2d4-4558-9614-966fb22097b7', '{"action":"logout","actor_id":"c08e7505-5146-4189-a3b0-8663f59a5f6d","actor_username":"tdrake13@gmail.com","actor_via_sso":false,"log_type":"account"}', '2025-07-20 20:59:48.703809+00', ''),
	('00000000-0000-0000-0000-000000000000', '84a6b1a3-fdde-457a-975e-0e248a68895f', '{"action":"login","actor_id":"c08e7505-5146-4189-a3b0-8663f59a5f6d","actor_username":"tdrake13@gmail.com","actor_via_sso":false,"log_type":"account","traits":{"provider":"email"}}', '2025-07-20 21:00:00.047892+00', ''),
	('00000000-0000-0000-0000-000000000000', '8b9eb714-5199-4f71-b8c1-d5660b6d8136', '{"action":"logout","actor_id":"c08e7505-5146-4189-a3b0-8663f59a5f6d","actor_username":"tdrake13@gmail.com","actor_via_sso":false,"log_type":"account"}', '2025-07-20 21:04:00.718367+00', ''),
	('00000000-0000-0000-0000-000000000000', 'a2603527-7681-413d-8e1a-013afe2a79cf', '{"action":"user_signedup","actor_id":"d1aac2c5-9af6-4185-ac39-a4b2a48e7a6a","actor_username":"gabedrake28@gmail.com","actor_via_sso":false,"log_type":"team","traits":{"provider":"email"}}', '2025-07-20 21:04:29.610297+00', ''),
	('00000000-0000-0000-0000-000000000000', '0d05ff13-b1d1-4238-abe2-2334889360ed', '{"action":"login","actor_id":"d1aac2c5-9af6-4185-ac39-a4b2a48e7a6a","actor_username":"gabedrake28@gmail.com","actor_via_sso":false,"log_type":"account","traits":{"provider":"email"}}', '2025-07-20 21:04:29.612554+00', ''),
	('00000000-0000-0000-0000-000000000000', 'c46b5e1f-8064-41b3-bf2b-22ad82df1329', '{"action":"logout","actor_id":"d1aac2c5-9af6-4185-ac39-a4b2a48e7a6a","actor_username":"gabedrake28@gmail.com","actor_via_sso":false,"log_type":"account"}', '2025-07-20 21:16:11.698587+00', ''),
	('00000000-0000-0000-0000-000000000000', '9522a960-b08b-45f2-b667-3183fd59311e', '{"action":"login","actor_id":"d1aac2c5-9af6-4185-ac39-a4b2a48e7a6a","actor_username":"gabedrake28@gmail.com","actor_via_sso":false,"log_type":"account","traits":{"provider":"email"}}', '2025-07-20 21:16:25.788262+00', '');


--
-- Data for Name: flow_state; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

INSERT INTO "auth"."users" ("instance_id", "id", "aud", "role", "email", "encrypted_password", "email_confirmed_at", "invited_at", "confirmation_token", "confirmation_sent_at", "recovery_token", "recovery_sent_at", "email_change_token_new", "email_change", "email_change_sent_at", "last_sign_in_at", "raw_app_meta_data", "raw_user_meta_data", "is_super_admin", "created_at", "updated_at", "phone", "phone_confirmed_at", "phone_change", "phone_change_token", "phone_change_sent_at", "email_change_token_current", "email_change_confirm_status", "banned_until", "reauthentication_token", "reauthentication_sent_at", "is_sso_user", "deleted_at", "is_anonymous") VALUES
	('00000000-0000-0000-0000-000000000000', 'c08e7505-5146-4189-a3b0-8663f59a5f6d', 'authenticated', 'authenticated', 'tdrake13@gmail.com', '$2a$10$shP2STcweOCDY3omxJwrJOXN1WrAEfa6DaFGu0gcCIrGsFQgJBYFi', '2025-07-20 20:57:06.791383+00', NULL, '', NULL, '', NULL, '', '', NULL, '2025-07-20 21:00:00.048373+00', '{"provider": "email", "providers": ["email"]}', '{"sub": "c08e7505-5146-4189-a3b0-8663f59a5f6d", "email": "tdrake13@gmail.com", "display_name": "Tom D (Admin)", "email_verified": true, "phone_verified": false}', NULL, '2025-07-20 20:57:06.785767+00', '2025-07-20 21:00:00.049345+00', NULL, NULL, '', '', NULL, '', 0, NULL, '', NULL, false, NULL, false),
	('00000000-0000-0000-0000-000000000000', 'd1aac2c5-9af6-4185-ac39-a4b2a48e7a6a', 'authenticated', 'authenticated', 'gabedrake28@gmail.com', '$2a$10$vr3gGwy63WXLb8IyBO8EG.yKPPnpO7TemmdOws0uA1Mh20kEljsqu', '2025-07-20 21:04:29.610588+00', NULL, '', NULL, '', NULL, '', '', NULL, '2025-07-20 21:16:25.788739+00', '{"provider": "email", "providers": ["email"]}', '{"sub": "d1aac2c5-9af6-4185-ac39-a4b2a48e7a6a", "email": "gabedrake28@gmail.com", "display_name": "Gabe", "email_verified": true, "phone_verified": false}', NULL, '2025-07-20 21:04:29.607695+00', '2025-07-20 21:16:25.789666+00', NULL, NULL, '', '', NULL, '', 0, NULL, '', NULL, false, NULL, false);


--
-- Data for Name: identities; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

INSERT INTO "auth"."identities" ("provider_id", "user_id", "identity_data", "provider", "last_sign_in_at", "created_at", "updated_at", "id") VALUES
	('c08e7505-5146-4189-a3b0-8663f59a5f6d', 'c08e7505-5146-4189-a3b0-8663f59a5f6d', '{"sub": "c08e7505-5146-4189-a3b0-8663f59a5f6d", "email": "tdrake13@gmail.com", "display_name": "Tom D (Admin)", "email_verified": false, "phone_verified": false}', 'email', '2025-07-20 20:57:06.788887+00', '2025-07-20 20:57:06.78891+00', '2025-07-20 20:57:06.78891+00', '72be9764-0c50-4f91-aa0d-535910beffde'),
	('d1aac2c5-9af6-4185-ac39-a4b2a48e7a6a', 'd1aac2c5-9af6-4185-ac39-a4b2a48e7a6a', '{"sub": "d1aac2c5-9af6-4185-ac39-a4b2a48e7a6a", "email": "gabedrake28@gmail.com", "display_name": "Gabe", "email_verified": false, "phone_verified": false}', 'email', '2025-07-20 21:04:29.609133+00', '2025-07-20 21:04:29.609151+00', '2025-07-20 21:04:29.609151+00', 'b931e105-ef09-42db-ac12-cc473364beff');


--
-- Data for Name: instances; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: sessions; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

INSERT INTO "auth"."sessions" ("id", "user_id", "created_at", "updated_at", "factor_id", "aal", "not_after", "refreshed_at", "user_agent", "ip", "tag") VALUES
	('2854b60b-090f-4441-9986-d91f9007c40a', 'd1aac2c5-9af6-4185-ac39-a4b2a48e7a6a', '2025-07-20 21:16:25.788783+00', '2025-07-20 21:16:25.788783+00', NULL, 'aal1', NULL, NULL, 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36', '173.194.208.95', NULL);


--
-- Data for Name: mfa_amr_claims; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

INSERT INTO "auth"."mfa_amr_claims" ("session_id", "created_at", "updated_at", "authentication_method", "id") VALUES
	('2854b60b-090f-4441-9986-d91f9007c40a', '2025-07-20 21:16:25.789826+00', '2025-07-20 21:16:25.789826+00', 'password', 'fba9f34f-7aac-4f65-863f-0266857e67b3');


--
-- Data for Name: mfa_factors; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: mfa_challenges; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: one_time_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

INSERT INTO "auth"."refresh_tokens" ("instance_id", "id", "token", "user_id", "revoked", "created_at", "updated_at", "parent", "session_id") VALUES
	('00000000-0000-0000-0000-000000000000', 4, 'pe7bb4pm5j34', 'd1aac2c5-9af6-4185-ac39-a4b2a48e7a6a', false, '2025-07-20 21:16:25.789211+00', '2025-07-20 21:16:25.789211+00', NULL, '2854b60b-090f-4441-9986-d91f9007c40a');


--
-- Data for Name: sso_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: saml_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: saml_relay_states; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: sso_domains; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--



--
-- Data for Name: age_groups; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."age_groups" ("id", "name", "created_at", "updated_at") VALUES
	(1, 'U13', '2025-07-20 20:08:45.733237+00', '2025-07-20 20:08:45.733237+00'),
	(2, 'U14', '2025-07-20 20:08:45.733237+00', '2025-07-20 20:08:45.733237+00');


--
-- Data for Name: divisions; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."divisions" ("id", "name", "description", "created_at", "updated_at") VALUES
	(1, 'Northeast', 'Northeast Division', '2025-07-20 20:08:45.77609+00', '2025-07-20 20:08:45.77609+00');


--
-- Data for Name: game_types; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."game_types" ("id", "name", "created_at", "updated_at") VALUES
	(1, 'League', '2025-07-20 20:08:45.733237+00', '2025-07-20 20:08:45.733237+00'),
	(2, 'Tournament', '2025-07-20 20:08:45.733237+00', '2025-07-20 20:08:45.733237+00'),
	(3, 'Friendly', '2025-07-20 20:08:45.733237+00', '2025-07-20 20:08:45.733237+00'),
	(4, 'Playoff', '2025-07-20 20:08:45.733237+00', '2025-07-20 20:08:45.733237+00');


--
-- Data for Name: seasons; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."seasons" ("id", "name", "start_date", "end_date", "created_at", "updated_at") VALUES
	(2, '2024-2025', '2024-09-01', '2025-06-30', '2025-07-20 20:08:45.733237+00', '2025-07-20 20:08:45.733237+00'),
	(3, '2025-2026', '2025-09-01', '2026-06-30', '2025-07-20 20:08:45.733237+00', '2025-07-20 20:08:45.733237+00');


--
-- Data for Name: teams; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."teams" ("id", "name", "city", "created_at", "updated_at", "academy_team") VALUES
	(1, 'Bayside FC', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(2, 'Beachside of Connecticut', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(3, 'Blau Weiss Gottschee', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(4, 'Cedar Stars Academy Bergen', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(5, 'Downtown United Soccer Club', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(6, 'FA Euro New York', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(7, 'FC Greater Boston Bolts', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(8, 'FC Westchester', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(9, 'IFA', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(10, 'Long Island Soccer Club', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(11, 'Metropolitan Oval', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(12, 'NEFC', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(15, 'New York SC', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(16, 'Oakwood Soccer Club', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(17, 'Rochester NY FC', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(18, 'Seacoast United', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(19, 'Valeo Futbol Club', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(20, 'Intercontinental Football Academy of New England', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', false),
	(13, 'New England Revolution', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', true),
	(14, 'New York City FC', 'Northeast', '2025-07-20 20:26:48.706028+00', '2025-07-20 20:26:48.706028+00', true),
	(21, 'NYRB', 'New York', '2025-07-20 21:01:30.392053+00', '2025-07-20 21:01:30.392053+00', true);


--
-- Data for Name: games; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."games" ("id", "game_date", "home_team_id", "away_team_id", "home_score", "away_score", "season_id", "age_group_id", "game_type_id", "created_at", "updated_at", "division_id") VALUES
	(1, '2025-08-16', 21, 9, 0, 0, 3, 2, 3, '2025-07-20 21:03:11.243726+00', '2025-07-20 21:03:11.243726+00', NULL),
	(2, '2025-08-17', 14, 9, 0, 0, 3, 2, 3, '2025-07-20 21:03:25.260617+00', '2025-07-20 21:03:25.260617+00', NULL);


--
-- Data for Name: team_game_types; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."team_game_types" ("id", "team_id", "game_type_id", "age_group_id", "is_active", "created_at", "updated_at") VALUES
	(1, 1, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(2, 1, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(3, 1, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(4, 1, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(5, 2, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(6, 2, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(7, 2, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(8, 2, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(9, 3, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(10, 3, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(11, 3, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(12, 3, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(13, 4, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(14, 4, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(15, 4, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(16, 4, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(17, 5, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(18, 5, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(19, 5, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(20, 5, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(21, 6, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(22, 6, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(23, 6, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(24, 6, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(25, 7, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(26, 7, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(27, 7, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(28, 7, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(29, 8, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(30, 8, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(31, 8, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(32, 8, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(33, 9, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(34, 9, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(35, 9, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(36, 9, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(37, 10, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(38, 10, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(39, 10, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(40, 10, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(41, 11, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(42, 11, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(43, 11, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(44, 11, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(45, 12, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(46, 12, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(47, 12, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(48, 12, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(49, 13, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(50, 13, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(51, 13, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(52, 13, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(53, 14, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(54, 14, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(55, 14, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(56, 14, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(57, 15, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(58, 15, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(59, 15, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(60, 15, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(61, 16, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(62, 16, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(63, 16, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(64, 16, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(65, 17, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(66, 17, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(67, 17, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(68, 17, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(69, 18, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(70, 18, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(71, 18, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(72, 18, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(73, 19, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(74, 19, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(75, 19, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(76, 19, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(77, 20, 1, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(78, 20, 2, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(79, 20, 3, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(80, 20, 4, 2, true, '2025-07-20 20:26:48.724247+00', '2025-07-20 20:26:48.724247+00'),
	(81, 21, 3, 2, true, '2025-07-20 21:02:45.47264+00', '2025-07-20 21:02:45.47264+00'),
	(82, 21, 4, 2, true, '2025-07-20 21:02:45.494566+00', '2025-07-20 21:02:45.494566+00'),
	(83, 21, 2, 2, true, '2025-07-20 21:02:45.512812+00', '2025-07-20 21:02:45.512812+00');


--
-- Data for Name: team_mappings; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."team_mappings" ("id", "team_id", "age_group_id", "created_at", "division_id") VALUES
	(1, 1, 2, '2025-07-20 20:26:48.718945+00', 1),
	(2, 2, 2, '2025-07-20 20:26:48.718945+00', 1),
	(3, 3, 2, '2025-07-20 20:26:48.718945+00', 1),
	(4, 4, 2, '2025-07-20 20:26:48.718945+00', 1),
	(5, 5, 2, '2025-07-20 20:26:48.718945+00', 1),
	(6, 6, 2, '2025-07-20 20:26:48.718945+00', 1),
	(7, 7, 2, '2025-07-20 20:26:48.718945+00', 1),
	(8, 8, 2, '2025-07-20 20:26:48.718945+00', 1),
	(9, 9, 2, '2025-07-20 20:26:48.718945+00', 1),
	(10, 10, 2, '2025-07-20 20:26:48.718945+00', 1),
	(11, 11, 2, '2025-07-20 20:26:48.718945+00', 1),
	(12, 12, 2, '2025-07-20 20:26:48.718945+00', 1),
	(13, 13, 2, '2025-07-20 20:26:48.718945+00', 1),
	(14, 14, 2, '2025-07-20 20:26:48.718945+00', 1),
	(15, 15, 2, '2025-07-20 20:26:48.718945+00', 1),
	(16, 16, 2, '2025-07-20 20:26:48.718945+00', 1),
	(17, 17, 2, '2025-07-20 20:26:48.718945+00', 1),
	(18, 18, 2, '2025-07-20 20:26:48.718945+00', 1),
	(19, 19, 2, '2025-07-20 20:26:48.718945+00', 1),
	(20, 20, 2, '2025-07-20 20:26:48.718945+00', 1),
	(21, 21, 2, '2025-07-20 21:01:30.412482+00', NULL);


--
-- Data for Name: user_profiles; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO "public"."user_profiles" ("id", "role", "team_id", "display_name", "created_at", "updated_at", "player_number", "positions") VALUES
	('c08e7505-5146-4189-a3b0-8663f59a5f6d', 'admin', 9, 'Tom D (Admin)', '2025-07-20 20:57:06.785538+00', '2025-07-20 20:57:27.308+00', NULL, '[]'),
	('d1aac2c5-9af6-4185-ac39-a4b2a48e7a6a', 'team-player', 9, 'Gabe', '2025-07-20 21:04:29.607486+00', '2025-07-20 21:21:48.570042+00', 35, '["CB", "LCB"]');


--
-- Data for Name: buckets; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: buckets_analytics; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: iceberg_namespaces; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: iceberg_tables; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: objects; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: prefixes; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: s3_multipart_uploads; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: s3_multipart_uploads_parts; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--



--
-- Data for Name: hooks; Type: TABLE DATA; Schema: supabase_functions; Owner: supabase_functions_admin
--



--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: supabase_auth_admin
--

SELECT pg_catalog.setval('"auth"."refresh_tokens_id_seq"', 4, true);


--
-- Name: age_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."age_groups_id_seq"', 8, true);


--
-- Name: divisions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."divisions_id_seq"', 6, true);


--
-- Name: game_types_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."game_types_id_seq"', 4, true);


--
-- Name: games_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."games_id_seq"', 2, true);


--
-- Name: seasons_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."seasons_id_seq"', 4, true);


--
-- Name: team_game_types_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."team_game_types_id_seq"', 83, true);


--
-- Name: team_mappings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."team_mappings_id_seq"', 21, true);


--
-- Name: teams_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('"public"."teams_id_seq"', 21, true);


--
-- Name: hooks_id_seq; Type: SEQUENCE SET; Schema: supabase_functions; Owner: supabase_functions_admin
--

SELECT pg_catalog.setval('"supabase_functions"."hooks_id_seq"', 1, false);


--
-- PostgreSQL database dump complete
--

RESET ALL;
