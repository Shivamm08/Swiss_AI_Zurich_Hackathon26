# Data

- `jira_first_20000_requested_fields_synthetic.json`: the training set (committed).
- `main.py`: rule-based `priority_mod` from the Urgency x Impact matrix
  (`rules.md`), writes `jira_first_20000_priority_mod.csv`. Runs on its own via
  the `Dockerfile` / `docker-compose.yml` in this folder.
- `raw/`: git-ignored drop zone for other files, e.g. the challenge file:
  `raw/jira_hackathon_blind_eval_challenge_20260923083915-1141.json`

The root docker compose mounts this folder read-only at `/data` in the backend
container, so `make import-challenge` reads
`/data/raw/jira_hackathon_blind_eval_challenge_*.json` and `make build-playbook`
reads `/data/jira_first_20000_requested_fields_synthetic.json`.
