"""Upgrading databases created by older versions of the app."""
from sqlalchemy import create_engine, inspect, text
from alembic import command
from database.migrate import upgrade, config, BASELINE


def test_database_from_before_the_merge_workflow_is_upgraded(tmp_path):
    # Databases created before mid-October 2026 have no client_merges table.
    old = create_engine(f'sqlite:///{tmp_path}/old.db')
    with old.begin() as c:
        command.upgrade(config(c), BASELINE)
        c.execute(text('DROP TABLE client_merges'))
        c.execute(text('DROP TABLE alembic_version'))
    upgrade(old)
    with old.connect() as c:
        assert inspect(c).has_table('client_merges')
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar() == '0004_ensure_client_merges'
    old.dispose()


def test_half_upgraded_database_gets_the_missing_table(tmp_path):
    # The state left behind when the 0003 upgrade succeeded but client_merges was missing.
    db = create_engine(f'sqlite:///{tmp_path}/half.db')
    with db.begin() as c:
        command.upgrade(config(c), '0003_ai_reviews')
        c.execute(text('DROP TABLE client_merges'))
    upgrade(db)
    upgrade(db)  # Idempotent.
    with db.connect() as c:
        assert inspect(c).has_table('client_merges')
    db.dispose()
