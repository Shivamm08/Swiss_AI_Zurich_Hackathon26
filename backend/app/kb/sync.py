"""Load the versioned KB files (services.yaml, playbook.jsonl) into kb_documents.

The files in git are the source of truth; the table is a searchable copy with
embeddings. Safe to re-run: rows are upserted by ref_id.
"""

import json

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain import SERVICE_CATALOG
from app.models import KbDocument, User
from app.pipeline import llm


def _service_cards() -> list[dict]:
    cards = yaml.safe_load((settings.kb_dir / "services.yaml").read_text()) or []
    docs = []
    for card in cards:
        team, criticality = SERVICE_CATALOG[card["name"]]
        content = (
            f"{card['name']} (team: {team}, {criticality}). {card.get('description', '')} "
            f"Keywords: {', '.join(card.get('keywords', []))}. {card.get('not_this', '')}"
        )
        docs.append({
            "kind": "service_card",
            "ref_id": f"svc-{card['name'].lower().replace(' & ', '-').replace(' ', '-')}",
            "title": card["name"],
            "content": content.strip(),
            "meta": {"team": team, "criticality": criticality, **card},
        })
    return docs


def _playbook() -> list[dict]:
    path = settings.kb_dir / "playbook.jsonl"
    if not path.exists():
        return []
    docs = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        docs.append({
            "kind": "playbook",
            "ref_id": entry["id"],
            "title": f"{entry['service']}: {entry['note'].removeprefix('Resolution: ')[:90]}",
            "content": f"Service: {entry['service']}. {entry['note']}",
            "meta": entry,
        })
    return docs


def sync_kb(db: Session) -> tuple[int, int]:
    docs = _service_cards() + _playbook()
    existing = {d.ref_id: d for d in db.scalars(select(KbDocument))}
    changed: list[KbDocument] = []
    for doc in docs:
        row = existing.get(doc["ref_id"])
        if row is None:
            row = KbDocument(**doc)
            db.add(row)
            changed.append(row)
        elif row.content != doc["content"] or row.meta != doc["meta"] or row.title != doc["title"]:
            row.title, row.content, row.meta = doc["title"], doc["content"], doc["meta"]
            row.embedding = None
            changed.append(row)

    to_embed = [r for r in list(existing.values()) + changed if r.embedding is None]
    embedded = 0
    if to_embed and settings.embeddings_configured:
        vectors = llm.embed([r.content for r in to_embed]) or []
        for row, vector in zip(to_embed, vectors):
            row.embedding = vector
            embedded += 1
    db.commit()
    return len(docs), embedded


def sync_roster(db: Session) -> int:
    """Upsert kb/roster.yaml into the users table (people added in the DB are kept)."""
    path = settings.kb_dir / "roster.yaml"
    if not path.exists():
        return 0
    people = yaml.safe_load(path.read_text()) or []
    for person in people:
        user = db.get(User, person["email"]) or User(email=person["email"])
        user.name = person["name"]
        user.role = person.get("role", "analyst")
        user.teams = person.get("teams", [])
        user.capacity = person.get("capacity", settings.default_capacity)
        db.add(user)
    db.commit()
    return len(people)
