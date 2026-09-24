from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent
INPUT_FILE = DATA_DIR / "jira_first_20000_requested_fields_synthetic.json"
OUTPUT_FILE = Path(
    os.getenv(
        "OUTPUT_FILE", str(DATA_DIR / "jira_first_20000_priority_mod.csv")
    )
)

# The rules table is indexed by urgency and then impact.
PRIORITY_RULES = {
    "highest": {
        "highest": "highest",
        "high": "highest",
        "medium": "high",
        "low": "medium",
        "lowest": "medium",
    },
    "high": {
        "highest": "highest",
        "high": "high",
        "medium": "high",
        "low": "medium",
        "lowest": "low",
    },
    "medium": {
        "highest": "high",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "lowest": "low",
    },
    "low": {
        "highest": "medium",
        "high": "medium",
        "medium": "low",
        "low": "low",
        "lowest": "lowest",
    },
    "lowest": {
        "highest": "medium",
        "high": "low",
        "medium": "low",
        "low": "lowest",
        "lowest": "lowest",
    },
}

# The source JSON stores both dimensions as ordinal levels. Map those values
# to the labels used by the rules table before looking them up.
URGENCY_LEVELS = {
    "highest": "highest",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "lowest": "lowest",
    "critical": "highest",
}
IMPACT_LEVELS = {
    "highest": "highest",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "lowest": "lowest",
    "major": "highest",
    "significant": "high",
    "moderate": "medium",
    "minor": "low",
    "no direct impact": "lowest",
}


def load_data(input_file: Path = INPUT_FILE) -> pd.DataFrame:
    """Load the JSON records into a pandas DataFrame."""
    with input_file.open("r", encoding="utf-8") as file:
        records = json.load(file)
    return pd.DataFrame(records)


def assign_priority_mod(data: pd.DataFrame) -> pd.DataFrame:
    """Add priority_mod using only the Impact and Urgency columns."""
    required_columns = {"Impact", "Urgency"}
    missing_columns = required_columns.difference(data.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    urgency = (
        data["Urgency"].astype("string").str.strip().str.lower().map(URGENCY_LEVELS)
    )
    impact = (
        data["Impact"].astype("string").str.strip().str.lower().map(IMPACT_LEVELS)
    )

    raw_urgency = data["Urgency"].astype("string").str.strip().str.lower()
    raw_impact = data["Impact"].astype("string").str.strip().str.lower()
    unknown_urgency = sorted(set(raw_urgency.dropna()) - set(URGENCY_LEVELS))
    unknown_impact = sorted(set(raw_impact.dropna()) - set(IMPACT_LEVELS))
    if unknown_urgency or unknown_impact:
        raise ValueError(
            f"Unknown urgency values: {unknown_urgency}; "
            f"unknown impact values: {unknown_impact}"
        )

    result = data.copy()
    result["priority_mod"] = [
        PRIORITY_RULES[urgency_value][impact_value]
        for urgency_value, impact_value in zip(urgency, impact)
    ]
    return result


def preprocess(
    input_file: Path = INPUT_FILE, output_file: Path = OUTPUT_FILE
) -> pd.DataFrame:
    """Load, enrich, and save the preprocessed Jira data."""
    data = assign_priority_mod(load_data(input_file))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_file, index=False)
    return data


if __name__ == "__main__":
    processed_data = preprocess()
    print(f"Processed {len(processed_data):,} rows")
    print(f"Saved to {OUTPUT_FILE}")
