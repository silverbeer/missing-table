"""Model ids → what ADK runs (SB-1315).

`MT_AI_MODEL` stays configuration, never code (mt2/ai.md). A Gemini id is passed to
ADK as-is. An Ollama id (`ollama_chat/<model>`, or `ollama/<model>`) becomes ADK's
`LiteLlm` pointed at a local Ollama server — the "local" profile, for development
and offline evals.

`litellm` is an optional extra (`uv sync --extra local-ai`) and is never in the
prod image. It is pinned exactly: litellm 1.82.7 and 1.82.8 were malicious PyPI
releases (March 2026).
"""

import os

from google.adk.models.base_llm import BaseLlm

OLLAMA_PREFIXES = ("ollama_chat/", "ollama/")
DEFAULT_OLLAMA_API_BASE = "http://127.0.0.1:11434"


class ModelUnavailableError(Exception):
    """The configured model cannot be loaded here. The message is for logs and operators."""


def is_local_model(model_id: str) -> bool:
    return model_id.startswith(OLLAMA_PREFIXES)


def resolve_model(model_id: str) -> BaseLlm | str:
    if not is_local_model(model_id):
        return model_id
    try:
        from google.adk.models.lite_llm import LiteLlm
    except ImportError as exc:
        raise ModelUnavailableError(
            f"{model_id} needs the local-ai extra: cd backend && uv sync --extra local-ai"
        ) from exc
    return LiteLlm(model=model_id, api_base=os.getenv("OLLAMA_API_BASE", DEFAULT_OLLAMA_API_BASE))
