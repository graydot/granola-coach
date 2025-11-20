#!/bin/bash

# Granola Meeting Analyzer - Uninstallation Script
# Removes cron job

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Uninstalling Granola Meeting Analyzer...${NC}"

# Remove cron job
if crontab -l 2>/dev/null | grep -q "granola_processor"; then
    echo "Removing cron job..."
    crontab -l 2>/dev/null | grep -v "granola_processor" | grep -v "Granola Meeting Analyzer" | crontab -
    echo -e "${GREEN}✓ Cron job removed${NC}"
else
    echo "No cron job found"
fi

echo ""
echo -e "${GREEN}Uninstallation complete!${NC}"
echo ""
echo "Note: This does not remove:"
echo "  - The project files"
echo "  - Your feedback history in feedback/"
echo "  - Your logs in logs/"
echo ""
echo "To remove everything, delete the project directory"
