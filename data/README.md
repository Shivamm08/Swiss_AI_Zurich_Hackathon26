# Data

Training data, the challenge drop zone, and the team's data-science experiments. The app itself
only reads the training set and the challenge file from here; everything else documents the
experiments that shaped it.

## Used by the app

| Path | What | Used by |
|---|---|---|
| `jira_first_20000_requested_fields_synthetic.json` | The 20,000-ticket training set | `make build-playbook` (the 21 real resolution notes), the roster, the simulated demo history |
| `raw/` | Git-ignored drop zone, e.g. `raw/jira_hackathon_blind_eval_challenge_20260923083915-1141.json` | `make import-challenge` |

The root docker compose mounts this folder read-only at `/data` in the backend container.

Priority, urgency, impact, resolution status and assignee in the training set are random, so the
app never learns from them ([why](../docs/wiki/08-Data-and-Database.md)).

## Team experiments (not used by the app)

| Path | What |
|---|---|
| `main.py`, `rules.md`, `criticality.md`, `Dockerfile`, `docker-compose.yml`, `requirement.txt` | Rule-based `priority_mod` from the Urgency × Impact matrix; runs on its own |
| `Data_Cleaning.py`, `data_cleaning_*/` | Data cleaning steps and their intermediate CSVs |
| `classify_service.py`, `classify_urgency.py`, `classify_impact.py`, `classify_work_type.py` | FinBERT embedding classifiers (nearest service / definition, CatBoost for work type) |
| `service_model/`, `urgency_model/`, `impact_model/` | Their stored embeddings and metadata |
| `jira_first_20000_priority_mod.csv`, `jira_service_classified.csv`, `output/` | Outputs of the experiments (including `decision_audit.csv`, `jira_triaged.*`, similarity tables) |
| `triage_cache/` | Cached evidence from an experimental triage run |

Why the app uses an AI reading plus fixed rules instead of these classifiers is explained in
[Triage pipeline → Why not the FinBERT classifiers](../docs/wiki/04-Triage-Pipeline.md#why-not-the-finbert-classifiers-from-the-data-cleaning-branch).

**Never tune prompts, thresholds or models on the 20 challenge tickets.** Their statistics
(Intake & export) are for checking coverage, not for tuning.
