"""Nearest-neighbour retrieval over the ticket corpus.

Pure text similarity is degenerate on this dataset: 64% of rows sit in groups
of 100+ byte-identical tickets (largest group 4,212), so a text-only top-10
returns ten arbitrary rows all scoring 1.000. Similarity is therefore computed
over *facets* of ticket content -- text, service, scenario, work type, team and
entity -- and neighbours are returned one-per-facet-signature so the list is
diverse rather than ten copies of the same ticket.

Nothing here reads Impact, Urgency or Priority: similarity describes what a
ticket *is*, not what was concluded about it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from . import config

# Weights sum to 1.0, so the composite score is directly interpretable on 0..1.
#
# Similarity is deliberately measured on ticket CONTENT only -- it carries no
# priority or severity term. Two reasons:
#   1. Priority is a conclusion drawn about a ticket, not a description of it.
#      Retrieval exists to find precedent for how a problem was handled, and
#      two identical faults are equally good precedent whoever triaged them.
#   2. Keeping it out prevents circularity: similarity can now feed priority
#      reasoning without priority having already fed similarity. It also stops
#      the age term in priority_score leaking in, which would make two
#      identical tickets look less alike purely for being raised months apart.
SIMILARITY_WEIGHTS = {
    "text": 0.35,
    "service": 0.25,
    "template": 0.15,
    "work_type": 0.10,
    "team": 0.10,
    "entity": 0.05,
}

# Partial credit when two different services share a criticality rating.
SERVICE_CLASS_CREDIT = 0.30

TOP_K = 10
SIGNATURE_KEYS = ["template", "service", "entity", "Work type", "team"]


def _equality_matrix(values: pd.Series) -> np.ndarray:
    codes = pd.factorize(values, sort=False)[0]
    return (codes[:, None] == codes[None, :]).astype(np.float32)


def build_signatures(frame: pd.DataFrame) -> pd.DataFrame:
    """Collapse rows to distinct facet signatures, with a representative ticket.

    The representative prefers a ticket that actually documents its resolution,
    because the downstream use is drafting resolution text from precedent.
    """
    work = frame.copy()
    work["_row"] = np.arange(len(work))
    work["_rep_rank"] = (~work["has_resolution_text"]).astype(int)

    ordered = work.sort_values(["_rep_rank", "_row"], kind="stable")
    grouped = ordered.groupby(SIGNATURE_KEYS, sort=False)

    signatures = grouped.agg(
        rep_ticket_id=("ticket_id", "first"),
        tie_group_size=("ticket_id", "size"),
        n_with_resolution=("has_resolution_text", "sum"),
        text=("sim_text", "first"),
        service_is_critical=("service_is_critical", "first"),
    ).reset_index()

    # A ticket's own signature is its best source of precedent, but it must not
    # be offered its own row -- so every signature keeps a spare representative.
    spare = (
        grouped["ticket_id"]
        .apply(lambda s: s.iloc[1] if len(s) > 1 else None)
        .reset_index(name="rep_ticket_id_alt")
    )
    signatures = signatures.merge(spare, on=SIGNATURE_KEYS, how="left")

    signatures["signature_id"] = np.arange(len(signatures))
    return signatures


def similarity_matrix(signatures: pd.DataFrame) -> np.ndarray:
    """Weighted facet similarity between every pair of signatures."""
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2), sublinear_tf=True, min_df=1, strip_accents="unicode"
    )
    tfidf = vectorizer.fit_transform(signatures["text"].tolist())
    text_sim = np.asarray((tfidf @ tfidf.T).todense(), dtype=np.float32)
    np.clip(text_sim, 0.0, 1.0, out=text_sim)

    service_exact = _equality_matrix(signatures["service"])
    critical = signatures["service_is_critical"].to_numpy(dtype=bool)
    same_class = (critical[:, None] == critical[None, :]).astype(np.float32)
    # Exact service match scores 1.0; a different service of the same
    # criticality still carries real triage signal, so it gets partial credit.
    service_sim = np.maximum(service_exact, same_class * SERVICE_CLASS_CREDIT)

    components = {
        "text": text_sim,
        "service": service_sim,
        "template": _equality_matrix(signatures["template"]),
        "work_type": _equality_matrix(signatures["Work type"]),
        "team": _equality_matrix(signatures["team"]),
        "entity": _equality_matrix(signatures["entity"]),
    }

    total = np.zeros_like(text_sim)
    for name, weight in SIMILARITY_WEIGHTS.items():
        total += weight * components[name]
    return np.clip(total, 0.0, 1.0)


def signature_neighbours(signatures: pd.DataFrame, matrix: np.ndarray, top_k: int = TOP_K) -> pd.DataFrame:
    """Top-k neighbouring signatures for each signature, rank 1 = most similar.

    A signature is allowed to match itself: when many byte-identical tickets
    exist, one of them really is the closest precedent. The query ticket is
    swapped out for a sibling row later, in ``attach_neighbours``.
    """
    n = len(signatures)
    k = min(top_k, n)

    scored = matrix.copy()

    # argpartition then sort only the k survivors: O(n^2) instead of O(n^2 log n).
    top_idx = np.argpartition(-scored, kth=k - 1, axis=1)[:, :k]
    rows = np.arange(n)[:, None]
    order = np.argsort(-scored[rows, top_idx], axis=1)
    top_idx = top_idx[rows, order]
    top_sim = scored[rows, top_idx]

    rep = signatures["rep_ticket_id"].to_numpy()
    alt = signatures["rep_ticket_id_alt"].to_numpy()
    ties = signatures["tie_group_size"].to_numpy()
    n_res = signatures["n_with_resolution"].to_numpy()

    return pd.DataFrame(
        {
            "signature_id": np.repeat(signatures["signature_id"].to_numpy(), k),
            "rank": np.tile(np.arange(1, k + 1), n),
            "neighbour_ticket_id": rep[top_idx].ravel(),
            "neighbour_ticket_id_alt": alt[top_idx].ravel(),
            "similarity": np.round(top_sim.ravel(), 4),
            "neighbour_tie_group_size": ties[top_idx].ravel(),
            "neighbour_n_with_resolution": n_res[top_idx].ravel(),
        }
    )


def attach_neighbours(frame: pd.DataFrame, top_k: int = TOP_K) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per-ticket neighbour table, signature table)."""
    signatures = build_signatures(frame)
    matrix = similarity_matrix(signatures)
    sig_neighbours = signature_neighbours(signatures, matrix, top_k)

    row_to_signature = frame.merge(
        signatures[SIGNATURE_KEYS + ["signature_id"]], on=SIGNATURE_KEYS, how="left"
    )[["ticket_id", "signature_id"]]

    per_ticket = row_to_signature.merge(sig_neighbours, on="signature_id", how="left")

    # Where the representative is the querying ticket itself, fall back to the
    # signature's spare row; drop it only if the group has no other member.
    is_self = per_ticket["ticket_id"] == per_ticket["neighbour_ticket_id"]
    per_ticket.loc[is_self, "neighbour_ticket_id"] = per_ticket.loc[
        is_self, "neighbour_ticket_id_alt"
    ]
    per_ticket = per_ticket.dropna(subset=["neighbour_ticket_id"])
    per_ticket = per_ticket[per_ticket["ticket_id"] != per_ticket["neighbour_ticket_id"]]

    per_ticket = per_ticket.drop(columns=["neighbour_ticket_id_alt"])
    # Ranks stay contiguous after any drop so "rank 1" always means "closest".
    per_ticket["rank"] = per_ticket.groupby("ticket_id", sort=False).cumcount() + 1
    return per_ticket.reset_index(drop=True), signatures
