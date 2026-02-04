# =============================================================================
# AutoBangumi Development Makefile
# =============================================================================
# Usage: make <target>
#
# Quick start:
#   make dev        - Start development environment
#   make down       - Stop development environment
#   make logs       - Follow all logs
# =============================================================================

.PHONY: dev dev-build down logs clean help build-jellyfin-rclone build-ab build-all

# Default target
.DEFAULT_GOAL := help

# Configurable image names/tags
JELLYFIN_RCLONE_IMAGE ?= jellyfin-rclone
JELLYFIN_RCLONE_TAG   ?= latest
AB_IMAGE              ?= ab
AB_TAG                ?= pikpak

# Development environment
dev: ## Start development environment (detached)
	@./dev-up.sh

dev-build: ## Start development environment with rebuild
	@./dev-up.sh --build

dev-logs: ## Start and follow logs
	@./dev-up.sh --logs

down: ## Stop development environment
	@./dev-down.sh

clean: ## Stop and remove all volumes (fresh start)
	@./dev-down.sh --clean

# Logs
logs: ## Follow all container logs
	docker compose -f docker-compose.dev.yml logs -f

logs-backend: ## Follow backend logs only
	docker compose -f docker-compose.dev.yml logs -f backend

logs-webui: ## Follow webui logs only
	docker compose -f docker-compose.dev.yml logs -f webui

logs-qb: ## Follow qBittorrent logs only
	docker compose -f docker-compose.dev.yml logs -f qbittorrent

# Status
status: ## Show container status
	docker compose -f docker-compose.dev.yml ps

# Shell access
shell-backend: ## Open shell in backend container
	docker compose -f docker-compose.dev.yml exec backend bash

shell-webui: ## Open shell in webui container
	docker compose -f docker-compose.dev.yml exec webui sh

# Production image builds
build-jellyfin-rclone: ## Build combined Jellyfin + Rclone image
	docker build -f Dockerfile.jellyfin-rclone -t $(JELLYFIN_RCLONE_IMAGE):$(JELLYFIN_RCLONE_TAG) .

build-ab: ## Build AutoBangumi image
	docker build -f Dockerfile -t $(AB_IMAGE):$(AB_TAG) .

build-all: build-ab build-jellyfin-rclone ## Build all production images

# Help
help: ## Show this help message
	@echo "AutoBangumi Development Commands"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  %-15s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "Services:"
	@echo "  Backend:     http://localhost:7893"
	@echo "  WebUI:       http://localhost:5173"
	@echo "  qBittorrent: http://localhost:8081 (admin/adminadmin)"
