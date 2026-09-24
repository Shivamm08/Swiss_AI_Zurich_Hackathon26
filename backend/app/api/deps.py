from fastapi import HTTPException

from app.pipeline import llm


def validate_model(model: str | None) -> str | None:
    """Reject models that are not offered in /api/llm/models."""
    if model is None or model == llm.HEURISTIC:
        return model
    if model not in llm.available_models():
        raise HTTPException(status_code=400, detail=f"Model '{model}' is not available. See GET /api/llm/models.")
    return model
