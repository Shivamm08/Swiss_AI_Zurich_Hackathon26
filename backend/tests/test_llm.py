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
