#!/usr/bin/env bash
# Uninstallation script for yt2ipod.

set -e

GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}=== Uninstalling yt2ipod ===${NC}"

# Uninstall via pip
pip uninstall -y yt2ipod

echo -e "${GREEN}[✓] yt2ipod has been successfully uninstalled.${NC}"
