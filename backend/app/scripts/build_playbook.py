"""Extract the resolution playbook from the training data.

Only ~21 distinct comments in the 20k training tickets describe a real fix
("Resolution: root cause -> action -> verification"). Each one is always
written by the same person, which we use as the resolver for that pattern.

    python -m app.scripts.build_playbook /data/raw/jira_first_20000_requested_fields_synthetic.json
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app.config import settings


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build(training_path: Path) -> list[dict]:
    tickets = json.loads(training_path.read_text())
    authors: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for t in tickets:
        service = (t.get("Affected Business or IT Services") or [None])[0]
        for comment in t.get("All Comments") or []:
            author, _, body = comment.partition(": ")
            if body.startswith("Resolution:") and service:
                authors[(service, body)][author] += 1

    entries, per_service = [], Counter()
    for (service, note), counter in sorted(authors.items()):
        per_service[service] += 1
        resolver, count = counter.most_common(1)[0]
        entries.append({
            "id": f"pb-{slug(service)}-{per_service[service]}",
            "service": service,
            "note": note,
            "resolver": resolver,
            "occurrences": sum(counter.values()),
            "resolver_share": round(count / sum(counter.values()), 3),
        })
    return entries


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    entries = build(Path(sys.argv[1]))
    out = settings.kb_dir / "playbook.jsonl"
    out.write_text("".join(json.dumps(e) + "\n" for e in entries))
    print(f"Wrote {len(entries)} playbook entries to {out}")


if __name__ == "__main__":
    main()
