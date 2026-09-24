import json
from pathlib import Path

from app.main import app

CONTRACT = Path(__file__).parents[2] / "contracts" / "openapi.json"


def test_contract_file_is_up_to_date():
    """Fails when schemas/routes changed but `make contract` was not run."""
    assert CONTRACT.exists(), "Run `make contract`"
    assert json.loads(CONTRACT.read_text()) == json.loads(json.dumps(app.openapi())), "Run `make contract`"
