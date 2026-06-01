# Relay — developer workflow
# Most targets wrap docker-compose in deploy/compose.

COMPOSE := docker compose -f deploy/compose/docker-compose.yml

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

.PHONY: up
up: ## Build and start the full stack
	$(COMPOSE) up --build -d

.PHONY: down
down: ## Stop the stack and remove volumes
	$(COMPOSE) down -v

.PHONY: seed
seed: ## Seed demo assets (assets in interesting lifecycle states)
	$(COMPOSE) exec -T api python -m relay.seed

.PHONY: demo
demo: up ## Start everything and seed demo data, then print the dashboard URL
	@echo "Waiting for the API to become healthy..."
	@until $(COMPOSE) exec -T api python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/healthz')" >/dev/null 2>&1; do sleep 1; done
	@$(MAKE) seed
	@echo ""
	@echo "  Relay is up.  Dashboard:  http://localhost:5173"
	@echo "  API docs (OpenAPI):        http://localhost:8000/docs"
	@echo ""

.PHONY: test
test: ## Run the backend test suite
	cd apps/relay && uv run pytest -q

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Show running services
	$(COMPOSE) ps
