#!/usr/bin/env bash
set -euo pipefail

function die() {
  echo "ERROR: $*" >&2
  exit 1
}

QUEUE="${QUEUE:-new_order}"

echo "1) publish invalid message with x-retry-count=999 (should go to DLQ immediately)"
docker compose exec -T web python - <<PY
import json

import pika

from app.core.config import get_settings

settings = get_settings()
queue = "${QUEUE}"
params = pika.URLParameters(settings.rabbitmq_dsn)
conn = pika.BlockingConnection(params)
ch = conn.channel()
ch.queue_declare(queue=f"{queue}.dlq", durable=True)
ch.queue_declare(
    queue=queue,
    durable=True,
    arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": f"{queue}.dlq",
    },
)
props = pika.BasicProperties(
    content_type="application/json",
    delivery_mode=2,
    headers={"x-retry-count": 999},
)
ch.basic_publish(
    exchange="",
    routing_key=queue,
    body=json.dumps({"bad": "payload"}).encode("utf-8"),
    properties=props,
)
conn.close()
print("published")
PY

echo "2) wait a bit for consumer to reject -> DLQ"
sleep 2

echo "3) check DLQ message count"
COUNT="$(
  docker compose exec -T rabbitmq rabbitmqctl list_queues -q name messages \
  | awk '$1=="'"${QUEUE}.dlq"'"{print $2}'
)"
COUNT="${COUNT:-0}"
if [[ "$COUNT" -lt 1 ]]; then
  docker compose exec -T rabbitmq rabbitmqctl list_queues name messages || true
  die "expected ${QUEUE}.dlq to have >=1 message, got $COUNT"
fi
echo "OK (dlq_messages=$COUNT)"

echo "ALL CONSUMER DLQ SCENARIO: OK"
