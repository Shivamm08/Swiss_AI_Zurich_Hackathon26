# Data

- `jira_first_20000_requested_fields_synthetic.json`: the 20,000-ticket training set (committed).
  It's used to build the resolution playbook (`make build-playbook`), the roster and the simulated
  demo history. Priority, urgency, impact, resolution status and assignee in it are random, so
  they're never learned from ([why](../docs/wiki/08-Data-and-Database.md)).
- `main.py`, `rules.md`, `Dockerfile`, `docker-compose.yml`: a teammate's rule-based `priority_mod`
  from the Urgency × Impact matrix, writes `jira_first_20000_priority_mod.csv`. Runs on its own.
- `raw/`: git-ignored drop zone, e.g. the challenge file
  `raw/jira_hackathon_blind_eval_challenge_20260923083915-1141.json`.

The root docker compose mounts this folder read-only at `/data` in the backend container, so
`make import-challenge` reads `/data/raw/jira_hackathon_blind_eval_challenge_*.json` and
`make build-playbook` reads `/data/jira_first_20000_requested_fields_synthetic.json`.

**Never tune prompts, thresholds or models on the 20 challenge tickets.** Their statistics
(Intake & export) are for checking coverage, not for tuning.
