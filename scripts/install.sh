#!/usr/bin/env bash
# Installation script for yt2ipod.
# Detects OS and checks for system dependencies, then installs python package.

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Installing yt2ipod ===${NC}"

# 1. Detect OS
OS="$(uname -s)"
DISTRO=""
if [ -f /etc/os-release ]; then
    DISTRO=$(awk -F= '/^ID=/{print $2}' /etc/os-release | tr -d '"')
fi

# 2. Check and suggest package managers
suggest_install() {
    local dep=$1
    echo -e "${YELLOW}[!] Missing dependency: $dep${NC}"
    if [ "$OS" = "Darwin" ]; then
        echo "  To install: brew install $dep"
    elif [ "$DISTRO" = "ubuntu" ] || [ "$DISTRO" = "debian" ]; then
        if [ "$dep" = "iproxy" ] || [ "$dep" = "ifuse" ]; then
            echo "  To install: sudo apt-get install libimobiledevice-utils ifuse"
        else
            echo "  To install: sudo apt-get install $dep"
        fi
    elif [ "$DISTRO" = "arch" ]; then
        if [ "$dep" = "iproxy" ]; then
            echo "  To install: sudo pacman -S libimobiledevice"
        else
            echo "  To install: sudo pacman -S $dep"
        fi
    elif [ -n "$TERMUX_VERSION" ]; then
        if [ "$dep" = "iproxy" ] || [ "$dep" = "ifuse" ]; then
            echo "  Note: $dep might require custom build or specific repository on Termux."
        else
            echo "  To install: pkg install $dep"
        fi
    else
        echo "  Please install $dep using your system's package manager."
    fi
}

DEPS=("ffmpeg" "ffprobe" "yt-dlp" "iproxy" "ifuse")
for dep in "${DEPS[@]}"; do
    if ! command -v "$dep" &> /dev/null; then
        suggest_install "$dep"
    else
        echo -e "${GREEN}[✓] $dep is installed.${NC}"
    fi
done

# 3. Pip installation
echo -e "\n${GREEN}[*] Installing python package...${NC}"
if [ -n "$VIRTUAL_ENV" ]; then
    echo -e "${GREEN}[✓] Active virtual environment detected. Installing inside it.${NC}"
    pip install -e ".[tui]"
else
    # Suggest user to use virtual env or install with --user
    echo -e "${YELLOW}[!] No active virtualenv detected. Installing in user site packages.${NC}"
    pip install --user -e ".[tui]"
fi

echo -e "\n${GREEN}[✓] Installation completed successfully!${NC}"
echo "You can now run yt2ipod CLI using:"
echo "  yt2ipod --help"
