"""Domain constants from the challenge README.

Single source of truth for enums, the service catalogue and the
Urgency x Impact -> Priority matrix. The API schemas (and therefore the
generated frontend types) are built from these Literals, so changing a value
here changes it everywhere after `make contract`.
"""

from typing import Literal, get_args

Level = Literal["Highest", "High", "Medium", "Low", "Lowest"]
WorkType = Literal["Incident", "Service Request"]
Resolution = Literal["done", "cancelled", "clarification", "cannot reproduce"]
Criticality = Literal["Critical", "Non-Critical"]

ServiceName = Literal[
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
    "Tax Reporting",
    "CRM & Client Portal",
    "Identity & Access Management",
    "SharePoint & File Storage",
    "Outlook & Email",
    "Emailed Support Tickets",
]

TeamName = Literal[
    "Service Desk",
    "Enterprise Applications",
    "Investment Operations",
    "Securities Operations",
    "Risk & Controls",
    "Valuation & Pricing",
    "Client Services",
    "Market Data Services",
    "Trading Support",
    "Tax & Reporting",
    "Treasury & Cash",
]

LEVELS: tuple[Level, ...] = get_args(Level)
WORK_TYPES: tuple[WorkType, ...] = get_args(WorkType)
RESOLUTIONS: tuple[Resolution, ...] = get_args(Resolution)
SERVICES: tuple[ServiceName, ...] = get_args(ServiceName)
TEAMS: tuple[TeamName, ...] = get_args(TeamName)

# Service -> (owning team, criticality). Team mapping is 100% consistent in the
# 20k training set; criticality comes from the README's critical service list.
SERVICE_CATALOG: dict[ServiceName, tuple[TeamName, Criticality]] = {
    "Trading Platform": ("Investment Operations", "Critical"),
    "Order Management": ("Trading Support", "Critical"),
    "Trade Matching": ("Investment Operations", "Critical"),
    "Securities Settlement": ("Securities Operations", "Critical"),
    "Corporate Actions": ("Securities Operations", "Critical"),
    "Fund Pricing": ("Valuation & Pricing", "Critical"),
    "NAV Calculation": ("Valuation & Pricing", "Critical"),
    "Portfolio Accounting": ("Investment Operations", "Critical"),
    "Cash Management": ("Treasury & Cash", "Critical"),
    "Risk & Compliance Monitoring": ("Risk & Controls", "Critical"),
    "Regulatory Reporting": ("Risk & Controls", "Critical"),
    "SimCorp Dimension": ("Enterprise Applications", "Critical"),
    "Rimes Data Feed": ("Market Data Services", "Critical"),
    "Client Reporting": ("Client Services", "Critical"),
    "Tax Reporting": ("Tax & Reporting", "Non-Critical"),
    "CRM & Client Portal": ("Client Services", "Non-Critical"),
    "Identity & Access Management": ("Enterprise Applications", "Non-Critical"),
    "SharePoint & File Storage": ("Enterprise Applications", "Non-Critical"),
    "Outlook & Email": ("Enterprise Applications", "Non-Critical"),
    "Emailed Support Tickets": ("Service Desk", "Non-Critical"),
}

# Ticket field values map onto the matrix's row/column names in order.
URGENCY_LABELS: dict[Level, str] = {
    "Highest": "Critical",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
    "Lowest": "Lowest",
}
IMPACT_LABELS: dict[Level, str] = {
    "Highest": "Major / Widespread",
    "High": "Significant / Large",
    "Medium": "Moderate / Limited",
    "Low": "Minor / Localized",
    "Lowest": "No direct impact / Information",
}

# Rows are urgency, columns are impact (Highest -> Lowest), copied from the README.
_MATRIX_ROWS: dict[Level, tuple[Level, Level, Level, Level, Level]] = {
    "Highest": ("Highest", "Highest", "High", "Medium", "Medium"),
    "High": ("Highest", "High", "High", "Medium", "Low"),
    "Medium": ("High", "High", "Medium", "Low", "Low"),
    "Low": ("Medium", "Medium", "Low", "Low", "Lowest"),
    "Lowest": ("Medium", "Low", "Low", "Lowest", "Lowest"),
}
PRIORITY_MATRIX: dict[Level, dict[Level, Level]] = {
    urgency: dict(zip(LEVELS, row)) for urgency, row in _MATRIX_ROWS.items()
}


def normalize_level(value: str | None) -> Level | None:
    """'high' / 'HIGH' / 'High' -> 'High'. Training data is lower-case, challenge is title-case."""
    if not value:
        return None
    for level in LEVELS:
        if level.lower() == value.strip().lower():
            return level
    return None


def priority_for(urgency: Level, impact: Level) -> Level:
    return PRIORITY_MATRIX[urgency][impact]


def team_for(service: ServiceName) -> TeamName:
    return SERVICE_CATALOG[service][0]


def as_service(value: str | None) -> ServiceName | None:
    return value if value in SERVICE_CATALOG else None  # type: ignore[return-value]
