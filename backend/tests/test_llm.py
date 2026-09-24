import pytest
from fastapi import HTTPException

from app.api.deps import validate_model
from app.config import settings
from app.pipeline import llm


@pytest.fixture
def openai_choices(monkeypatch):
    monkeypatch.setattr(settings, "azure_openai_endpoint", None)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "openai_chat_model", None)
    monkeypatch.setattr(settings, "llm_model_choices", "model-a, model-b")
    monkeypatch.setattr(settings, "apertus_api_key", None)
    llm.available_models.cache_clear()
    yield
    llm.available_models.cache_clear()


def test_default_model_is_first_choice(openai_choices):
    assert settings.chat_model == "model-a"
    assert llm.resolve_model(None) == "model-a"


def test_requested_model_and_heuristic(openai_choices):
    assert llm.resolve_model("model-b") == "model-b"
    assert llm.resolve_model("heuristic") is None


def test_validate_model(openai_choices):
    assert validate_model("model-b") == "model-b"
    assert validate_model("heuristic") == "heuristic"
    assert validate_model(None) is None
    with pytest.raises(HTTPException) as err:
        validate_model("not-offered")
    assert err.value.status_code == 400


def test_apertus_is_offered_and_routed(openai_choices, monkeypatch):
    monkeypatch.setattr(settings, "apertus_api_key", "test-key")
    llm.available_models.cache_clear()
    llm.get_apertus_client.cache_clear()
    options = {m.id: m.provider for m in llm.available_models()}
    assert options == {"model-a": "openai", "model-b": "openai", settings.apertus_model: "apertus"}
    assert validate_model(settings.apertus_model) == settings.apertus_model
    assert llm._client_for(settings.apertus_model)[1] == "apertus"
    assert llm._client_for("model-a")[1] == "openai"
    llm.get_apertus_client.cache_clear()
