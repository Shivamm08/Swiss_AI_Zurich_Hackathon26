"""Evidence extraction over the distinct ticket variants.

The 20,000 rows collapse to 173 distinct (Summary, Description, Service)
variants, so the whole corpus is covered by 173 x N_VOTES model calls. Results
are cached on disk by content hash, making re-runs free.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config, schema
from .apertus import ApertusClient, ApertusError

VARIANT_KEYS = ["Summary", "Description", "service"]


def variant_id(summary: str, description: str, service: str) -> str:
    digest = hashlib.sha1(
        "\x1f".join([summary, description, service]).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def build_variants(frame) -> list[dict]:
    """Collapse the corpus to its distinct ticket variants."""
    grouped = frame.groupby(VARIANT_KEYS, sort=False).size().reset_index(name="n_rows")
    variants = []
    for row in grouped.itertuples(index=False):
        variants.append(
            {
                "variant_id": variant_id(row.Summary, row.Description, row.service),
                "Summary": row.Summary,
                "Description": row.Description,
                "service": row.service,
                "n_rows": int(row.n_rows),
            }
        )
    return variants


def _majority(values: list) -> tuple[object, float]:
    """Most common value plus the share of votes it won."""
    counts = Counter(values)
    winner, wins = counts.most_common(1)[0]
    return winner, wins / len(values)


def _extract_one(client: ApertusClient, variant: dict) -> dict:
    """N_VOTES samples for one variant, reduced by per-field majority."""
    samples: list[dict] = []
    errors: list[str] = []
    user_prompt = schema.build_user_prompt(
        variant["Summary"], variant["Description"], variant["service"], comments=""
    )

    for vote in range(config.N_VOTES):
        try:
            samples.append(
                client.chat_json(
                    schema.SYSTEM_PROMPT,
                    user_prompt,
                    schema.EVIDENCE_SCHEMA,
                    # Vote 0 is greedy; later votes perturb the seed so
                    # agreement across them is a real stability signal.
                    temperature=0.0 if vote == 0 else 0.3,
                    seed=1000 + vote,
                )
            )
        except ApertusError as exc:
            errors.append(str(exc))

    if not samples:
        raise ApertusError(f"All votes failed for {variant['variant_id']}: {errors}")

    evidence: dict = {}
    agreements: list[float] = []
    for field in schema.VOTED_FIELDS:
        value, share = _majority([s[field] for s in samples])
        evidence[field] = value
        agreements.append(share)

    return {
        "variant_id": variant["variant_id"],
        "evidence": evidence,
        "confidence": round(sum(agreements) / len(agreements), 4),
        "n_votes_ok": len(samples),
        "vote_errors": errors,
    }


def _run_pass(client: ApertusClient, pending: list[dict], cache: dict, cache_path) -> list[dict]:
    """Extract a batch, persisting after each result. Returns what failed.

    The cache is written as results arrive rather than at the end: a rate-limit
    death two thirds of the way through a run must not throw away the work
    already paid for.
    """
    failed: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        futures = {pool.submit(_extract_one, client, v): v for v in pending}
        for future in as_completed(futures):
            variant = futures[future]
            done += 1
            try:
                result = future.result()
            except ApertusError as exc:
                failed.append(variant)
                print(f"\n    ! {variant['variant_id']}: {str(exc)[:110]}")
                continue
            cache[result["variant_id"]] = result
            cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            print(f"    {done}/{len(pending)} variants", end="\r", flush=True)
    print()
    return failed


def extract_variants(variants: list[dict], refresh: bool = False) -> dict[str, dict]:
    """Extract every variant, reusing the on-disk cache where possible."""
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = config.CACHE_DIR / "evidence.json"

    cache: dict[str, dict] = {}
    if cache_path.exists() and not refresh:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    pending = [v for v in variants if v["variant_id"] not in cache]
    print(
        f"  {len(variants)} distinct variants | {len(cache)} cached | "
        f"{len(pending)} to extract ({len(pending) * config.N_VOTES} calls)"
    )
    if not pending:
        return cache

    client = ApertusClient()
    print(f"  healthcheck: {client.healthcheck()}")

    failed = _run_pass(client, pending, cache, cache_path)
    if failed:
        print(f"  retrying {len(failed)} variant(s) after a cool-down")
        time.sleep(30)
        failed = _run_pass(client, failed, cache, cache_path)

    print(f"  cached -> {cache_path} ({len(cache)} variants)")
    if failed:
        ids = ", ".join(v["variant_id"] for v in failed[:5])
        raise ApertusError(
            f"{len(failed)} variant(s) still failing after retry ({ids}). "
            f"Cache holds {len(cache)}; re-run to resume from there."
        )
    return cache
