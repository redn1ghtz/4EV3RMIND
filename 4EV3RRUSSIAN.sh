#!/bin/bash
# Auto-install 4EV3RMIND for ev3dev

#set -e  # Abort in case of errors

echo "=== Welcome to the 4EV3RMIND installer for ev3dev! ==="
echo "===                 4EV3RMIND_setup v0.1 by redn1ghtz                  ==="
echo "===                GitHub: https://github.com/redn1ghtz                ==="
echo "===           Installing Russian language support for ev3dev           ==="
echo ""

echo "[1/11] Stopping unnecessary ones..."
sudo systemctl stop bluetooth 2>/dev/null || true
sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl stop apache2 2>/dev/null || true
sudo systemctl stop avahi-daemon 2>/dev/null || true
sudo systemctl stop brickman 2>/dev/null || true

echo "[2/11] Adding repository to sources.list..."
REPO_URL="deb http://archive.debian.org/debian/ stretch main"
# Check if repository already exists
if grep -q "$REPO_URL" /etc/apt/sources.list; then
    echo "Repository already exists in sources.list"
else
    echo "Adding repository: $REPO_URL"
    echo "$REPO_URL" | sudo tee -a /etc/apt/sources.list
    echo "Repository added successfully"
fi

echo "[3/11] Updating the system..."
sudo apt update
sudo apt upgrade -y

echo "[4/11] Setting locales..."
sudo apt install -y locales locales-all

echo "[5/11] Setting up the Russian locale..."
# Creating backup
sudo cp /etc/locale.gen /etc/locale.gen.backup

# Adding the Russian locale
if ! grep -q "ru_RU.UTF-8 UTF-8" /etc/locale.gen; then
    echo "ru_RU.UTF-8 UTF-8" | sudo tee -a /etc/locale.gen
fi

# Generating locales
echo "[6/11] Localization generation (may take some time)..."
sudo locale-gen ru_RU.UTF-8

echo "[7/11] Installing system settings..."
sudo update-locale LANG=ru_RU.UTF-8 LC_MESSAGES=ru_RU.UTF-8

echo "[8/11] Installing python3-requests..."
sudo apt-get install -y python3-requests

echo "[9/11] Installing TTS (Text-to-Speech)..."
sudo apt install -y espeak espeak-data

# Checking for additional Russian dictionaries
echo "[10/11] Search for additional Russian dictionaries..."
if apt-cache show espeak-data-ru &> /dev/null; then
    sudo apt install -y espeak-data-ru
fi

echo "[11/11] Checking the installation..."
echo "=== Checking locales ==="
locale
echo ""
echo "=== Checking TTS ==="
espeak --voices | grep -i ru || echo "Russian voices not found!"

echo ""
echo "=== The installation is complete! ==="
echo ""
echo "DONE! PLEASE REBOOT THE SYSTEM: sudo reboot"