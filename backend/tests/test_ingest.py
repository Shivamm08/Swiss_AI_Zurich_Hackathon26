from app.ingest import jira_records, ticket_from_jira

RECORD = {
    "Work type": "Incident",
    "Request type": "Machine Created Alert",
    "Summary": "Job failed",
    "Description": "Details",
    "Affected Business or IT Services": ["SimCorp Dimension"],
    "Business Entity": ["France"],
    "Urgency": "highest",
    "Impact": "Low",
    "Priority": "Medium",
    "Created date": "2026-09-18 23:36",
    "Linked issues": ["REP-1"],
    "All Comments": ["a@b.com: hello"],
}


def test_ticket_from_jira_maps_and_normalises():
    t = ticket_from_jira(RECORD, "challenge")
    assert t.affected_service == "SimCorp Dimension"
    assert t.business_entity == "France"
    assert t.urgency == "Highest"
    assert t.linked_issues == ["REP-1"]
    assert t.source_created_at.year == 2026
    assert t.raw is RECORD


def test_jira_records_accepts_both_file_shapes():
    assert jira_records({"records": [RECORD]}) == [RECORD]
    assert jira_records([RECORD]) == [RECORD]
