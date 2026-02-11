# Order Management (gpt_codex)

Sprint 0: project skeleton (FastAPI + config + logging + Docker + Makefile).
Sprint 1: DB + Alembic + auth (register/token).
Sprint 2: orders CRUD + validation + JWT authz.
Sprint 3: Redis cache + graceful degradation.
Sprint 4: RabbitMQ event-bus + outbox + consumer + Celery tasks.

## Quick start (local)

```bash
cd gpt_codex
make venv
make install
cp .env.example .env
make run
```

Open Swagger UI: `http://localhost:8000/docs`

## Quick start (Docker)

```bash
cd gpt_codex
cp .env.example .env
docker compose up --build
```

Swagger UI: `http://localhost:8001/docs`

## Tests

```bash
cd gpt_codex
make test
```

## CI

Локально:

```bash
cd gpt_codex
make ci
```

## Migrations

### Как устроено в этом проекте (для тестового)

По умолчанию в `.env.example` выставлено `RUN_MIGRATIONS_ON_STARTUP=true`, и миграции
запускаются **один раз на старт процесса** через FastAPI lifespan
(`app/core/migrations.py`, advisory lock для Postgres).

Это удобно для проверки тестового через `docker compose up`, чтобы не требовать
ручной команды миграций.

Отключить автозапуск миграций:

```bash
RUN_MIGRATIONS_ON_STARTUP=false
```

После отключения миграции можно прогнать вручную:

```bash
cd gpt_codex
make migrate
```

Create a new revision (autogenerate):

```bash
cd gpt_codex
make makemigrations m="add something"
```

## Auth API

- `POST /register/` — JSON `{ "email": "...", "password": "..." }`
- `POST /token/` — form-data `username=email`, `password=...`

## Orders API

- `POST /orders/` — создать заказ (Authorization required)
- `GET /orders/{order_id}/` — получить заказ (Authorization required)
- `PATCH /orders/{order_id}/` — обновить статус (Authorization required)
- `GET /orders/user/{user_id}/` — список заказов пользователя (только свой user_id)

## Curl проверки

При запущенном API:

```bash
cd gpt_codex
./scripts/test_api_curl.sh
```

Полный позитив/негатив прогон:

```bash
cd gpt_codex
BASE_URL=http://localhost:8001 ./scripts/test_api_curl_full.sh
```

E2E проверка event-bus → consumer → celery (с проверкой по логам контейнеров):

```bash
cd gpt_codex
BASE_URL=http://localhost:8001 ./scripts/test_event_flow.sh
```

## Redis cache

`GET /orders/{order_id}/` сначала пытается читать заказ из Redis (TTL по умолчанию 300 секунд),
при ошибках Redis делает fallback на БД.

## Event-bus (RabbitMQ) + Outbox + Celery

- `new_order` событие пишется в outbox таблицу при создании заказа и доставляется в RabbitMQ отдельным процессом.
- Consumer читает очередь `new_order` и запускает Celery задачу `process_order`.
- Celery по умолчанию использует Redis как брокер задач (не RabbitMQ), чтобы не смешивать роли.

## Security

- CORS включён через middleware (настраивается env-переменными `CORS_*`).
- Rate limiting включён через Token Bucket middleware (настраивается `RATE_LIMIT_*`).
