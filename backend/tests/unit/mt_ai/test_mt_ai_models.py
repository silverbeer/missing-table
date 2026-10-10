"""mt_ai.models (SB-1315): model id → what ADK runs."""

import builtins

import pytest

from mt_ai.models import DEFAULT_OLLAMA_API_BASE, ModelUnavailableError, is_local_model, resolve_model

pytestmark = [pytest.mark.unit, pytest.mark.backend]


@pytest.mark.parametrize("model_id", ["gemini-3.7-flash", "gemini-2.5-pro"])
def test_a_gemini_id_passes_through_unchanged(model_id):
    assert resolve_model(model_id) == model_id
    assert not is_local_model(model_id)


@pytest.mark.parametrize("model_id", ["ollama_chat/gemma4:12b", "ollama/llama3.3"])
def test_an_ollama_id_becomes_litellm_at_the_local_server(model_id, monkeypatch):
    pytest.importorskip("litellm")  # the local-ai extra
    monkeypatch.delenv("OLLAMA_API_BASE", raising=False)

    model = resolve_model(model_id)

    assert model.model == model_id
    assert model._additional_args["api_base"] == DEFAULT_OLLAMA_API_BASE


def test_the_ollama_server_is_configurable(monkeypatch):
    pytest.importorskip("litellm")
    monkeypatch.setenv("OLLAMA_API_BASE", "http://mac-mini.local:11434")

    assert resolve_model("ollama_chat/llama3.3")._additional_args["api_base"] == "http://mac-mini.local:11434"


def test_without_the_extra_the_error_says_how_to_install_it(monkeypatch):
    real_import = builtins.__import__

    def no_litellm(name, *args, **kwargs):
        if name == "google.adk.models.lite_llm":
            raise ImportError("No module named 'litellm'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_litellm)

    with pytest.raises(ModelUnavailableError, match="local-ai"):
        resolve_model("ollama_chat/gemma4:12b")
