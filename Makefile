.PHONY: infra-up infra-down api-test api-run web-install web-dev web-test

infra-up:
	docker compose -f infra/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker-compose.yml down

api-test:
	cd apps/api && uv run pytest -q

api-run:
	cd apps/api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web-install:
	cd apps/web && npm install

web-dev:
	cd apps/web && npm run dev

web-test:
	cd apps/web && npm run test
