"""python -m app.scripts.sync_kb  (runs automatically when the backend container starts)"""

from app.db import SessionLocal
from app.kb.sync import sync_kb

if __name__ == "__main__":
    with SessionLocal() as db:
        synced, embedded = sync_kb(db)
    print(f"KB synced: {synced} documents, {embedded} newly embedded")
