#!/usr/bin/env bash
# =============================================================================
# AutoBangumi Development Environment Stop Script
# =============================================================================
# Usage: ./dev-down.sh [options]
#
# Options:
#   --clean    Also remove volumes (fresh start)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

VOLUME_FLAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            VOLUME_FLAG="-v"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}→ Stopping development services...${NC}"
docker compose -f docker-compose.dev.yml down $VOLUME_FLAG

echo -e "${GREEN}✓ Development environment stopped.${NC}"

if [ -n "$VOLUME_FLAG" ]; then
    echo -e "${YELLOW}  (Volumes removed - next start will be fresh)${NC}"
fi
