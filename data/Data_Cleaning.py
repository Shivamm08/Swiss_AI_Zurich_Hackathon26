"""Run the complete Jira data-cleaning and classification pipeline.

The classifiers are run in dependency order. Each classifier overwrites the
original target column, so the final dataset contains one value per target and
the derived ``criticality`` column from service classification.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = DATA_DIR / "jira_first_20000_priority_mod.csv"
DEFAULT_OUTPUT = DATA_DIR / "jira_first_20000_cleaned.csv"


def run_classifier(script: str, input_file: Path, output_file: Path, *extra: str) -> None:
    command = [
        sys.executable,
        str(DATA_DIR / script),
        "--input",
        str(input_file),
        "--output",
        str(output_file),
        *extra,
    ]
    print(f"\nRunning {script}...")
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input dataset does not exist: {args.input}")

    with tempfile.TemporaryDirectory(prefix="data_cleaning_", dir=DATA_DIR) as temp:
        temp_dir = Path(temp)
        service_output = temp_dir / "01_service.csv"
        impact_output = temp_dir / "02_impact.csv"
        urgency_output = temp_dir / "03_urgency.csv"
        impact_final_output = temp_dir / "04_impact_final.csv"

        # 1. Predict the service and retain the derived criticality column.
        run_classifier(
            "classify_service.py",
            args.input,
            service_output,
            "--model-dir",
            str(DATA_DIR / "service_model"),
        )

        # 2. Impact uses Description + the newly predicted service.
        run_classifier(
            "classify_impact.py",
            service_output,
            impact_output,
            "--model-dir",
            str(DATA_DIR / "impact_model"),
        )

        # 3. Urgency uses the predicted service and the remaining text fields.
        run_classifier(
            "classify_urgency.py",
            impact_output,
            urgency_output,
            "--model-dir",
            str(DATA_DIR / "urgency_model"),
        )

        # 4. Run the impact classifier again as requested after urgency.
        # It intentionally ignores Urgency and therefore remains deterministic.
        run_classifier(
            "classify_impact.py",
            urgency_output,
            impact_final_output,
            "--model-dir",
            str(DATA_DIR / "impact_model"),
        )

        # 5. Predict Work type and produce the final dataset.
        run_classifier(
            "classify_work_type.py",
            impact_final_output,
            args.output,
            "--output-dir",
            str(DATA_DIR / "work_type_model"),
        )

    # Remove legacy prediction columns if the input was produced by an older
    # version of one of the classifiers. Keep criticality by design.
    final_data = pd.read_csv(args.output)
    legacy_columns = [
        column
        for column in ("it_services_mod", "urgency_mod", "service_target")
        if column in final_data.columns
    ]
    if legacy_columns:
        final_data.drop(columns=legacy_columns).to_csv(args.output, index=False)

    print(f"\nSaved final cleaned dataset to {args.output}")


if __name__ == "__main__":
    main()
