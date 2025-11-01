FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl gcc build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Instala uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s $HOME/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# Copiamos solo pyproject/lock para cachear deps
COPY pyproject.toml uv.lock ./
RUN uv venv --python 3.12 && . .venv/bin/activate && uv sync --frozen

# Copiamos el resto del código
COPY alembic alembic
COPY app app
COPY alembic.ini .

EXPOSE 8000
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
