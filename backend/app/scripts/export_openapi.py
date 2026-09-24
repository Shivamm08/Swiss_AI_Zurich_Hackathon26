"""Write the API contract to contracts/openapi.json (no database needed).

    python -m app.scripts.export_openapi ../contracts/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import app

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "../contracts/openapi.json")
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"Wrote {out}")
