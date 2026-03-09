#!/usr/bin/env sh
set -eu

LIMIT="${1:-20}"
curl -fsS "http://127.0.0.1:8100/execution/intents?status=open&limit=${LIMIT}"
echo
