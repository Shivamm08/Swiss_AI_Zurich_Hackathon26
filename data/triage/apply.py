"""Load the corpus, apply the rubric to every row, and write the outputs."""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
from scipy.stats import f_oneway

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


# Field order of the source export, captured on load so the JSON output can be
# written back in exactly the same shape (a drop-in replacement for the input).
SOURCE_FIELDS: list[str] = []

# Fields the pipeline predicts, which therefore get overwritten in the output.
PREDICTED_FIELDS = {
    "Work type": "work_type_pred",
    "Impact": "impact_pred",
    "Urgency": "urgency_pred",
    "Priority": "priority_pred",
}


def load_corpus(path=None) -> pd.DataFrame:
    """Read the synthetic Jira export into a frame with triage-ready facets."""
    source = path or config.INPUT_JSON
    with open(source, "r", encoding="utf-8") as handle:
        records = json.load(handle)

    global SOURCE_FIELDS
    SOURCE_FIELDS = list(records[0].keys()) if records else []

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

    # Soft-factor inputs. "Resolved" is taken from Status rather than from the
    # presence of a date, so an in-progress ticket still ages.
    frame["created_at"] = pd.to_datetime(frame["Created date"], errors="coerce")
    frame["resolved_at"] = pd.to_datetime(frame["Resolution date"], errors="coerce")
    frame["is_resolved"] = frame["Status"].eq("done")
    frame["resolution_days"] = (
        frame["resolved_at"] - frame["created_at"]
    ).dt.total_seconds() / 86400.0
    # Age is measured from the corpus's own horizon so the result is stable and
    # reproducible, rather than drifting with today's date.
    horizon = frame["created_at"].max()
    frame["age_days"] = (horizon - frame["created_at"]).dt.total_seconds() / 86400.0
    frame.loc[frame["is_resolved"], "age_days"] = 0.0
    frame["variant_id"] = [
        variant_id(s, d, svc)
        for s, d, svc in zip(frame["Summary"], frame["Description"], frame["service"])
    ]
    return frame


PEER_KEYS = ["template", "service"]
# Bias-corrected effect size and significance both have to clear the bar.
# Plain eta^2 is NOT usable here: it is inflated by the number of groups, and
# with 173 peer groups pure noise already yields eta^2 ~ 0.0101, so a naive
# 0.01 threshold sits below chance and lets noise straight through.
MIN_EPSILON_SQUARED = 0.01
MAX_P_VALUE = 0.01
MIN_PEER_GROUP = 5


def peer_difficulty(frame: pd.DataFrame) -> tuple[pd.Series | None, float]:
    """Per-ticket difficulty from how long its peer group took to resolve.

    "Peers" are tickets sharing a scenario template and service. Returns the
    normalised 0..1 difficulty per row, or ``None`` when resolution time
    explains too little variance between peer groups to be worth using.
    Returns the bias-corrected effect size alongside it.

    The guard matters: in this synthetic corpus resolution time is a uniform
    random draw, so feeding it in would add fake precision to the ranking. On
    real Jira data -- or the challenge set -- the guard passes and the factor
    activates automatically.
    """
    resolved = frame.dropna(subset=["resolution_days"])
    groups = [
        group["resolution_days"].to_numpy()
        for _, group in resolved.groupby(PEER_KEYS, sort=False)
        if len(group) >= MIN_PEER_GROUP
    ]
    if len(groups) < 2:
        return None, 0.0

    values = np.concatenate(groups)
    n_groups = len(groups)
    n_rows = len(values)
    grand_mean = values.mean()
    between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
    total = float(((values - grand_mean) ** 2).sum())
    if not total or n_rows <= n_groups:
        return None, 0.0

    # epsilon^2 subtracts the variance a random split would produce anyway.
    within_ms = (total - between) / (n_rows - n_groups)
    epsilon_squared = (between - (n_groups - 1) * within_ms) / total
    _, p_value = f_oneway(*groups)

    if epsilon_squared < MIN_EPSILON_SQUARED or p_value > MAX_P_VALUE:
        return None, epsilon_squared

    medians = resolved.groupby(PEER_KEYS)["resolution_days"].median()
    per_row = frame.set_index(PEER_KEYS).index.map(medians)
    series = pd.Series(per_row, index=frame.index, dtype="float64")
    low, high = series.min(), series.max()
    if not np.isfinite(low) or high <= low:
        return None, epsilon_squared
    return (series - low) / (high - low), epsilon_squared


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

    difficulty, eta_squared = peer_difficulty(frame)
    if difficulty is None:
        print(
            f"  difficulty factor OFF: peer resolution time has no usable "
            f"signal (bias-corrected eps^2 = {eta_squared:.5f}); "
            f"its weight is redistributed"
        )
    else:
        print(f"  difficulty factor ON: bias-corrected eps^2 = {eta_squared:.5f}")

    # The categorical verdict depends only on (variant, service), but the score
    # also depends on per-row age and difficulty, so scoring runs per row.
    rows = []
    difficulty_values = (
        difficulty.to_numpy() if difficulty is not None else [None] * len(frame)
    )
    for vid, service, age, resolved, diff in zip(
        frame["variant_id"],
        frame["service"],
        frame["age_days"],
        frame["is_resolved"],
        difficulty_values,
    ):
        payload = per_variant[vid]
        result = rubric.apply_rubric(
            payload["evidence"],
            service,
            age_days=None if pd.isna(age) else float(age),
            resolved=bool(resolved),
            difficulty=None if diff is None or pd.isna(diff) else float(diff),
        )
        result["confidence"] = payload["confidence"]
        for field in (
            "work_type",
            "scope",
            "outage_extent",
            "workaround",
            "regulatory_or_security",
            "deadline_pressure",
        ):
            result[f"ev_{field}"] = payload["evidence"][field]
        rows.append(result)

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
        "work_type_pred",
        "impact_pred",
        "urgency_pred",
        "priority_pred",
        "priority_score",
        "confidence",
        "severity_offset",
        "age_factor",
        "difficulty_factor",
        "combined_offset",
        "age_days",
        "is_resolved",
        "resolution_days",
        "service_is_critical",
        "service_unresolvable",
        "ev_work_type",
        "ev_scope",
        "ev_outage_extent",
        "ev_workaround",
        "ev_regulatory_or_security",
        "ev_deadline_pressure",
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
            work_type=("work_type_pred", "first"),
            critical=("service_is_critical", "first"),
            description=("Description", "first"),
        )
        .reset_index()
        .sort_values("priority_score", ascending=False)
    )
    audit_path = config.OUTPUT_DIR / "decision_audit.csv"
    audit.to_csv(audit_path, index=False)

    signatures_path = config.OUTPUT_DIR / "similarity_signatures.csv"
    signatures.drop(columns=["text"]).to_csv(signatures_path, index=False)

    return {
        "triaged_csv": triaged_path,
        "neighbours": neighbours_path,
        "audit": audit_path,
        "signatures": signatures_path,
    }


