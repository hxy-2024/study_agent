.PHONY: infra-up infra-down api-test api-run api-seed-dev api-smoke-local web-install web-dev web-test

infra-up:
	docker compose -f infra/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker-compose.yml down

api-test:
	cd apps/api && uv run pytest -q

api-run:
	cd apps/api && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

api-seed-dev:
	cd apps/api && uv run python -m scripts.seed_dev

api-smoke-local:
	cd apps/api && uv run python -m scripts.smoke_local

web-install:
	cd apps/web && npm install

web-dev:
	cd apps/web && npm run dev -- --host 127.0.0.1 --port 3000

web-test:
	cd apps/web && npm run test
