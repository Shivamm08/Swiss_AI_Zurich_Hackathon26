.PHONY: help up up-local down logs contract test migration migrate import-challenge build-playbook seed-demo clear-demo

help: ## List commands
	@grep -E '^[a-z-]+:.*## ' Makefile | sed 's/:.*## /\t/'

up: ## Start the stack against DATABASE_URL in .env (Supabase)
	docker compose up --build --renew-anon-volumes

up-local: ## Start the stack with a local Postgres
	DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/triage docker compose --profile local-db up --build --renew-anon-volumes

down: ## Stop everything
	docker compose --profile local-db down

logs: ## Follow backend logs
	docker compose logs -f backend

contract: ## Regenerate contracts/openapi.json and frontend types (run after any API change)
	docker compose run --rm --no-deps backend python -m app.scripts.export_openapi /contracts/openapi.json
	docker compose run --rm --no-deps frontend npm run gen:api

test: ## Backend tests + frontend lint/build
	docker compose run --rm --no-deps backend pytest -q
	docker compose run --rm --no-deps frontend sh -c 'npm run lint && npm run build'

migration: ## Create a DB migration after editing models.py: make migration m="add x"
	docker compose run --rm backend alembic revision --autogenerate -m "$(m)"

migrate: ## Apply migrations
	docker compose run --rm backend alembic upgrade head

import-challenge: ## Load the 20 challenge tickets into the DB
	docker compose exec backend sh -c 'python -m app.scripts.import_tickets /data/raw/jira_hackathon_blind_eval_challenge_*.json --source challenge'

build-playbook: ## Rebuild the playbook from training data and reload the KB
	docker compose exec backend python -m app.scripts.build_playbook /data/jira_first_20000_requested_fields_synthetic.json
	docker compose exec backend python -m app.scripts.sync_kb

seed-demo: ## (Re)create 4 weeks of SIMULATED desk history for demos (tickets, reviews, chat)
	docker compose exec backend python -m app.scripts.seed_demo

clear-demo: ## Remove the simulated demo history (real tickets are untouched)
	docker compose exec backend python -m app.scripts.seed_demo --clear
