#!/usr/bin/env sh
set -eu

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
N8N_DIR="${ROOT_DIR}/n8n"

cd "${N8N_DIR}"
mkdir -p data postgres

if [ ! -f .env.trading ]; then
  cp .env.trading.example .env.trading
  echo "Creado n8n/.env.trading desde plantilla. Ajusta secretos antes de live trading."
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  if ! docker compose --env-file .env.trading -f docker-compose.trading.yml up -d --build; then
    if command -v sudo >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
      sudo docker compose --env-file .env.trading -f docker-compose.trading.yml up -d --build
    else
      exit 1
    fi
  fi
elif command -v docker >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
  sudo docker compose --env-file .env.trading -f docker-compose.trading.yml up -d --build
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose --env-file .env.trading -f docker-compose.trading.yml up -d --build
elif command -v sudo >/dev/null 2>&1; then
  sudo docker-compose --env-file .env.trading -f docker-compose.trading.yml up -d --build
else
  exit 1
fi

echo "Stack trading levantado:"
echo "- n8n: http://127.0.0.1:5111"
echo "- strategy_service: http://127.0.0.1:8100/health"
