#!/usr/bin/env bash
set -euo pipefail

cd "/home/lucy/Escritorio/La Vieja/n8n"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose down
elif command -v docker >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
  sudo docker compose down
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose down
else
  sudo docker-compose down
fi

echo "n8n (Docker) detenido."
