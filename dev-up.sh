#!/usr/bin/env bash
# =============================================================================
# AutoBangumi Development Environment Launcher
# =============================================================================
# Invoked by `make dev` / `make dev-build` / `make dev-logs`. The Makefile
# is the canonical entrypoint — prefer `make` targets over invoking this
# script directly.
#
# Options:
#   --build      Force rebuild of images before starting
#   --logs       Follow logs after services come up
#   --no-detach  Run in the foreground (blocks the terminal)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BUILD_FLAG=""
LOGS_FLAG=""
DETACH_FLAG="-d"

while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD_FLAG="--build"
            shift
            ;;
        --logs)
            LOGS_FLAG="true"
            shift
            ;;
        --no-detach)
            DETACH_FLAG=""
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            exit 1
            ;;
    esac
done

echo -e "${BLUE}── AutoBangumi dev environment ──────────────────────────────${NC}"

# Ensure host-side bind-mount targets exist before compose attempts mounts.
echo -e "${YELLOW}→ Ensuring dev-config dirs exist...${NC}"
mkdir -p dev-config/backend dev-config/data dev-config/downloads

# The backend imports module.__version__ at startup; write a placeholder
# only when absent so a committed version file (release builds) is not
# overwritten.
VERSION_FILE="backend/src/module/__version__.py"
if [ ! -f "$VERSION_FILE" ]; then
    echo -e "${YELLOW}→ Writing dev version marker: ${VERSION_FILE}${NC}"
    echo "VERSION='DEV_VERSION'" > "$VERSION_FILE"
fi

if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running. Start Docker Desktop and retry.${NC}" >&2
    exit 1
fi

echo -e "${YELLOW}→ Starting services...${NC}"
docker compose -f docker-compose.dev.yml up ${DETACH_FLAG} ${BUILD_FLAG}

if [ -n "$DETACH_FLAG" ]; then
    echo ""
    echo -e "${GREEN}✓ Development environment ready.${NC}"
    echo ""
    echo -e "${BLUE}Endpoints:${NC}"
    echo -e "  Backend  ${GREEN}http://localhost:7893${NC}"
    echo -e "  WebUI    ${GREEN}http://localhost:5173${NC}"
    echo ""
    echo -e "${BLUE}Common commands:${NC}"
    echo -e "  make logs-backend    follow backend logs"
    echo -e "  make logs-webui      follow webui logs"
    echo -e "  make shell-backend   open shell in backend container"
    echo -e "  make down            stop everything"
    echo -e "  make clean           stop and wipe named volumes"
    echo ""

    if [ "$LOGS_FLAG" = "true" ]; then
        echo -e "${YELLOW}→ Following logs (Ctrl+C to detach)...${NC}"
        docker compose -f docker-compose.dev.yml logs -f
    fi
fi
