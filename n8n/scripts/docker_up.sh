#!/usr/bin/env bash
set -euo pipefail

cd "/home/lucy/Escritorio/La Vieja/n8n"
sudo mkdir -p data
sudo chown -R 1000:1000 data

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose up -d
elif command -v docker >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
  sudo docker compose up -d
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose up -d
else
  sudo docker-compose up -d
fi

echo "n8n (Docker) levantado en: http://127.0.0.1:5111"
