-- MT AI traces (SB-1197): what each turn did and how long it took.
--
-- ai_tool_calls holds one row per tool call: name, the arguments the model
-- sent, the result it was shown, the error kind if the tool reported one, and
-- how long it ran. Large results are stored as a digest (see mt_ai/trace.py).
-- Together with the turn timings added to ai_messages, this answers "where
-- did the time go" (model vs tools) and lets an eval check the tool
-- trajectory, not just the answer text.
--
-- Retention (decided 2026-10-02): kept until the user is deleted. Rows cascade
-- with their conversation, which cascades from user_profiles. No purge job.
--
-- Written best-effort after the turn is saved: if this migration hasn't
-- reached an environment yet, chat still works and the trace is skipped.

ALTER TABLE public.ai_messages
    ADD COLUMN duration_ms integer CHECK (duration_ms >= 0),
    ADD COLUMN llm_ms integer CHECK (llm_ms >= 0);

COMMENT ON COLUMN public.ai_messages.duration_ms IS
    'Assistant rows: wall time of the whole turn, in ms (SB-1197). NULL before SB-1197 or if not recorded.';
COMMENT ON COLUMN public.ai_messages.llm_ms IS
    'Assistant rows: time spent waiting on the model across the turn''s LLM calls, in ms (SB-1197).';

CREATE TABLE public.ai_tool_calls (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES public.ai_conversations(id) ON DELETE CASCADE,
    turn integer NOT NULL CHECK (turn >= 1),
    seq integer NOT NULL CHECK (seq >= 1),
    tool_name text NOT NULL,
    args jsonb NOT NULL DEFAULT '{}'::jsonb,
    result jsonb,
    error_kind text,
    duration_ms integer CHECK (duration_ms >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ai_tool_calls_turn_seq_unique UNIQUE (conversation_id, turn, seq)
);

CREATE INDEX idx_ai_tool_calls_conversation_turn ON public.ai_tool_calls(conversation_id, turn, seq);

-- Same posture as ai_messages: the backend uses the service key; RLS is
-- defence in depth. Users may read traces of their own conversations; admins
-- everything. (The API serves traces to admins only.)
ALTER TABLE public.ai_tool_calls ENABLE ROW LEVEL SECURITY;

CREATE POLICY ai_tool_calls_user_select
    ON public.ai_tool_calls FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM public.ai_conversations c
        WHERE c.id = ai_tool_calls.conversation_id AND c.user_id = auth.uid()
    ));

CREATE POLICY ai_tool_calls_admin_all
    ON public.ai_tool_calls FOR ALL
    USING (EXISTS (SELECT 1 FROM public.user_profiles up WHERE up.id = auth.uid() AND up.role = 'admin'))
    WITH CHECK (EXISTS (SELECT 1 FROM public.user_profiles up WHERE up.id = auth.uid() AND up.role = 'admin'));

COMMENT ON TABLE public.ai_tool_calls IS
    'MT AI tool calls per turn: name, args, result (or digest), error kind, duration (SB-1197).';
