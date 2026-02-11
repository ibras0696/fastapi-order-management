#!/usr/bin/env bash
set -euo pipefail

# E2E сценарий: Redis down -> API не падает (fallback на БД).
#
# Проверяет ключевое требование: кеш должен быть best-effort.
# При недоступности Redis GET /orders/{id} должен вернуть 200 из PostgreSQL.
#
# Как читать сценарий:
# - Шаги 1–4: создаём пользователя, получаем JWT и создаём заказ (в норме он кешируется в Redis).
# - Шаги 5–6: принудительно останавливаем Redis и проверяем, что чтение заказа всё равно работает (из БД).
# - Шаг 7: возвращаем Redis обратно, чтобы не ломать последующие проверки/CI.

# Базовые параметры.
# Их можно переопределить при запуске:
#   BASE_URL=http://localhost:8001 ./scripts/test_redis_down.sh
#   EMAIL=... PASSWORD=... ./scripts/test_redis_down.sh
BASE_URL="${BASE_URL:-http://localhost:8001}"
EMAIL="${EMAIL:-redis_down_$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-password123}"

function die() {
  echo "ERROR: $*" >&2
  exit 1
}

echo "BASE_URL=$BASE_URL"
echo "EMAIL=$EMAIL"

# 1) Простой smoke: проверяем, что API живой
echo "1) health"
curl -fsS "$BASE_URL/health" >/dev/null
echo "OK"

# 2) Создаём пользователя
echo "2) register"
curl -fsS -X POST "$BASE_URL/register/" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" >/dev/null
echo "OK"

# 3) Получаем JWT (логин)
echo "3) token"
TOKEN="$(
  curl -fsS -X POST "$BASE_URL/token/" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "username=$EMAIL&password=$PASSWORD" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
)"
test -n "$TOKEN" || die "empty token"
echo "OK"

# 4) Создаём заказ.
# В нормальном режиме сервис дополнительно пишет заказ в Redis (как кеш).
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

# 5) Имитируем падение Redis.
# Важно: это не должно "ронять" API (никаких 500 из-за кеша).
echo "5) stop redis"
docker compose stop redis >/dev/null

# 6) Читаем заказ снова.
# Ожидание: ответ 200 и валидный JSON (fallback на PostgreSQL).
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

# 7) Поднимаем Redis обратно (чтобы не ломать остальные сценарии/CI).
echo "7) start redis back"
docker compose start redis >/dev/null

echo "ALL REDIS-DOWN SCENARIO: OK"
