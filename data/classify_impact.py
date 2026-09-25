"""Assign Impact using weighted description/service embeddings and impact rules.

For each ticket, the Description and Affected Business or IT Services embeddings are combined.
That representation is compared with the five embedded impact definitions from
rules.md. The nearest definition determines the Impact value.
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
DEFAULT_OUTPUT = DATA_DIR / "jira_first_20000_impact_classified.csv"
DEFAULT_MODEL_DIR = DATA_DIR / "impact_model"
MODEL_NAME = "ProsusAI/finbert"
TEXT_COLUMNS = ("Description", "Affected Business or IT Services")

# The output labels match the ordinal labels used by the Jira dataset.
IMPACT_PROTOTYPES = {
    "highest": (
        "Major / Widespread impact: full unavailability of critical IT services "
        "supporting key operations, including more than two hours of downtime."
    ),
    "high": (
        "Significant / Large impact: partial unavailability of critical IT services, "
        "one or more business entities affected, or financial counterparties affected."
    ),
    "medium": (
        "Moderate / Limited impact: full unavailability of non-critical IT services "
        "or up to one business entity affected."
    ),
    "low": (
        "Minor / Localized impact: partial unavailability of non-critical IT services "
        "or only individual users affected."
    ),
    "lowest": (
        "No direct impact / Information: no direct operational impact, informational "
        "request, or maintenance without service degradation."
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


def weighted_average(
    description: np.ndarray, service: np.ndarray, weights: tuple[float, float]
) -> np.ndarray:
    if any(weight < 0 for weight in weights) or sum(weights) == 0:
        raise ValueError("Embedding weights must be non-negative and not all zero")
    combined = (weights[0] * description + weights[1] * service) / sum(weights)
    norms = np.linalg.norm(combined, axis=1, keepdims=True)
    return combined / np.maximum(norms, 1e-12)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--description-weight", type=float, default=0.7)
    parser.add_argument("--service-weight", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    np.random.seed(args.seed)
    data = pd.read_csv(args.input)
    service_column = "Affected Business or IT Services"
    required = set(TEXT_COLUMNS) | {"Impact"}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading {MODEL_NAME} on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)

    description_embeddings = embed_texts(
        data["Description"].map(as_text).tolist(),
        tokenizer,
        model,
        device,
        args.batch_size,
        args.max_length,
    )
    service_embeddings = embed_texts(
        data[service_column].map(as_text).tolist(),
        tokenizer,
        model,
        device,
        args.batch_size,
        args.max_length,
    )
    row_embeddings = weighted_average(
        description_embeddings,
        service_embeddings,
        (args.description_weight, args.service_weight),
    )

    impact_labels = list(IMPACT_PROTOTYPES)
    impact_embeddings = embed_texts(
        list(IMPACT_PROTOTYPES.values()),
        tokenizer,
        model,
        device,
        args.batch_size,
        args.max_length,
    )
    # Normalized vectors make dot product equivalent to cosine similarity.
    similarities = row_embeddings @ impact_embeddings.T
    predictions = np.array(impact_labels, dtype=object)[similarities.argmax(axis=1)]

    actual = data["Impact"].map(as_text).str.lower()
    accuracy = accuracy_score(actual, predictions)
    print(f"Nearest-impact accuracy: {accuracy:.4f}")
    print(classification_report(actual, predictions, zero_division=0))

    output = data.copy()
    output["Impact"] = predictions
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)

    args.model_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.model_dir / "impact_prototype_embeddings.npz",
        labels=np.array(impact_labels),
        embeddings=impact_embeddings,
    )
    (args.model_dir / "metadata.json").write_text(
        json.dumps(
            {
                "embedding_model": MODEL_NAME,
                "embedded_columns": list(TEXT_COLUMNS),
                "weights": {
                    "Description": args.description_weight,
                    "Affected Business or IT Services": args.service_weight,
                },
                "distance": "cosine distance",
                "impact_prototypes": IMPACT_PROTOTYPES,
                "rows": len(output),
                "accuracy_against_existing_impact": float(accuracy),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved impact-classified dataset to {args.output}")


if __name__ == "__main__":
    main()
