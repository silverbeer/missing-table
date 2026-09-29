-- MT AI conversations (SB-1143): the walking skeleton's persistence.
--
-- MT's tables are the system of record for conversations. ADK's session is
-- an in-memory, per-request object rebuilt from these rows, so nothing here
-- depends on ADK's internals (docs/03-architecture/mt2/ai.md).
--
-- A conversation is a sequence of turns. Each turn is one user message and
-- one assistant message sharing a `turn` number; they are written together
-- after the turn finishes. A turn that did not produce an answer is still
-- recorded — its assistant row carries the status (budget_exhausted,
-- ai_failed) and no content — and is left out when history is rebuilt.
--
-- Deliberately not here yet: tool-call detail, token counts, cost, feedback.
-- Those land with the slices that use them.

CREATE TABLE public.ai_conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    agent_version text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_conversations_user ON public.ai_conversations(user_id);

CREATE TABLE public.ai_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES public.ai_conversations(id) ON DELETE CASCADE,
    turn integer NOT NULL CHECK (turn >= 1),
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text,
    status text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'budget_exhausted', 'ai_failed')),
    model text,
    agent_version text,
    llm_calls integer,
    tool_calls integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ai_messages_turn_role_unique UNIQUE (conversation_id, turn, role),
    CONSTRAINT ai_messages_user_has_content CHECK (role <> 'user' OR content IS NOT NULL)
);

CREATE INDEX idx_ai_messages_conversation_turn ON public.ai_messages(conversation_id, turn);

-- The backend reads and writes with the service key. RLS is defence in depth:
-- a user may read only their own conversations; admins may read everything.
ALTER TABLE public.ai_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY ai_conversations_user_select
    ON public.ai_conversations FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY ai_conversations_admin_all
    ON public.ai_conversations FOR ALL
    USING (EXISTS (SELECT 1 FROM public.user_profiles up WHERE up.id = auth.uid() AND up.role = 'admin'))
    WITH CHECK (EXISTS (SELECT 1 FROM public.user_profiles up WHERE up.id = auth.uid() AND up.role = 'admin'));

CREATE POLICY ai_messages_user_select
    ON public.ai_messages FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM public.ai_conversations c
        WHERE c.id = ai_messages.conversation_id AND c.user_id = auth.uid()
    ));

CREATE POLICY ai_messages_admin_all
    ON public.ai_messages FOR ALL
    USING (EXISTS (SELECT 1 FROM public.user_profiles up WHERE up.id = auth.uid() AND up.role = 'admin'))
    WITH CHECK (EXISTS (SELECT 1 FROM public.user_profiles up WHERE up.id = auth.uid() AND up.role = 'admin'));

COMMENT ON TABLE public.ai_conversations IS
    'MT AI conversations, one per chat thread, owned by the user who started it (SB-1143).';
COMMENT ON TABLE public.ai_messages IS
    'MT AI turns: a user row and an assistant row per turn. Non-ok assistant rows record failed turns and are excluded from rebuilt history (SB-1143).';
