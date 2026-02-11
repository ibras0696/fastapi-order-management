#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8001}"

EMAIL1="${EMAIL1:-user1_$(date +%s)@example.com}"
EMAIL2="${EMAIL2:-user2_$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-password123}"

function curl_json() {
  # Args: method url json_data [extra_headers...]
  local method="$1"; shift
  local url="$1"; shift
  local data="$1"; shift
  curl -sS -X "$method" "$url" \
    -H 'Content-Type: application/json' \
    "$@" \
    -d "$data"
}

function curl_form() {
  # Args: url form_data [extra_headers...]
  local url="$1"; shift
  local data="$1"; shift
  curl -sS -X POST "$url" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    "$@" \
    -d "$data"
}

function expect_status() {
  # Args: expected_code method url [data] [headers...]
  local expected="$1"; shift
  local method="$1"; shift
  local url="$1"; shift

  local out
  if [[ "$method" == "POST_JSON" ]]; then
    local data="${1:-}"; shift || true
    out="$(curl -sS -w "\n%{http_code}" -X POST "$url" -H 'Content-Type: application/json' "$@" -d "$data")"
  elif [[ "$method" == "PATCH_JSON" ]]; then
    local data="${1:-}"; shift || true
    out="$(curl -sS -w "\n%{http_code}" -X PATCH "$url" -H 'Content-Type: application/json' "$@" -d "$data")"
  elif [[ "$method" == "GET" ]]; then
    out="$(curl -sS -w "\n%{http_code}" -X GET "$url" "$@")"
  elif [[ "$method" == "OPTIONS" ]]; then
    out="$(curl -sS -D - -o /dev/null -w "\n%{http_code}" -X OPTIONS "$url" "$@")"
  else
    echo "Unknown method: $method" >&2
    exit 2
  fi

  local body code
  body="$(echo "$out" | sed '$d')"
  code="$(echo "$out" | tail -n 1)"

  if [[ "$code" != "$expected" ]]; then
    echo "FAILED: expected HTTP $expected, got $code for $method $url" >&2
    echo "Response body/headers:" >&2
    echo "$body" >&2
    exit 1
  fi

  echo "$body"
}

function py_get() {
  # Args: json key
  local key="$1"
  python3 -c "import json,sys; print(json.load(sys.stdin)[$key])"
}

echo "BASE_URL=$BASE_URL"
echo "EMAIL1=$EMAIL1"
echo "EMAIL2=$EMAIL2"

echo
echo "== Health =="
expect_status 200 GET "$BASE_URL/health" >/dev/null
echo "OK"

echo
echo "== CORS preflight (positive) =="
expect_status 200 OPTIONS "$BASE_URL/orders/" \
  -H "Origin: http://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: authorization,content-type" >/dev/null
echo "OK"

echo
echo "== Auth negative =="
expect_status 422 POST_JSON "$BASE_URL/register/" '{"email":"not-an-email","password":"password123"}' >/dev/null
expect_status 422 POST_JSON "$BASE_URL/register/" '{"email":"user@example.com","password":"123"}' >/dev/null
expect_status 422 POST_JSON "$BASE_URL/token/" '{}' >/dev/null
echo "OK"

echo
echo "== Register two users =="
USER1_JSON="$(expect_status 201 POST_JSON "$BASE_URL/register/" "{\"email\":\"$EMAIL1\",\"password\":\"$PASSWORD\"}")"
USER2_JSON="$(expect_status 201 POST_JSON "$BASE_URL/register/" "{\"email\":\"$EMAIL2\",\"password\":\"$PASSWORD\"}")"
USER1_ID="$(echo "$USER1_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
USER2_ID="$(echo "$USER2_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "USER1_ID=$USER1_ID USER2_ID=$USER2_ID"

echo
echo "== Register duplicate email (negative) =="
expect_status 400 POST_JSON "$BASE_URL/register/" "{\"email\":\"$EMAIL1\",\"password\":\"$PASSWORD\"}" >/dev/null
echo "OK"

echo
echo "== Token (positive/negative) =="
TOKEN1="$(curl_form "$BASE_URL/token/" "username=$EMAIL1&password=$PASSWORD" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
TOKEN2="$(curl_form "$BASE_URL/token/" "username=$EMAIL2&password=$PASSWORD" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
BAD_TOKEN_CODE="$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/token/" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "username=$EMAIL1&password=wrong-password")"
if [[ "$BAD_TOKEN_CODE" != "401" ]]; then
  echo "FAILED: expected HTTP 401 for wrong password, got $BAD_TOKEN_CODE" >&2
  exit 1
fi
echo "OK"

AUTH1=(-H "Authorization: Bearer $TOKEN1")
AUTH2=(-H "Authorization: Bearer $TOKEN2")

echo
echo "== Orders negative validation/authorization =="
expect_status 401 POST_JSON "$BASE_URL/orders/" '{"items":[{"product_id":1,"quantity":1,"price":10.0}]}' >/dev/null
expect_status 422 POST_JSON "$BASE_URL/orders/" '{"items":[]}' "${AUTH1[@]}" >/dev/null
expect_status 422 POST_JSON "$BASE_URL/orders/" '{"items":[{"product_id":1,"quantity":0,"price":10.0}]}' "${AUTH1[@]}" >/dev/null
expect_status 422 POST_JSON "$BASE_URL/orders/" '{"items":[{"product_id":1,"quantity":1,"price":0}]}' "${AUTH1[@]}" >/dev/null
echo "OK"

echo
echo "== Orders happy path =="
ORDER_JSON="$(expect_status 201 POST_JSON "$BASE_URL/orders/" \
  '{"items":[{"product_id":1,"quantity":2,"price":10.0},{"product_id":2,"quantity":1,"price":5.5}]}' \
  "${AUTH1[@]}")"
ORDER_ID="$(echo "$ORDER_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "ORDER_ID=$ORDER_ID"

echo
echo "== Get order (positive) + cache path (2nd GET) =="
expect_status 200 GET "$BASE_URL/orders/$ORDER_ID/" "${AUTH1[@]}" >/dev/null
expect_status 200 GET "$BASE_URL/orders/$ORDER_ID/" "${AUTH1[@]}" >/dev/null
echo "OK"

echo
echo "== Get order forbidden / not found =="
expect_status 403 GET "$BASE_URL/orders/$ORDER_ID/" "${AUTH2[@]}" >/dev/null
expect_status 404 GET "$BASE_URL/orders/00000000-0000-0000-0000-000000000000/" "${AUTH1[@]}" >/dev/null
echo "OK"

echo
echo "== Patch status negative/positive =="
expect_status 422 PATCH_JSON "$BASE_URL/orders/$ORDER_ID/" '{"status":"NOT_A_STATUS"}' "${AUTH1[@]}" >/dev/null
expect_status 403 PATCH_JSON "$BASE_URL/orders/$ORDER_ID/" '{"status":"PAID"}' "${AUTH2[@]}" >/dev/null
expect_status 200 PATCH_JSON "$BASE_URL/orders/$ORDER_ID/" '{"status":"PAID"}' "${AUTH1[@]}" >/dev/null
echo "OK"

echo
echo "== List user orders positive/forbidden =="
expect_status 200 GET "$BASE_URL/orders/user/$USER1_ID/" "${AUTH1[@]}" >/dev/null
expect_status 403 GET "$BASE_URL/orders/user/$USER1_ID/" "${AUTH2[@]}" >/dev/null
echo "OK"

echo
echo "ALL CURL SCENARIOS: OK"
