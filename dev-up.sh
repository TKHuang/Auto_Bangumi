#!/usr/bin/env bash
# =============================================================================
# AutoBangumi Development Environment Launcher
# =============================================================================
# Usage: ./dev-up.sh [options]
#
# Options:
#   --build    Force rebuild containers
#   --logs     Follow logs after starting
#   --detach   Run in detached mode (default)
#
# Services:
#   - Backend:     http://localhost:7893 (FastAPI)
#   - WebUI:       http://localhost:5173 (Vite)
#   - qBittorrent: http://localhost:8081 (admin / adminadmin)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
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
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        AutoBangumi Development Environment                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Create required directories
echo -e "${YELLOW}→ Creating development directories...${NC}"
mkdir -p dev-config/backend dev-config/data dev-config/downloads dev-config/qbittorrent
mkdir -p backend/src/config backend/src/data

# Ensure version file exists for dev mode
VERSION_FILE="backend/src/module/__version__.py"
if [ ! -f "$VERSION_FILE" ]; then
    echo -e "${YELLOW}→ Creating version file for development...${NC}"
    echo "VERSION='DEV_VERSION'" > "$VERSION_FILE"
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Start services
echo -e "${YELLOW}→ Starting development services...${NC}"
docker compose -f docker-compose.dev.yml up $DETACH_FLAG $BUILD_FLAG

if [ -n "$DETACH_FLAG" ]; then
    echo ""
    echo -e "${GREEN}✓ Development environment started!${NC}"
    echo ""
    echo -e "${BLUE}Services:${NC}"
    echo -e "  • Backend API:    ${GREEN}http://localhost:7893${NC}"
    echo -e "  • WebUI:          ${GREEN}http://localhost:5173${NC}"
    echo -e "  • qBittorrent:    ${GREEN}http://localhost:8081${NC} (admin / adminadmin)"
    echo ""
    echo -e "${BLUE}Commands:${NC}"
    echo -e "  • View logs:      docker compose -f docker-compose.dev.yml logs -f"
    echo -e "  • Stop all:       ./dev-down.sh"
    echo -e "  • Rebuild:        ./dev-up.sh --build"
    echo ""

    if [ "$LOGS_FLAG" = "true" ]; then
        echo -e "${YELLOW}→ Following logs (Ctrl+C to exit)...${NC}"
        docker compose -f docker-compose.dev.yml logs -f
    fi
fi
