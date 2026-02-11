#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8001}"

EMAIL="${EMAIL:-user_$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-password123}"

echo "BASE_URL=$BASE_URL"
echo "EMAIL=$EMAIL"

echo "1) register"
curl -sS -X POST "$BASE_URL/register/" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | tee /tmp/register.json
echo

echo "2) token"
TOKEN="$(curl -sS -X POST "$BASE_URL/token/" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=$EMAIL&password=$PASSWORD" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
echo "TOKEN acquired"

echo "3) create order"
ORDER_JSON="$(curl -sS -X POST "$BASE_URL/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":2,"price":10.0},{"product_id":2,"quantity":1,"price":5.5}]}' )"
echo "$ORDER_JSON" | tee /tmp/order.json
echo

ORDER_ID="$(echo "$ORDER_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
USER_ID="$(echo "$ORDER_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["user_id"])')"

echo "4) get order (should use Redis if enabled)"
curl -sS -X GET "$BASE_URL/orders/$ORDER_ID/" -H "Authorization: Bearer $TOKEN" | tee /tmp/order_get.json
echo

echo "5) patch status -> PAID"
curl -sS -X PATCH "$BASE_URL/orders/$ORDER_ID/" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"status":"PAID"}' | tee /tmp/order_patch.json
echo

echo "6) list user orders"
curl -sS -X GET "$BASE_URL/orders/user/$USER_ID/" -H "Authorization: Bearer $TOKEN" | tee /tmp/orders_list.json
echo

echo "OK"
