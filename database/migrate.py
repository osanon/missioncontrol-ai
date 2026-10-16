"""Apply Alembic migrations. Databases created before migrations existed are stamped at the baseline first."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from backend.db import engine

BASELINE = '0001_baseline'


def config(connection):
    cfg = Config()
    cfg.set_main_option('script_location', str(Path(__file__).resolve().parent / 'migrations'))
    cfg.attributes['connection'] = connection
    return cfg


def upgrade(target=engine):
    with target.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        cfg = config(connection)
        if 'clients' in tables and 'alembic_version' not in tables:
            # Pre-migration database (v0.1 create_all): its tables match the baseline, so record that and upgrade from there.
            command.stamp(cfg, BASELINE)
        command.upgrade(cfg, 'head')


if __name__ == '__main__':
    upgrade()
    print('Database schema is up to date.')
