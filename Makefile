.DEFAULT_GOAL := help

PY := python3

.PHONY: help
help:
	@printf "%s\n" \
	"Targets:" \
	"  make venv        - create venv in .venv" \
	"  make install     - install deps into venv" \
	"  make run         - run API locally" \
	"  make test        - run pytest" \
	"  make format      - run black" \
	"  make lint        - run flake8" \
	"  make typecheck   - run mypy" \
	"  make ci          - lint + tests" \
	"  make migrate     - alembic upgrade head" \
	"  make makemigrations - alembic revision --autogenerate" \
	"  make clean       - remove caches/artifacts" \
	"  make clean-venv  - remove .venv (recreate with make venv)" \
	"  make dc-up       - docker compose up" \
	"  make dc-down     - docker compose down" \
	"  make dc-logs     - docker compose logs -f"

.PHONY: venv
venv:
	$(PY) -m venv .venv

.PHONY: install
install:
	. .venv/bin/activate && pip install -U pip && pip install -r requirements.txt -r requirements-dev.txt

.PHONY: run
run:
	. .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

.PHONY: test
test:
	. .venv/bin/activate && pytest -q

.PHONY: format
format:
	. .venv/bin/activate && black .

.PHONY: lint
lint:
	. .venv/bin/activate && flake8 .

.PHONY: ci
ci:
	$(MAKE) lint
	$(MAKE) test

.PHONY: typecheck
typecheck:
	. .venv/bin/activate && mypy .

.PHONY: migrate
migrate:
	. .venv/bin/activate && alembic upgrade head

.PHONY: makemigrations
makemigrations:
	. .venv/bin/activate && alembic revision --autogenerate -m "$(m)"

.PHONY: dc-up
dc-up:
	docker compose up --build

.PHONY: dc-down
dc-down:
	docker compose down -v

.PHONY: dc-logs
dc-logs:
	docker compose logs -f

.PHONY: clean
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build
	find . -path ./.venv -prune -o -name "__pycache__" -type d -exec rm -rf {} +
	find . -path ./.venv -prune -o -name "*.py[co]" -type f -delete
	find . -path ./.venv -prune -o -name "*.pyd" -type f -delete
	find . -path ./.venv -prune -o -name "*.egg-info" -type d -exec rm -rf {} +
	rm -f alembic_ci.db alembic_ci_local.db alembic_test.db

.PHONY: clean-venv
clean-venv:
	rm -rf .venv
