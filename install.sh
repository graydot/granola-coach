#!/bin/bash

# Granola Meeting Analyzer - Installation Script
# Adds daily cron job to run at 5 PM

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Installing Granola Meeting Analyzer...${NC}"

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Project directory: $PROJECT_DIR"

# Find uv executable
UV_PATH=$(which uv 2>/dev/null || echo "")
if [ -z "$UV_PATH" ]; then
    echo -e "${RED}Error: uv not found. Please install uv first:${NC}"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "Found uv at: $UV_PATH"

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Please create .env from .env.example and configure your API keys"
    echo "  cp .env.example .env"
    echo "  # Edit .env with your keys"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
cd "$PROJECT_DIR"
uv sync

# Create cron job entry (runs at 5 PM daily)
CRON_CMD="0 17 * * * cd $PROJECT_DIR && $UV_PATH run python analyze_meetings.py >> $PROJECT_DIR/logs/cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "granola_processor"; then
    echo -e "${YELLOW}Cron job already exists. Updating...${NC}"
    # Remove old job and add new one
    (crontab -l 2>/dev/null | grep -v "granola_processor"; echo "# Granola Meeting Analyzer"; echo "$CRON_CMD") | crontab -
else
    # Add new job
    (crontab -l 2>/dev/null; echo ""; echo "# Granola Meeting Analyzer"; echo "$CRON_CMD") | crontab -
fi

echo -e "${GREEN}✓ Installation complete!${NC}"
echo ""
echo "Daily analysis will run at 5:00 PM"
echo "Logs will be saved to: $PROJECT_DIR/logs/cron.log"
echo ""
echo "To test manually, run:"
echo "  uv run python analyze_meetings.py"
echo ""
echo "To uninstall, run:"
echo "  ./uninstall.sh"
