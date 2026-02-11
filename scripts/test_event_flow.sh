#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8001}"
COMPOSE_PROJECT_DIR="${COMPOSE_PROJECT_DIR:-.}"

EMAIL="${EMAIL:-event_$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-password123}"

function require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 2; }
}

require_cmd curl
require_cmd python3
require_cmd docker

cd "$COMPOSE_PROJECT_DIR"

echo "BASE_URL=$BASE_URL"
echo "EMAIL=$EMAIL"

echo "1) health"
curl -sS "$BASE_URL/health" >/dev/null
echo "OK"

echo "2) register"
curl -sS -X POST "$BASE_URL/register/" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null
echo "OK"

echo "3) token"
TOKEN="$(curl -sS -X POST "$BASE_URL/token/" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=$EMAIL&password=$PASSWORD" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
echo "OK"

echo "4) create order (should trigger outbox -> rabbitmq -> consumer -> celery)"
ORDER_JSON="$(curl -sS -X POST "$BASE_URL/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":1,"price":10.0}]}' )"
ORDER_ID="$(echo "$ORDER_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "ORDER_ID=$ORDER_ID"

echo "5) wait for celery_worker log: Order processed"
for i in {1..45}; do
  if docker compose logs --no-color --tail 200 celery_worker 2>/dev/null | grep -Fq "Order processed order_id=$ORDER_ID"; then
    echo "OK: celery processed order_id=$ORDER_ID"
    exit 0
  fi
  sleep 1
done

echo "FAILED: did not see celery processing log for order_id=$ORDER_ID" >&2
echo "--- outbox_publisher (tail 200) ---" >&2
docker compose logs --no-color --tail 200 outbox_publisher >&2 || true
echo "--- message_consumer (tail 200) ---" >&2
docker compose logs --no-color --tail 200 message_consumer >&2 || true
echo "--- celery_worker (tail 200) ---" >&2
docker compose logs --no-color --tail 200 celery_worker >&2 || true
exit 1

