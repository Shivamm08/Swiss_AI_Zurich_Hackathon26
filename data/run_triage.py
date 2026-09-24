"""End-to-end triage run.

    python run_triage.py                # full pipeline
    python run_triage.py --dry-run      # no API calls; rubric on cached evidence
    python run_triage.py --limit 20     # extract only 20 variants (smoke test)
    python run_triage.py --refresh      # ignore the evidence cache

Needs SWISSCOM_API_KEY in the environment or in data/.env
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

from triage import apply, config, extract, similarity


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="extract only N variants")
    parser.add_argument("--refresh", action="store_true", help="ignore the evidence cache")
    parser.add_argument("--dry-run", action="store_true", help="use cached evidence only")
    parser.add_argument("--top-k", type=int, default=similarity.TOP_K)
    args = parser.parse_args()

    config.load_dotenv()
    started = time.time()

    print("[1/4] Loading corpus")
    frame = apply.load_corpus()
    print(f"  {len(frame):,} tickets")

    print("[2/4] Extracting evidence with Apertus")
    variants = extract.build_variants(frame)
    if args.limit:
        variants = variants[: args.limit]
        keep = {v["variant_id"] for v in variants}
        frame = frame[frame["variant_id"].isin(keep)].reset_index(drop=True)
        print(f"  --limit {args.limit}: {len(frame):,} tickets retained")

    if args.dry_run:
        import json

        cache_path = config.CACHE_DIR / "evidence.json"
        if not cache_path.exists():
            raise SystemExit("--dry-run needs a populated cache; run without it once.")
        evidence = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"  dry run: {len(evidence)} cached variants")
    else:
        evidence = extract.extract_variants(variants, refresh=args.refresh)

    print("[3/4] Applying the deterministic rubric")
    frame = apply.apply_rubric_to_corpus(frame, evidence)
    print(f"  priority mix: {dict(frame['priority_pred'].value_counts())}")
    print(
        f"  priority_score range {frame['priority_score'].min():.3f}"
        f"-{frame['priority_score'].max():.3f}"
        f" | mean confidence {frame['confidence'].mean():.3f}"
    )

    # Work type is NOT randomised in this dataset (only Priority/Urgency/Impact
    # are), so it is the one field with usable ground truth -- which makes it
    # the only honest accuracy check available on the extraction step.
    correct = frame["work_type_pred"].eq(frame["Work type"])
    print(f"  work_type accuracy vs recorded Work type: {correct.mean():.3f}")
    confusion = pd.crosstab(frame["work_type_pred"], frame["Work type"])
    print("  " + confusion.to_string().replace("\n", "\n  "))

    distinct = frame["priority_score"].nunique()
    print(f"  distinct priority_score values: {distinct:,} (was 7 before soft factors)")

    print("[4/4] Building similarity neighbours")
    neighbours, signatures = similarity.attach_neighbours(frame, top_k=args.top_k)
    print(f"  {len(signatures):,} facet signatures | {len(neighbours):,} neighbour rows")
    print(
        f"  similarity range {neighbours['similarity'].min():.3f}"
        f"-{neighbours['similarity'].max():.3f}"
        f" | rank-1 median {neighbours[neighbours['rank'] == 1]['similarity'].median():.3f}"
    )

    paths = apply.write_outputs(frame, neighbours, signatures)
    print(f"\nDone in {time.time() - started:.1f}s")
    for name, path in paths.items():
        print(f"  {name:12s} {path}")


if __name__ == "__main__":
    main()
