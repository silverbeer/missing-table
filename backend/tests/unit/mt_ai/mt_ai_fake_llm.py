"""A scripted model and an in-memory conversation store for MT AI tests (SB-1143).

`ScriptedLlm` is a real ADK `BaseLlm`: the ADK runner, tool dispatch and
callbacks all run for real, and only the network call to a provider is
replaced by a script. That is what lets the tests prove the wiring
(agent → search_teams → typed result → agent) without a live model.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types


def calls_tool(name: str, **args: Any) -> LlmResponse:
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    return LlmResponse(content=types.Content(role="model", parts=[part]))


def says(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


class ModelDown(Exception):
    pass


class ScriptedLlm(BaseLlm):
    """Replies with the next scripted response; records every request it gets."""

    model: str = "scripted-test-model"
    script: list[Any] = []
    requests: list[Any] = []

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse]:
        self.requests.append(llm_request)
        if not self.script:
            raise AssertionError("ScriptedLlm ran out of script — the agent made an unexpected call")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        yield step

    # --- what the tests inspect -------------------------------------------------

    def tool_results(self) -> list[dict]:
        """Every function_response the model was shown, in order."""
        out = []
        for request in self.requests:
            for content in request.contents:
                for part in content.parts or []:
                    if part.function_response:
                        out.append(part.function_response.response)
        return out

    def declared_tools(self) -> dict[str, Any]:
        config = self.requests[0].config
        return {
            decl.name: decl.parameters_json_schema or decl.parameters
            for tool in (config.tools or [])
            for decl in (tool.function_declarations or [])
        }

    def texts_seen(self, request_index: int = 0) -> list[tuple[str, str]]:
        return [(c.role, p.text) for c in self.requests[request_index].contents for p in c.parts or [] if p.text]


def scripted(*steps: Any) -> ScriptedLlm:
    return ScriptedLlm(script=list(steps), requests=[])


class InMemoryStore:
    """ConversationStore double, with switches to make each operation fail."""

    def __init__(self) -> None:
        self.conversations: dict[str, dict] = {}
        self.messages: list[dict] = []
        self.fail_create = self.fail_get = self.fail_save = False

    def create_conversation(self, user_id: str, agent_version: str) -> dict:
        if self.fail_create:
            raise RuntimeError("insert failed")
        conv = {"id": str(uuid.uuid4()), "user_id": user_id, "agent_version": agent_version}
        self.conversations[conv["id"]] = conv
        return conv

    def get_conversation(self, conversation_id: str, user_id: str) -> dict | None:
        if self.fail_get:
            raise RuntimeError("select failed")
        conv = self.conversations.get(conversation_id)
        return conv if conv and conv["user_id"] == user_id else None

    def list_messages(self, conversation_id: str) -> list[dict]:
        return sorted(
            (m for m in self.messages if m["conversation_id"] == conversation_id),
            key=lambda m: (m["turn"], m["role"] != "user"),
        )

    def add_turn(self, conversation_id: str, turn: int, user_row: dict, assistant_row: dict) -> None:
        if self.fail_save:
            raise RuntimeError("insert failed")
        self.messages.append({**user_row, "conversation_id": conversation_id, "turn": turn, "role": "user"})
        self.messages.append({**assistant_row, "conversation_id": conversation_id, "turn": turn, "role": "assistant"})

    def turns(self, conversation_id: str) -> list[tuple[int, str, str | None, str | None]]:
        return [(m["turn"], m["role"], m.get("status"), m.get("content")) for m in self.list_messages(conversation_id)]
