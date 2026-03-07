#!/usr/bin/env sh
set -eu

N8N_DIR="/home/lucy/Escritorio/La Vieja/n8n"
cd "${N8N_DIR}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  if ! docker compose --env-file .env.trading -f docker-compose.trading.yml down; then
    if command -v sudo >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
      sudo docker compose --env-file .env.trading -f docker-compose.trading.yml down
    else
      exit 1
    fi
  fi
elif command -v docker >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
  sudo docker compose --env-file .env.trading -f docker-compose.trading.yml down
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose --env-file .env.trading -f docker-compose.trading.yml down
elif command -v sudo >/dev/null 2>&1; then
  sudo docker-compose --env-file .env.trading -f docker-compose.trading.yml down
else
  exit 1
fi

echo "Stack trading detenido."
