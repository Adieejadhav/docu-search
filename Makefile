COMPOSE := docker compose --env-file .env.docker

.PHONY: help build run build-run logs logs-backend logs-frontend logs-postgres

help:
	@echo "Docu Search Docker commands"
	@echo ""
	@echo "Build:"
	@echo "  make build"
	@echo "    docker compose --env-file .env.docker build"
	@echo ""
	@echo "Run:"
	@echo "  make run"
	@echo "    docker compose --env-file .env.docker up"
	@echo ""
	@echo "Build and run:"
	@echo "  make build-run"
	@echo "    docker compose --env-file .env.docker up --build"
	@echo ""
	@echo "Logs:"
	@echo "  make logs"
	@echo "    docker compose --env-file .env.docker logs -f"
	@echo ""
	@echo "  make logs-backend"
	@echo "    docker compose --env-file .env.docker logs -f backend"
	@echo ""
	@echo "  make logs-frontend"
	@echo "    docker compose --env-file .env.docker logs -f frontend"
	@echo ""
	@echo "  make logs-postgres"
	@echo "    docker compose --env-file .env.docker logs -f postgres"
	@echo ""

build:
	$(COMPOSE) build

run:
	$(COMPOSE) up

build-run:
	$(COMPOSE) up --build

logs:
	$(COMPOSE) logs -f

logs-backend:
	$(COMPOSE) logs -f backend

logs-frontend:
	$(COMPOSE) logs -f frontend

logs-postgres:
	$(COMPOSE) logs -f postgres
