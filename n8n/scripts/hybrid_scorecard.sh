#!/usr/bin/env sh
set -eu

LOOKBACK_DAYS="${1:-7}"
MODE="${2:-shadow}"
HORIZON_MINUTES="${3:-10}"
TIMEFRAME="${4:-5m}"

curl -fsS "http://127.0.0.1:8100/hybrid/scorecard?lookback_days=${LOOKBACK_DAYS}&mode=${MODE}&horizon_minutes=${HORIZON_MINUTES}&timeframe=${TIMEFRAME}"
echo

