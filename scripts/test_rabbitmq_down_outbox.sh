#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8001}"
EMAIL="${EMAIL:-rabbit_down_$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-password123}"

function die() {
  echo "ERROR: $*" >&2
  exit 1
}

set -a
if [[ -f ".env" ]]; then
  . .env
fi
set +a

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-order_management}"

echo "BASE_URL=$BASE_URL"
echo "EMAIL=$EMAIL"

echo "1) stop rabbitmq"
docker compose stop rabbitmq >/dev/null

echo "2) register"
curl -fsS -X POST "$BASE_URL/register/" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null
echo "OK"

echo "3) token"
TOKEN="$(
  curl -fsS -X POST "$BASE_URL/token/" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "username=$EMAIL&password=$PASSWORD" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
)"
test -n "$TOKEN" || die "empty token"
echo "OK"

echo "4) create order while rabbitmq is down (API must return 201)"
OUT="$(
  curl -sS -w "\n%{http_code}" -X POST "$BASE_URL/orders/" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"items":[{"product_id":1,"quantity":1,"price":10.0}]}' \
)"
BODY="$(echo "$OUT" | sed '$d')"
CODE="$(echo "$OUT" | tail -n 1)"
if [[ "$CODE" != "201" ]]; then
  echo "$BODY" >&2
  die "expected 201, got $CODE"
fi
ORDER_ID="$(echo "$BODY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
test -n "$ORDER_ID" || die "empty order_id"
echo "ORDER_ID=$ORDER_ID"

echo "5) verify outbox event exists and is pending (DB)"
STATUS="$(
  docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc \
    "SELECT status FROM outbox_events WHERE aggregate_id='$ORDER_ID' ORDER BY id DESC LIMIT 1;"
)"
STATUS="$(echo "$STATUS" | tr -d '[:space:]')"
if [[ "$STATUS" != "PENDING" && "$STATUS" != "PROCESSING" ]]; then
  die "expected outbox status PENDING/PROCESSING while rabbit is down, got '$STATUS'"
fi
echo "OK (status=$STATUS)"

echo "6) start rabbitmq back"
docker compose start rabbitmq >/dev/null

echo "7) wait for consumer/celery to process via existing e2e check"
BASE_URL="$BASE_URL" ./scripts/test_event_flow.sh >/dev/null
echo "OK"

echo "ALL RABBITMQ-DOWN OUTBOX SCENARIO: OK"

