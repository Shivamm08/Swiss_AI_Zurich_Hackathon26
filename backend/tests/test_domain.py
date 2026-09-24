import pytest

from app.domain import LEVELS, SERVICE_CATALOG, SERVICES, TEAMS, normalize_level, priority_for

# (urgency, impact) -> priority, spot checks straight from the README matrix
README_CELLS = [
    ("Highest", "Highest", "Highest"),
    ("Highest", "Lowest", "Medium"),
    ("High", "Lowest", "Low"),
    ("Medium", "Highest", "High"),
    ("Medium", "Medium", "Medium"),
    ("Low", "High", "Medium"),
    ("Low", "Lowest", "Lowest"),
    ("Lowest", "Highest", "Medium"),
    ("Lowest", "High", "Low"),
]


@pytest.mark.parametrize(("urgency", "impact", "expected"), README_CELLS)
def test_priority_matrix(urgency, impact, expected):
    assert priority_for(urgency, impact) == expected


def test_matrix_is_complete():
    for u in LEVELS:
        for i in LEVELS:
            assert priority_for(u, i) in LEVELS


def test_every_service_has_a_known_team():
    assert set(SERVICE_CATALOG) == set(SERVICES)
    assert {team for team, _ in SERVICE_CATALOG.values()} == set(TEAMS)


@pytest.mark.parametrize("raw", ["high", "HIGH", " High "])
def test_normalize_level(raw):
    assert normalize_level(raw) == "High"


def test_normalize_level_rejects_unknown():
    assert normalize_level("urgent") is None
    assert normalize_level(None) is None
