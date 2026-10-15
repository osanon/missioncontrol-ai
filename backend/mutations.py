from sqlalchemy import text


def serialize_writes(connection):
    """Use one transaction lock for app proposals/decisions, including merges."""
    if connection.dialect.name == 'postgresql':
        connection.execute(text('SELECT pg_advisory_xact_lock(641024601)'))
