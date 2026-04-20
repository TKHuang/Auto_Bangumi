# =============================================================================
# AutoBangumi Development Makefile
# =============================================================================
# Canonical entrypoint for dev. Never run uvicorn/vite/docker-compose by
# hand — always go through `make`.
#
# Quick start:
#   make dev           start dev stack in background
#   make dev-logs      start and tail logs
#   make down          stop dev stack
#   make clean         stop and wipe named volumes
#   make status        show container state
#   make logs-backend  tail backend logs
# =============================================================================

.PHONY: dev dev-build dev-logs down clean \
        logs logs-backend logs-webui status \
        shell-backend shell-webui \
        test \
        build-ab build-jellyfin-rclone build-all \
        help

.DEFAULT_GOAL := help

# Configurable image names/tags (production build targets)
JELLYFIN_RCLONE_IMAGE ?= jellyfin-rclone
JELLYFIN_RCLONE_TAG   ?= latest
AB_IMAGE              ?= ab
AB_TAG                ?= pikpak

COMPOSE := docker compose -f docker-compose.dev.yml

# ---------------------------------------------------------------------------
# Dev environment
# ---------------------------------------------------------------------------
dev: ## Start dev stack (detached)
	@./dev-up.sh

dev-build: ## Start dev stack, force image rebuild
	@./dev-up.sh --build

dev-logs: ## Start dev stack and follow logs
	@./dev-up.sh --logs

down: ## Stop dev stack
	@./dev-down.sh

clean: ## Stop dev stack and remove named volumes
	@./dev-down.sh --clean

# ---------------------------------------------------------------------------
# Logs / status / shells
# ---------------------------------------------------------------------------
logs: ## Follow all container logs
	$(COMPOSE) logs -f

logs-backend: ## Follow backend logs only
	$(COMPOSE) logs -f backend

logs-webui: ## Follow webui logs only
	$(COMPOSE) logs -f webui

status: ## Show container status
	$(COMPOSE) ps

shell-backend: ## Open shell in backend container
	$(COMPOSE) exec backend bash

shell-webui: ## Open shell in webui container
	$(COMPOSE) exec webui sh

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
test: ## Run backend pytest suite inside the running backend container
	$(COMPOSE) exec backend python -m pytest src/tests -q

# ---------------------------------------------------------------------------
# Production image builds
# ---------------------------------------------------------------------------
build-ab: ## Build AutoBangumi production image
	docker build -f Dockerfile -t $(AB_IMAGE):$(AB_TAG) .

build-jellyfin-rclone: ## Build combined Jellyfin + Rclone image
	docker build -f Dockerfile.jellyfin-rclone -t $(JELLYFIN_RCLONE_IMAGE):$(JELLYFIN_RCLONE_TAG) .

build-all: build-ab build-jellyfin-rclone ## Build all production images

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help: ## Show this help message
	@echo "AutoBangumi development"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  %-18s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "Endpoints:"
	@echo "  Backend  http://localhost:7893"
	@echo "  WebUI    http://localhost:5173"
