"""Shared configuration for the Apertus-backed triage pipeline.

Endpoint defaults follow the Swiss {ai} Weeks hacker guide. Note the product
path is ``swiss-ai-weeks`` -- the ``swiss-ai-platform`` path in Swisscom's
public docs is a different product that hackathon keys are not entitled to.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR.parent
CACHE_DIR = DATA_DIR / "triage_cache"
OUTPUT_DIR = DATA_DIR / "output"
INPUT_JSON = DATA_DIR / "jira_first_20000_requested_fields_synthetic.json"

API_KEY_ENV = "SWISSCOM_API_KEY"
BASE_URL = os.environ.get(
    "APERTUS_BASE_URL",
    "https://api.swisscom.com/products/swiss-ai-weeks/apertus-1.5-70b/v1",
)
MODEL = os.environ.get("APERTUS_MODEL", "swiss-ai/Apertus-v1.5-70B")

# The hacker guide documents 5 requests/second, but the gateway starts
# returning 429 well below that under sustained load, so we run deliberately
# slower and let the client throttle itself further on any 429.
REQUESTS_PER_SECOND = 2.0
MAX_WORKERS = 2
MAX_RETRIES = 6
REQUEST_TIMEOUT = 180
# Multiplier applied to the request interval each time a 429 comes back.
THROTTLE_FACTOR = 1.6
MIN_REQUESTS_PER_SECOND = 0.2

# Self-consistency: each distinct ticket variant is extracted this many times
# and the per-field majority wins. Odd numbers avoid 50/50 splits.
N_VOTES = 3

# Criticality ratings come from the challenge README. Impact depends on these,
# so they are data, not a heuristic.
CRITICAL_SERVICES = frozenset({
    "Trading Platform",
    "Order Management",
    "Trade Matching",
    "Securities Settlement",
    "Corporate Actions",
    "Fund Pricing",
    "NAV Calculation",
    "Portfolio Accounting",
    "Cash Management",
    "Risk & Compliance Monitoring",
    "Regulatory Reporting",
    "SimCorp Dimension",
    "Rimes Data Feed",
    "Client Reporting",
})
NON_CRITICAL_SERVICES = frozenset({
    "Tax Reporting",
    "CRM & Client Portal",
    "Identity & Access Management",
    "SharePoint & File Storage",
    "Outlook & Email",
    "Emailed Support Tickets",
})

# This bucket is the dataset's generic mis-triage sink. Its ticket text names no
# real service, so criticality is genuinely unrecoverable -- we default it to
# non-critical and flag the row rather than inventing a service.
UNRESOLVABLE_SERVICES = frozenset({"Emailed Support Tickets"})


def load_dotenv(path: Path | None = None) -> None:
    """Populate os.environ from a .env file. Avoids a python-dotenv dependency."""
    env_path = path or (DATA_DIR / ".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def is_critical(service: str) -> bool:
    return service in CRITICAL_SERVICES
