#!/bin/bash

# Auto upgrade system

echo "===         Welcome to the 4EV3RMIND PRE-installer for ev3dev!         ==="
echo "===                 4EV3RMIND_setup v0.1 by redn1ghtz                  ==="
echo "===                GitHub: https://github.com/redn1ghtz                ==="
echo "===             PRE-installing support for 4EV3RMIND ev3dev            ==="
echo ""

echo "[1/4] Adding a repository..."
REPO_URL="deb http://archive.debian.org/debian/ stretch main"
# Check if repository already exists
if grep -q "$REPO_URL" /etc/apt/sources.list; then
    echo "Repository already exists in sources.list"
else
    echo "Adding repository: $REPO_URL"
    echo "$REPO_URL" | sudo tee -a /etc/apt/sources.list
    echo "Repository added successfully"
fi
echo "[2/4] System upgrade..."
sudo apt update
sudo apt upgrade -y

echo "[3/4] Setting chmod +x to install.sh..."
sudo chmod +x install.sh

echo "[4/4] Done! System reboot..."
echo ""
echo "After reboot, run: sudo ./install.sh"
sudo reboot