"""Import a Jira export into the tickets table.

    python -m app.scripts.import_tickets /data/raw/<challenge file>.json --source challenge
    python -m app.scripts.import_tickets /data/raw/<training file>.json --source training --limit 200
"""

import argparse
import json
from pathlib import Path

from app.db import SessionLocal
from app.ingest import jira_records, ticket_from_jira


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--source", default="challenge", choices=["challenge", "training", "manual", "email"])
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    records = jira_records(json.loads(args.path.read_text()))[: args.limit]
    with SessionLocal() as db:
        db.add_all(ticket_from_jira(r, args.source) for r in records)
        db.commit()
    print(f"Imported {len(records)} tickets as source={args.source}")


if __name__ == "__main__":
    main()
