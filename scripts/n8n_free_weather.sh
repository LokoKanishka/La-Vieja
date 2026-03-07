#!/usr/bin/env sh
set -eu

lat="${1:--34.6037}"
lon="${2:--58.3816}"

url="https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&timezone=auto"

if command -v curl >/dev/null 2>&1; then
  curl -sS "${url}"
else
  wget -qO- "${url}"
fi
