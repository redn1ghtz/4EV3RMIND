#!/bin/bash
# Auto-install 4EV3RMIND for ev3dev

#set -e  # Abort in case of errors

echo "===           Welcome to the 4EV3RMIND installer for ev3dev!           ==="
echo "===                 4EV3RMIND_setup v0.1 by redn1ghtz                  ==="
echo "===                GitHub: https://github.com/redn1ghtz                ==="
echo "===               Installing support for 4EV3RMIND ev3dev              ==="
echo ""

echo "[1/9] Stopping unnecessary ones..."
sudo systemctl stop bluetooth 2>/dev/null || true
sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl stop apache2 2>/dev/null || true
sudo systemctl stop avahi-daemon 2>/dev/null || true
sudo systemctl stop brickman 2>/dev/null || true

echo "[2/9] Installing python3-requests..."
sudo apt install -y python3-requests

echo "[3/9] Installing TTS (Text-to-Speech)..."
sudo apt install -y espeak espeak-data

echo "[4/9] Setting locales..."
sudo apt install -y locales locales-all

echo "[5/9] Setting up the Russian locale..."
# Creating backup
sudo cp /etc/locale.gen /etc/locale.gen.backup
sudo sed -i 's/^# *\(ru_RU\.UTF-8 UTF-8\)/\1/' /etc/locale.gen

# Generating locales
echo "[6/9] Localization generation (may take some time)..."
sudo localedef -i ru_RU -c -f UTF-8 ru_RU.UTF-8

echo "[7/9] Installing system settings..."
sudo update-locale LANG=ru_RU.UTF-8 LC_MESSAGES=ru_RU.UTF-8

echo "[8/9] Setting chmod +x to g_run.sh..."
sudo chmod +x g_run.sh

echo "[9/9] Checking the installation..."
echo "=== Checking locales ==="
locale
echo ""
echo "=== Checking TTS ==="
espeak --voices | grep -i ru || echo "Russian voices not found!"

echo ""
echo "===                       The installation is complete!                       ==="
echo ""
echo "===                   ADD GEMINI API KEY IN google_config.py!                 ==="
echo "=== You can also configure the robot's behavior in the google_config.py file. ==="
echo "===                       Run 4EV3RMIND: sudo ./g_run.sh                      ==="
echo ""
echo "===                          DONE! SYSTEM NOW REBOOT!                         ==="
sudo reboot
