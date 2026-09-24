"""Classify approved services by distance to embedded service labels.

The three predictive fields are embedded independently with FinBERT:
Summary, Description, and Service Team(s). Their normalized embeddings are
combined with a weighted average. The result is compared with an embedding of
each approved service name, and the closest service is selected.
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
DEFAULT_OUTPUT = DATA_DIR / "jira_service_classified.csv"
DEFAULT_MODEL_DIR = DATA_DIR / "service_model"
MODEL_NAME = "ProsusAI/finbert"
TEXT_COLUMNS = ("Summary", "Description", "Service Team(s)")
TARGET_COLUMN = "Affected Business or IT Services"

SERVICE_RATING = {
    "Trading Platform": "Critical",
    "Order Management": "Critical",
    "Trade Matching": "Critical",
    "Securities Settlement": "Critical",
    "Corporate Actions": "Critical",
    "Fund Pricing": "Critical",
    "NAV Calculation": "Critical",
    "Portfolio Accounting": "Critical",
    "Cash Management": "Critical",
    "Risk & Compliance Monitoring": "Critical",
    "Regulatory Reporting": "Critical",
    "SimCorp Dimension": "Critical",
    "Rimes Data Feed": "Critical",
    "Client Reporting": "Critical",
    "Tax Reporting": "Non-Critical",
    "CRM & Client Portal": "Non-Critical",
    "Identity & Access Management": "Non-Critical",
    "SharePoint & File Storage": "Non-Critical",
    "Outlook & Email": "Non-Critical",
    "Emailed Support Tickets": "Non-Critical",
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


def service_target(value: object) -> str:
    """Extract one approved service from the source target field."""
    services = [item.strip() for item in as_text(value).split(" | ") if item.strip()]
    if len(services) != 1 or services[0] not in SERVICE_RATING:
        raise ValueError(f"Target contains an unsupported service value: {value!r}")
    return services[0]


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


def combine_embeddings(
    summary: np.ndarray,
    description: np.ndarray,
    service_team: np.ndarray,
    weights: tuple[float, float, float],
) -> np.ndarray:
    """Weighted-average the three embeddings and normalize the result."""
    if any(weight < 0 for weight in weights) or sum(weights) == 0:
        raise ValueError("Embedding weights must be non-negative and not all zero")
    combined = (
        weights[0] * summary
        + weights[1] * description
        + weights[2] * service_team
    ) / sum(weights)
    norms = np.linalg.norm(combined, axis=1, keepdims=True)
    return combined / np.maximum(norms, 1e-12)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--summary-weight", type=float, default=0.4)
    parser.add_argument("--description-weight", type=float, default=0.4)
    parser.add_argument("--service-team-weight", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    np.random.seed(args.seed)
    data = pd.read_csv(args.input)
    service_team_column = (
        "Service Team(s)" if "Service Team(s)" in data else "Service Team"
    )
    required = {"Summary", "Description", service_team_column, TARGET_COLUMN}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    data["service_target"] = data[TARGET_COLUMN].map(service_target)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading {MODEL_NAME} on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)

    text_data = pd.DataFrame(
        {
            "Summary": data["Summary"].map(as_text),
            "Description": data["Description"].map(as_text),
            "Service Team(s)": data[service_team_column].map(as_text),
        }
    )
    text_embeddings = {
        column: embed_texts(
            text_data[column].tolist(),
            tokenizer,
            model,
            device,
            args.batch_size,
            args.max_length,
        )
        for column in TEXT_COLUMNS
    }
    weights = (
        args.summary_weight,
        args.description_weight,
        args.service_team_weight,
    )
    row_embeddings = combine_embeddings(
        text_embeddings["Summary"],
        text_embeddings["Description"],
        text_embeddings["Service Team(s)"],
        weights,
    )

    service_names = list(SERVICE_RATING)
    service_embeddings = embed_texts(
        service_names, tokenizer, model, device, args.batch_size, args.max_length
    )
    # Both sides are normalized, so dot product is cosine similarity.
    similarities = row_embeddings @ service_embeddings.T
    prediction_indices = similarities.argmax(axis=1)
    predictions = np.array(service_names, dtype=object)[prediction_indices]

    accuracy = accuracy_score(data["service_target"], predictions)
    print(f"Nearest-service accuracy: {accuracy:.4f}")
    print(
        classification_report(
            data["service_target"], predictions, zero_division=0
        )
    )

    output = data.drop(columns=["service_target"]).copy()
    output[TARGET_COLUMN] = predictions
    output["criticality"] = output[TARGET_COLUMN].map(SERVICE_RATING)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)

    args.model_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.model_dir / "service_target_embeddings.npz",
        services=np.array(service_names),
        embeddings=service_embeddings,
    )
    (args.model_dir / "metadata.json").write_text(
        json.dumps(
            {
                "embedding_model": MODEL_NAME,
                "embedded_columns": TEXT_COLUMNS,
                "target_column": TARGET_COLUMN,
                "approved_services": service_names,
                "weights": dict(zip(TEXT_COLUMNS, weights)),
                "similarity": "cosine",
                "rows": len(output),
                "accuracy_against_existing_labels": float(accuracy),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved classified dataset to {args.output}")


if __name__ == "__main__":
    main()
