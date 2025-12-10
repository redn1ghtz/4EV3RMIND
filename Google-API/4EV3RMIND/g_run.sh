#!/bin/bash
echo "Остановка ненужных служб для оптимизации..."

sudo systemctl stop bluetooth 2>/dev/null || true
sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl stop apache2 2>/dev/null || true
sudo systemctl stop avahi-daemon 2>/dev/null || true
sudo systemctl stop brickman 2>/dev/null || true

echo "Запуск робота..."

python3 google_4EV3RMIND.py