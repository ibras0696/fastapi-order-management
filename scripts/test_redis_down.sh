#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8001}"
EMAIL="${EMAIL:-redis_down_$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-password123}"

function die() {
  echo "ERROR: $*" >&2
  exit 1
}

echo "BASE_URL=$BASE_URL"
echo "EMAIL=$EMAIL"

echo "1) health"
curl -fsS "$BASE_URL/health" >/dev/null
echo "OK"

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

echo "4) create order"
ORDER_JSON="$(
  curl -fsS -X POST "$BASE_URL/orders/" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"items":[{"product_id":1,"quantity":1,"price":10.0}]}' \
)"
ORDER_ID="$(echo "$ORDER_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
test -n "$ORDER_ID" || die "empty order_id"
echo "ORDER_ID=$ORDER_ID"

echo "5) stop redis"
docker compose stop redis >/dev/null

echo "6) GET order (must fallback to DB and return 200)"
CODE="$(
  curl -sS -o /tmp/order_get_redis_down.json -w "%{http_code}" \
    -X GET "$BASE_URL/orders/$ORDER_ID/" \
    -H "Authorization: Bearer $TOKEN"
)"
if [[ "$CODE" != "200" ]]; then
  echo "Response:" >&2
  cat /tmp/order_get_redis_down.json >&2 || true
  die "expected 200 while Redis is down, got $CODE"
fi
echo "OK"

echo "7) start redis back"
docker compose start redis >/dev/null

echo "ALL REDIS-DOWN SCENARIO: OK"

