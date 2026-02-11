# Order Management (FastAPI) — Test Task

Production-minded backend service for managing orders:
- FastAPI + Swagger UI
- PostgreSQL + SQLAlchemy + Alembic migrations
- JWT auth (OAuth2 Password Flow)
- Redis cache with graceful degradation (fallback to DB)
- RabbitMQ event-bus with Outbox pattern (reliable delivery)
- Celery background processing (separate broker, default Redis)

## Requirements

- Docker + Docker Compose (recommended)
- Or Python 3.12+ (local run)

## Quick start (Docker) — recommended

```bash
cd gpt_codex
cp .env.example .env
docker compose up -d --build
```

- Swagger UI: `http://localhost:8001/docs`
- Health: `http://localhost:8001/health`
- RabbitMQ UI: `http://localhost:15673` (default `guest/guest`)

## Quick start (Local)

```bash
cd gpt_codex
make venv
make install
cp .env.example .env
make run
```

- Swagger UI: `http://localhost:8000/docs`

## How to validate (what a reviewer can run)

### Lint + unit tests

```bash
cd gpt_codex
make ci
```

### Curl scenarios (positive + negative)

```bash
cd gpt_codex
./scripts/test_api_curl_full.sh
```

### E2E: create order → outbox → RabbitMQ → consumer → Celery

```bash
cd gpt_codex
./scripts/test_event_flow.sh
```

## API summary

### Auth

- `POST /register/` — JSON `{ "email": "...", "password": "..." }`
- `POST /token/` — `application/x-www-form-urlencoded` fields: `username` (email), `password`

### Orders (Authorization: Bearer <token>)

- `POST /orders/` — create order
- `GET /orders/{order_id}/` — get order (Redis first; fallback to DB)
- `PATCH /orders/{order_id}/` — update status
- `GET /orders/user/{user_id}/` — list own orders

## Architecture (high-level)

1) `POST /orders/` writes `orders` + `outbox_events` in the same DB transaction.
2) `outbox_publisher` reads pending outbox events and publishes to RabbitMQ (with retries).
3) `message_consumer` consumes `new_order` events and triggers Celery task `process_order`.
4) Celery runs on a separate broker (default Redis) to keep event-bus and task queue independent.

## Migrations

### Test-task mode (self-contained docker compose)

By default `.env.example` enables:

```bash
RUN_MIGRATIONS_ON_STARTUP=true
```

Migrations run once on application startup using Postgres advisory lock
(`app/core/migrations.py`). This makes `docker compose up` self-contained for the test.

### Production recommendation (typical approach)

In production, migrations are usually executed as a **separate deploy step / job**
(CI/CD step, Kubernetes Job/initContainer), and the API process runs without DDL rights.

To disable migrations-on-startup in this project:

```bash
RUN_MIGRATIONS_ON_STARTUP=false
```

Then run migrations explicitly:

```bash
cd gpt_codex
make migrate
```

## Useful commands

```bash
cd gpt_codex
make clean        # remove caches/artifacts
make dc-up        # docker compose up --build
make dc-down      # docker compose down -v
make dc-logs      # follow compose logs
```

## Notes (production-ready expectations)

- Redis is best-effort: Redis errors must not crash the API (fallback to DB).
- Event-bus publishing is reliable: outbox prevents “order created but event lost”.
- No hardcoded secrets: use `.env` locally; use secret manager in real deployments.
