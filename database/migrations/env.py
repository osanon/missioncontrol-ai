"""Alembic environment. Uses DATABASE_URL (or a connection passed in by database.migrate)."""
from alembic import context
from backend.db import metadata, engine_for, DATABASE_URL

config = context.config


def run_migrations_online():
    connection = config.attributes.get('connection')
    if connection is not None:
        context.configure(connection=connection, target_metadata=metadata, render_as_batch=connection.dialect.name == 'sqlite')
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = engine_for(DATABASE_URL)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, render_as_batch=connection.dialect.name == 'sqlite')
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    context.configure(url=DATABASE_URL, target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
