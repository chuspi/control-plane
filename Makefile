.PHONY: venv install install.dev lock sync sync.dev run migrate.up migrate.dn test lint fmt export-req

venv:
	uv venv --python 3.12

lock:
	uv lock

sync: venv
	uv sync --frozen

sync.dev: venv
	uv sync --frozen --group dev

install: lock sync
install.dev: lock sync.dev

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

migrate.up:
	uv run alembic upgrade head

migrate.dn:
	uv run alembic downgrade -1

test:
	uv run pytest -q

lint:
	uv run ruff check .

fmt:
	uv run black .

export-req:
	uv export --format requirements.txt --no-dev --output requirements.txt