def _clean(value):
    """Convert numpy/pandas scalars to JSON-native types, NaN/NaT to None."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if pd.isna(value) else float(value)
    if value is pd.NaT:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def write_json_output(
    frame: pd.DataFrame,
    neighbours: pd.DataFrame,
    path=None,
    indent: int | None = None,
) -> tuple:
    """Write the triaged corpus back in the source export's own JSON shape.

    Every original field is preserved in its original order, with the four
    predicted fields overwritten, so the file is a drop-in replacement for the
    input. Everything the pipeline adds lives under a single ``triage`` key,
    which keeps the original schema clean for anything that consumes it.
    """
    target = path or (config.OUTPUT_DIR / "jira_triaged.json")
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fields = SOURCE_FIELDS or [c for c in frame.columns if c in PREDICTED_FIELDS]

    # Pre-group neighbours once; grouping inside the row loop would be O(n^2).
    by_ticket: dict[str, list] = {}
    for row in neighbours.itertuples(index=False):
        by_ticket.setdefault(row.ticket_id, []).append(
            {
                "rank": int(row.rank),
                "ticket_id": row.neighbour_ticket_id,
                # float32 -> float leaks artefacts like 0.9499999880; round it.
                "similarity": round(float(row.similarity), 4),
                "tie_group_size": int(row.neighbour_tie_group_size),
                "n_with_resolution": int(row.neighbour_n_with_resolution),
            }
        )

    records = []
    for row in frame.to_dict(orient="records"):
        record = {}
        for field in fields:
            source_column = PREDICTED_FIELDS.get(field)
            record[field] = _clean(
                row[source_column] if source_column else row.get(field)
            )

        record["triage"] = {
            "ticket_id": row["ticket_id"],
            "priority_score": _clean(row["priority_score"]),
            "severity_offset": _clean(row["severity_offset"]),
            "age_factor": _clean(row["age_factor"]),
            "difficulty_factor": _clean(row["difficulty_factor"]),
            "combined_offset": _clean(row["combined_offset"]),
            "confidence": _clean(row["confidence"]),
            "service_is_critical": _clean(row["service_is_critical"]),
            "service_unresolvable": _clean(row["service_unresolvable"]),
            "is_resolved": _clean(row["is_resolved"]),
            "age_days": None if pd.isna(row["age_days"]) else round(float(row["age_days"]), 2),
            "evidence": {
                "work_type": _clean(row["ev_work_type"]),
                "scope": _clean(row["ev_scope"]),
                "outage_extent": _clean(row["ev_outage_extent"]),
                "workaround": _clean(row["ev_workaround"]),
                "regulatory_or_security": _clean(row["ev_regulatory_or_security"]),
                "deadline_pressure": _clean(row["ev_deadline_pressure"]),
            },
            "original": {
                # The randomised source values, kept for reference so nothing
                # is lost by the overwrite above.
                field: _clean(row.get(field)) for field in PREDICTED_FIELDS
            },
            "similar_tickets": by_ticket.get(row["ticket_id"], []),
        }
        records.append(record)

    with open(target, "w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=indent)

    return target, len(records)
