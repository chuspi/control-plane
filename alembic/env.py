import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool

config = context.config

# Logging opcional si tienes secciones en alembic.ini
try:
    if config.config_file_name and config.get_section("loggers"):
        fileConfig(config.config_file_name)
except KeyError:
    pass

target_metadata = None  # no autogenerate en este proyecto


def _get_db_url() -> str:
    url = os.getenv("CONTROL_PLANE_DATABASE_URL")
    if not url:
        raise RuntimeError("CONTROL_PLANE_DATABASE_URL no está definida en el entorno")
    return url


def run_migrations_offline() -> None:
    """Genera SQL sin conectar."""
    url = _get_db_url()
    context.configure(
        url=url,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones conectado a la DB."""
    url = _get_db_url()
    engine = create_engine(url, poolclass=pool.NullPool, future=True)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            compare_type=True,
            compare_server_default=True,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
