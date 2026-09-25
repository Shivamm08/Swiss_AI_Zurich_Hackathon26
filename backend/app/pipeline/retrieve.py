"""Retrieval (the "R" in RAG) over kb_documents.

- BM25 keyword scoring always runs (good at exact tokens like MT536, SCD_POS_SYNC).
- When embeddings exist, pgvector cosine search runs too and the two rankings
  are merged with reciprocal rank fusion (hybrid search).
- Only RELEVANT documents are returned, so k is a maximum, not a quota: a document must reach
  RELEVANCE_MIN cosine similarity and be within RELEVANCE_BAND of the best hit. A clear match
  returns 1-2 documents, a broad question more, an unrelated or brand-new problem none.
  Measured with text-embedding-3-small on our knowledge base: tickets with a real precedent and
  on-topic questions 0.47-0.79; a new kind of problem 0.25-0.37 (only loosely related documents);
  off-topic questions below 0.12.
"""

import math
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KbDocument
from app.pipeline import llm
from app.schemas import Evidence, EvidenceKind

_TOKEN = re.compile(r"[a-z0-9_]+")
_RRF_K = 60
RELEVANCE_MIN = 0.40   # below this a document is not about the query
RELEVANCE_BAND = 0.12  # keep only documents close to the best hit


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _bm25(docs: list[KbDocument], query: str, k1: float = 1.5, b: float = 0.75) -> list[tuple[KbDocument, float]]:
    tokenised = [_tokens(f"{d.title} {d.content}") for d in docs]
    if not tokenised:
        return []
    avg_len = sum(len(t) for t in tokenised) / len(tokenised)
    df = Counter(term for toks in tokenised for term in set(toks))
    n = len(docs)
    scored = []
    q_terms = set(_tokens(query))
    for doc, toks in zip(docs, tokenised):
        tf = Counter(toks)
        score = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * len(toks) / avg_len))
        if score > 0:
            scored.append((doc, score))
    return sorted(scored, key=lambda x: x[1], reverse=True)


def embed_query(query: str) -> list[float] | None:
    vectors = llm.embed([query])
    return vectors[0] if vectors else None


def _vector(db: Session, vector: list[float] | None, kinds: list[EvidenceKind] | None, k: int) -> list[KbDocument]:
    if vector is None:
        return []
    stmt = select(KbDocument).where(KbDocument.embedding.is_not(None))
    if kinds:
        stmt = stmt.where(KbDocument.kind.in_(kinds))
    stmt = stmt.order_by(KbDocument.embedding.cosine_distance(vector)).limit(k)
    return list(db.scalars(stmt))


def cosine_similarity(db: Session, vector: list[float] | None, ref_ids: list[str]) -> dict[str, float]:
    """Cosine similarity between the query and the given documents (for retrieval confidence)."""
    if vector is None or not ref_ids:
        return {}
    rows = db.execute(
        select(KbDocument.ref_id, 1 - KbDocument.embedding.cosine_distance(vector))
        .where(KbDocument.ref_id.in_(ref_ids), KbDocument.embedding.is_not(None))
    )
    return {ref: float(sim) for ref, sim in rows}


def relevant(ranked: list[tuple[str, float]], similarity: dict[str, float], min_similarity: float = RELEVANCE_MIN) -> list[tuple[str, float]]:
    """Keep documents that reach the floor AND are close to the best hit, in rank order."""
    best = max(similarity.values(), default=0.0)
    floor = max(min_similarity, best - RELEVANCE_BAND)
    return [(ref, score) for ref, score in ranked if similarity.get(ref, 0.0) >= floor]


def search(
    db: Session,
    query: str,
    k: int = 5,
    kinds: list[EvidenceKind] | None = None,
    query_vector: list[float] | None = None,
    min_similarity: float = RELEVANCE_MIN,
) -> list[Evidence]:
    """Up to `k` relevant documents (possibly none). Without embeddings: keyword ranking only, top k."""
    stmt = select(KbDocument)
    if kinds:
        stmt = stmt.where(KbDocument.kind.in_(kinds))
    docs = list(db.scalars(stmt))

    keyword_ranked = [d for d, _ in _bm25(docs, query)][: k * 3]
    vector = query_vector if query_vector is not None else embed_query(query)
    vector_ranked = _vector(db, vector, kinds, k * 3)

    fused: dict[str, float] = {}
    by_ref: dict[str, KbDocument] = {}
    for ranking in (keyword_ranked, vector_ranked):
        for rank, doc in enumerate(ranking):
            fused[doc.ref_id] = fused.get(doc.ref_id, 0.0) + 1 / (_RRF_K + rank + 1)
            by_ref[doc.ref_id] = doc

    ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)
    similarity: dict[str, float] = {}
    if vector is not None and ranked:
        similarity = cosine_similarity(db, vector, [ref for ref, _ in ranked])
        ranked = relevant(ranked, similarity, min_similarity)
    top = ranked[:k]
    best = top[0][1] if top else 1.0
    return [
        Evidence(
            kind=by_ref[ref].kind,  # type: ignore[arg-type]
            ref_id=ref,
            title=by_ref[ref].title,
            snippet=by_ref[ref].content[:400],
            score=round(score / best, 3),  # normalised: best hit = 1.0
            similarity=round(similarity[ref], 3) if ref in similarity else None,
        )
        for ref, score in top
    ]


def get_document(db: Session, ref_id: str) -> KbDocument | None:
    return db.scalar(select(KbDocument).where(KbDocument.ref_id == ref_id))
