from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

settings = get_settings()
# Migrations precisam da role dona das tabelas (CREATE TABLE, ALTER, CREATE POLICY);
# `database_url` em produção deve ser uma role restrita sem esses privilégios (ver
# app/core/config.py). Cai para `database_url` quando `database_migration_url` não
# estiver configurada (setup de uma role só).
migration_url = settings.database_migration_url or settings.database_url
if migration_url:
    config.set_main_option("sqlalchemy.url", migration_url)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    """Filter autogenerate to avoid noisy diffs from legacy schema.

    Index and FK naming diverges between models and existing migrations (legacy
    composite indexes vs model-generated single-column ones). Column attribute
    changes (server_default, nullable) also skipped. New/removed tables and
    columns are still reported.
    """
    if type_ in {"index", "foreign_key_constraint"}:
        return False
    return not (type_ == "column" and compare_to is not None)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
