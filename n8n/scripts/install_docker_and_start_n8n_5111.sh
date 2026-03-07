#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] Actualizando paquetes..."
sudo apt-get update -y

echo "[2/4] Instalando Docker..."
if ! sudo apt-get install -y docker.io docker-compose-v2; then
  sudo apt-get install -y docker.io docker-compose-plugin
fi

echo "[3/4] Habilitando servicio Docker..."
sudo systemctl enable --now docker

echo "[4/4] Levantando n8n en Docker (puerto 5111)..."
cd "/home/lucy/Escritorio/La Vieja/n8n"
sudo mkdir -p data
sudo chown -R 1000:1000 data
if sudo docker compose version >/dev/null 2>&1; then
  sudo docker compose up -d
else
  sudo docker-compose up -d
fi

echo
echo "Listo. n8n deberia estar en: http://127.0.0.1:5111"
echo "Verificacion rapida:"
echo "  curl -I http://127.0.0.1:5111"
