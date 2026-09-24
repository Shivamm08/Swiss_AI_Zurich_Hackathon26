"""Load the corpus, apply the rubric to every row, and write the outputs."""

from __future__ import annotations

import json
import re

import pandas as pd

from . import config, rubric
from .extract import variant_id

_AUTHOR = re.compile(r"^[^:]+:\s*")
# The dataset's only genuinely informative comment form. 5,851 comments are
# the bare string "Problem fixed.", which is useless as resolution precedent.
_RESOLUTION_MARKER = "Resolution recorded:"


def _first(value) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    if isinstance(value, str) and value:
        return value
    return "UNKNOWN"


def _has_resolution_text(comments) -> bool:
    if not isinstance(comments, list):
        return False
    return any(_RESOLUTION_MARKER in _AUTHOR.sub("", c) for c in comments)


def load_corpus(path=None) -> pd.DataFrame:
    """Read the synthetic Jira export into a frame with triage-ready facets."""
    source = path or config.INPUT_JSON
    with open(source, "r", encoding="utf-8") as handle:
        records = json.load(handle)

    frame = pd.DataFrame(records)
    # The export carries no issue key, so the row index is the stable id.
    frame.insert(0, "ticket_id", [f"T{i:05d}" for i in range(len(frame))])

    frame["service"] = frame["Affected Business or IT Services"].map(_first)
    frame["entity"] = frame["Business Entity"].map(_first)
    frame["team"] = frame["Service Team(s)"].map(_first)
    frame["template"] = [
        summary.replace(service, "<SVC>")
        for summary, service in zip(frame["Summary"], frame["service"])
    ]
    frame["has_resolution_text"] = frame["All Comments"].map(_has_resolution_text)
    frame["sim_text"] = frame["Summary"].str.cat(frame["Description"], sep=". ")
    frame["variant_id"] = [
        variant_id(s, d, svc)
        for s, d, svc in zip(frame["Summary"], frame["Description"], frame["service"])
    ]
    return frame


def apply_rubric_to_corpus(frame: pd.DataFrame, evidence_cache: dict) -> pd.DataFrame:
    """Join extracted evidence onto every row and run the deterministic rubric.

    Evidence is per-variant, so this is a lookup over 173 results rather than
    20,000 model calls.
    """
    per_variant = dict(evidence_cache)

    missing = sorted(set(frame["variant_id"]) - set(per_variant))
    if missing:
        raise KeyError(
            f"{len(missing)} variants have no extracted evidence "
            f"(first: {missing[:3]}). Re-run extraction."
        )

    rows = []
    # Cache rubric results per (variant, service): the rubric is a pure
    # function of those two, so it runs 173 times, not 20,000.
    memo: dict[tuple[str, str], dict] = {}
    for vid, service in zip(frame["variant_id"], frame["service"]):
        key = (vid, service)
        if key not in memo:
            payload = per_variant[vid]
            result = rubric.apply_rubric(payload["evidence"], service)
            result["confidence"] = payload["confidence"]
            result["evidence_quote"] = payload["evidence"].get("evidence", "")
            for field in (
                "scope",
                "outage_extent",
                "workaround",
                "regulatory_or_security",
                "deadline_pressure",
                "is_request",
            ):
                result[f"ev_{field}"] = payload["evidence"][field]
            memo[key] = result
        rows.append(memo[key])

    return pd.concat([frame.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def write_outputs(frame: pd.DataFrame, neighbours: pd.DataFrame, signatures: pd.DataFrame) -> dict:
    """Write the three deliverables and return their paths."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    main_columns = [
        "ticket_id",
        "Summary",
        "service",
        "entity",
        "team",
        "Work type",
        "impact_pred",
        "urgency_pred",
        "priority_pred",
        "priority_score",
        "confidence",
        "severity_offset",
        "service_is_critical",
        "service_unresolvable",
        "ev_scope",
        "ev_outage_extent",
        "ev_workaround",
        "ev_regulatory_or_security",
        "ev_deadline_pressure",
        "ev_is_request",
        "evidence_quote",
        "Priority",
        "Urgency",
        "Impact",
    ]
    triaged_path = config.OUTPUT_DIR / "jira_triaged.csv"
    # The dataset's own Priority/Urgency/Impact are random by construction.
    # They are carried through for reference only, renamed so nobody mistakes
    # them for a ground truth the predictions should agree with.
    frame[main_columns].rename(
        columns={
            "Priority": "Priority_original_random",
            "Urgency": "Urgency_original_random",
            "Impact": "Impact_original_random",
        }
    ).to_csv(triaged_path, index=False)

    neighbours_path = config.OUTPUT_DIR / "similarity_neighbours.csv"
    neighbours.to_csv(neighbours_path, index=False)

    # Every distinct decision the pipeline can make, on one reviewable page.
    audit = (
        frame.groupby(["template", "service"], sort=False)
        .agg(
            n_rows=("ticket_id", "size"),
            impact=("impact_pred", "first"),
            urgency=("urgency_pred", "first"),
            priority=("priority_pred", "first"),
            priority_score=("priority_score", "first"),
            confidence=("confidence", "first"),
            scope=("ev_scope", "first"),
            outage=("ev_outage_extent", "first"),
            workaround=("ev_workaround", "first"),
            regulatory=("ev_regulatory_or_security", "first"),
            deadline=("ev_deadline_pressure", "first"),
            is_request=("ev_is_request", "first"),
            critical=("service_is_critical", "first"),
        )
        .reset_index()
        .sort_values("priority_score", ascending=False)
    )
    audit_path = config.OUTPUT_DIR / "decision_audit.csv"
    audit.to_csv(audit_path, index=False)

    signatures_path = config.OUTPUT_DIR / "similarity_signatures.csv"
    signatures.drop(columns=["text"]).to_csv(signatures_path, index=False)

    return {
        "triaged": triaged_path,
        "neighbours": neighbours_path,
        "audit": audit_path,
        "signatures": signatures_path,
    }
