#!/usr/bin/env sh
set -eu

LOOKBACK_DAYS="${1:-7}"
HORIZON_MINUTES="${2:-10}"
TIMEFRAME="${3:-5m}"

curl -fsS "http://127.0.0.1:8100/forecast/scorecard?lookback_days=${LOOKBACK_DAYS}&horizon_minutes=${HORIZON_MINUTES}&timeframe=${TIMEFRAME}"
echo

