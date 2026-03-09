#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/lucy/Escritorio/La Vieja"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-btc_postgres}"
POSTGRES_USER="${POSTGRES_USER:-n8n}"
POSTGRES_DB="${POSTGRES_DB:-n8n}"
SYMBOL="${SYMBOL:-BTCUSD}"
TIMEFRAME="${TIMEFRAME:-5m}"
VENUE="${VENUE:-binance}"
BINANCE_SYMBOL="${BINANCE_SYMBOL:-BTCUSDT}"
CSV_PATH="$(mktemp /tmp/binance_btcusd_5m_backfill_XXXXXX.csv)"
CSV_IN_CONTAINER="/tmp/binance_btcusd_5m_backfill.csv"

START_ISO="${1:-}"
END_ISO="${2:-}"

cd "${ROOT_DIR}"

if [ -z "${START_ISO}" ]; then
  START_ISO="$(docker exec "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At -c "select to_char(min(ts) at time zone 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') from signals where symbol='${SYMBOL}';")"
fi

if [ -z "${END_ISO}" ]; then
  END_ISO="$(docker exec "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At -c "select to_char(min(ts) at time zone 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') from market_candles where symbol='${SYMBOL}' and timeframe='${TIMEFRAME}';")"
fi

if [ -z "${START_ISO}" ] || [ "${START_ISO}" = "" ]; then
  echo "ERROR: no se pudo resolver START_ISO" >&2
  exit 1
fi

if [ -z "${END_ISO}" ] || [ "${END_ISO}" = "" ]; then
  echo "ERROR: no se pudo resolver END_ISO" >&2
  exit 1
fi

python3 - "${CSV_PATH}" "${START_ISO}" "${END_ISO}" "${BINANCE_SYMBOL}" "${VENUE}" "${SYMBOL}" "${TIMEFRAME}" <<'PY'
import csv
import datetime as dt
import json
import sys
import time
import urllib.parse
import urllib.request

csv_path, start_iso, end_iso, binance_symbol, venue, symbol, timeframe = sys.argv[1:8]

def parse_iso(value: str) -> dt.datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)

start_dt = parse_iso(start_iso)
end_dt = parse_iso(end_iso)
if end_dt <= start_dt:
    raise SystemExit(f"Rango invalido: start={start_dt.isoformat()} end={end_dt.isoformat()}")

start_ms = int(start_dt.timestamp() * 1000)
end_ms = int(end_dt.timestamp() * 1000)
step_ms = 5 * 60 * 1000
cursor_ms = start_ms
rows_written = 0
first_ts = None
last_ts = None

with open(csv_path, "w", newline="", encoding="utf-8") as fh:
    writer = csv.writer(fh)
    while cursor_ms < end_ms:
        params = {
            "symbol": binance_symbol,
            "interval": "5m",
            "startTime": str(cursor_ms),
            "endTime": str(end_ms),
            "limit": "1000",
        }
        url = "https://api.binance.com/api/v3/klines?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.load(response)
        if not data:
            break

        for row in data:
            open_ms = int(row[0])
            if open_ms < start_ms or open_ms >= end_ms:
                continue
            ts = dt.datetime.fromtimestamp(open_ms / 1000, tz=dt.timezone.utc).isoformat()
            raw_payload = json.dumps(
                {
                    "provider": "binance",
                    "binance_symbol": binance_symbol,
                    "open_time_ms": open_ms,
                    "close_time_ms": int(row[6]),
                    "trade_count": int(row[8]),
                },
                separators=(",", ":"),
            )
            writer.writerow(
                [
                    ts,
                    venue,
                    symbol,
                    timeframe,
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    raw_payload,
                ]
            )
            rows_written += 1
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        next_cursor = int(data[-1][0]) + step_ms
        if next_cursor <= cursor_ms:
            break
        cursor_ms = next_cursor
        time.sleep(0.05)

print(
    json.dumps(
        {
            "csv_path": csv_path,
            "rows_written": rows_written,
            "start_iso": start_dt.isoformat(),
            "end_iso": end_dt.isoformat(),
            "first_ts": first_ts,
            "last_ts": last_ts,
        },
        ensure_ascii=False,
    )
)
PY

docker cp "${CSV_PATH}" "${POSTGRES_CONTAINER}:${CSV_IN_CONTAINER}"
docker exec "${POSTGRES_CONTAINER}" sh -lc "chmod 644 '${CSV_IN_CONTAINER}'"

before_count="$(docker exec "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At -c "select count(*) from market_candles where venue='${VENUE}' and symbol='${SYMBOL}' and timeframe='${TIMEFRAME}';")"

docker exec "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 -c "
create temp table tmp_market_backfill (
  ts timestamptz,
  venue text,
  symbol text,
  timeframe text,
  open numeric,
  high numeric,
  low numeric,
  close numeric,
  volume numeric,
  raw_payload jsonb
);
copy tmp_market_backfill(ts, venue, symbol, timeframe, open, high, low, close, volume, raw_payload)
from '${CSV_IN_CONTAINER}' with (format csv);
insert into market_candles(ts, venue, symbol, timeframe, open, high, low, close, volume, raw_payload)
select ts, venue, symbol, timeframe, open, high, low, close, volume, coalesce(raw_payload, '{}'::jsonb)
from tmp_market_backfill
on conflict (ts, venue, symbol, timeframe) do update
set open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    volume = excluded.volume,
    raw_payload = excluded.raw_payload,
    updated_at = now();
"

after_count="$(docker exec "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -At -c "select count(*) from market_candles where venue='${VENUE}' and symbol='${SYMBOL}' and timeframe='${TIMEFRAME}';")"

docker exec "${POSTGRES_CONTAINER}" rm -f "${CSV_IN_CONTAINER}" >/dev/null 2>&1 || true
rm -f "${CSV_PATH}"

echo "market_backfill_venue=${VENUE} symbol=${SYMBOL} timeframe=${TIMEFRAME} start=${START_ISO} end=${END_ISO} before=${before_count} after=${after_count}"
