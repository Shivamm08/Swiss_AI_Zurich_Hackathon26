"""Assign urgency using weighted ticket embeddings and urgency definitions.

The explanatory variables are Summary, Description, Affected Business or IT
Services, Business Entity, and Service Team(s). Their weighted embedding is
compared with the five urgency definitions from the rules table. The nearest
definition determines ``urgency_mod``.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, classification_report
from transformers import AutoModel, AutoTokenizer


DATA_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = DATA_DIR / "jira_first_20000_priority_mod.csv"
DEFAULT_OUTPUT = DATA_DIR / "jira_first_20000_urgency_classified.csv"
DEFAULT_MODEL_DIR = DATA_DIR / "urgency_model"
MODEL_NAME = "ProsusAI/finbert"
TEXT_COLUMNS = (
    "Summary",
    "Description",
    "Affected Business or IT Services",
    "Business Entity",
    "Service Team(s)",
)
TARGET_COLUMN = "Urgency"

# The row labels in the rules table are mapped to the ordinal values used in
# the Jira data. Each prototype contains the definition from the table.
URGENCY_PROTOTYPES = {
    "highest": (
        "Critical urgency: immediate action required to prevent or fix a "
        "regulatory breach, security compromise, or major outage. No workaround."
    ),
    "high": (
        "High urgency: rapid resolution needed within hours to avoid escalation. "
        "A workaround exists but is difficult or time-consuming."
    ),
    "medium": (
        "Medium urgency: important to fix soon, with no immediate operational or "
        "regulatory threat. An easy workaround is available."
    ),
    "low": (
        "Low urgency: handled in the normal workflow without urgent escalation."
    ),
    "lowest": (
        "Lowest urgency: routine or informational request with no effect on "
        "operations or compliance."
    ),
}


def as_text(value: object) -> str:
    """Convert scalar and CSV list representations to text."""
    if isinstance(value, (list, tuple)):
        return " | ".join(str(item) for item in value)
    if value is None or pd.isna(value):
        return "__missing__"
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, (list, tuple)):
            return " | ".join(str(item) for item in parsed)
    return text or "__missing__"


def embed_texts(
    texts: list[str],
    tokenizer: AutoTokenizer,
    model: AutoModel,
    device: torch.device,
    batch_size: int,
    max_length: int,
) -> np.ndarray:
    """Return mean-pooled, L2-normalized FinBERT embeddings."""
    chunks: list[np.ndarray] = []
    model.eval()
    for start in range(0, len(texts), batch_size):
        tokens = tokenizer(
            texts[start : start + batch_size],
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        tokens = {key: value.to(device) for key, value in tokens.items()}
        with torch.inference_mode():
            hidden = model(**tokens).last_hidden_state
        mask = tokens["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
        pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
        normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
        chunks.append(normalized.cpu().numpy().astype(np.float32))
    return np.vstack(chunks)


def weighted_average(embeddings: list[np.ndarray], weights: list[float]) -> np.ndarray:
    if len(embeddings) != len(weights):
        raise ValueError("Each explanatory column must have one embedding weight")
    if any(weight < 0 for weight in weights) or sum(weights) == 0:
        raise ValueError("Embedding weights must be non-negative and not all zero")
    combined = sum(weight * embedding for embedding, weight in zip(embeddings, weights))
    combined /= sum(weights)
    norms = np.linalg.norm(combined, axis=1, keepdims=True)
    return combined / np.maximum(norms, 1e-12)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--summary-weight", type=float, default=0.2)
    parser.add_argument("--description-weight", type=float, default=0.3)
    parser.add_argument("--service-weight", type=float, default=0.2)
    parser.add_argument("--business-entity-weight", type=float, default=0.15)
    parser.add_argument("--service-team-weight", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    np.random.seed(args.seed)
    data = pd.read_csv(args.input)
    service_team_column = (
        "Service Team(s)" if "Service Team(s)" in data else "Service Team"
    )
    source_columns = (
        "Summary",
        "Description",
        "Affected Business or IT Services",
        "Business Entity",
        service_team_column,
    )
    missing = sorted(set(source_columns + (TARGET_COLUMN,)).difference(data.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading {MODEL_NAME} on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)

    text_data = {
        "Summary": data["Summary"].map(as_text).tolist(),
        "Description": data["Description"].map(as_text).tolist(),
        "Affected Business or IT Services": data[
            "Affected Business or IT Services"
        ].map(as_text).tolist(),
        "Business Entity": data["Business Entity"].map(as_text).tolist(),
        "Service Team(s)": data[service_team_column].map(as_text).tolist(),
    }
    embedded = {
        column: embed_texts(
            text_data[column],
            tokenizer,
            model,
            device,
            args.batch_size,
            args.max_length,
        )
        for column in TEXT_COLUMNS
    }
    weights = [
        args.summary_weight,
        args.description_weight,
        args.service_weight,
        args.business_entity_weight,
        args.service_team_weight,
    ]
    row_embeddings = weighted_average(
        [embedded[column] for column in TEXT_COLUMNS], weights
    )

    urgency_labels = list(URGENCY_PROTOTYPES)
    urgency_embeddings = embed_texts(
        list(URGENCY_PROTOTYPES.values()),
        tokenizer,
        model,
        device,
        args.batch_size,
        args.max_length,
    )
    # Normalized vectors make dot product equivalent to cosine similarity.
    similarities = row_embeddings @ urgency_embeddings.T
    predictions = np.array(urgency_labels, dtype=object)[similarities.argmax(axis=1)]

    actual = data[TARGET_COLUMN].map(as_text).str.lower()
    accuracy = accuracy_score(actual, predictions)
    print(f"Nearest-urgency accuracy: {accuracy:.4f}")
    print(classification_report(actual, predictions, zero_division=0))

    output = data.copy()
    output[TARGET_COLUMN] = predictions
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)

    args.model_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.model_dir / "urgency_prototype_embeddings.npz",
        labels=np.array(urgency_labels),
        embeddings=urgency_embeddings,
    )
    (args.model_dir / "metadata.json").write_text(
        json.dumps(
            {
                "embedding_model": MODEL_NAME,
                "embedded_columns": TEXT_COLUMNS,
                "weights": dict(zip(TEXT_COLUMNS, weights)),
                "distance": "cosine distance",
                "urgency_prototypes": URGENCY_PROTOTYPES,
                "rows": len(output),
                "accuracy_against_existing_urgency": float(accuracy),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved urgency-classified dataset to {args.output}")


if __name__ == "__main__":
    main()
