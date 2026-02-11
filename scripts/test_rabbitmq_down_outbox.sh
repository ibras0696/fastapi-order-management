#!/usr/bin/env bash
set -euo pipefail

# E2E сценарий: RabbitMQ down -> заказ создаётся, событие не теряется.
#
# Логика:
# - Останавливаем RabbitMQ.
# - Создаём заказ (API должен вернуть 201).
# - Проверяем, что в БД появилась outbox запись со статусом PENDING/PROCESSING.
# - Поднимаем RabbitMQ обратно.
# - Ждём, что outbox publisher доставит событие, consumer прочитает и Celery обработает.
#
# Почему это важно:
# Это закрывает продакшен-сценарий "заказ создан, но событие потеряно".
# Мы запрещаем синхронную публикацию в RabbitMQ внутри HTTP-запроса и используем outbox,
# чтобы при падении брокера API всё равно возвращал успешный ответ, а событие дождалось отправки.

# Параметры можно переопределять:
#   BASE_URL=http://localhost:8001 ./scripts/test_rabbitmq_down_outbox.sh
#   EMAIL=... PASSWORD=... ./scripts/test_rabbitmq_down_outbox.sh
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

# Параметры доступа к Postgres (для проверки outbox напрямую).
# Здесь используем `docker compose exec db psql ...`, поэтому достаточно user/db.
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-order_management}"

echo "BASE_URL=$BASE_URL"
echo "EMAIL=$EMAIL"

# 1) Имитируем недоступность event-bus (RabbitMQ).
# Важно: это именно "инфраструктурный отказ" — API при этом не должен падать.
echo "1) stop rabbitmq"
docker compose stop rabbitmq >/dev/null

# 2–3) Создаём пользователя и получаем токен (JWT).
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

# 4) Создаём заказ.
# Ожидание: событие должно попасть в outbox, а не пытаться синхронно публиковаться в RabbitMQ
# (иначе мы бы получили 500 при недоступном брокере).
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

# 5) Проверяем в БД, что outbox событие действительно создано и ждёт публикации.
# Если тут пусто/FAILED — значит сервис не гарантирует доставку события при падении брокера.
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

# 6) Возвращаем RabbitMQ.
echo "6) start rabbitmq back"
docker compose start rabbitmq >/dev/null

# 7) Ждём, что outbox publisher отправит событие,
# consumer его прочитает и поставит задачу в Celery,
# а Celery worker задачу обработает.
#
# Проверка делается через уже готовый скрипт, который смотрит, что цепочка "outbox -> rabbit -> consumer -> celery"
# отработала (через API/логи).
echo "7) wait for consumer/celery to process via existing e2e check"
BASE_URL="$BASE_URL" ./scripts/test_event_flow.sh >/dev/null
echo "OK"

echo "ALL RABBITMQ-DOWN OUTBOX SCENARIO: OK"
