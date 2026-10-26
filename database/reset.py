"""Wipe and reseed the FICTIONAL demo dataset, including proposals, AI reviews, runs and audit history.

Needs the database owner's credentials, so it runs in the one-shot seed container, never in the web backend:
    docker compose run --rm seed python -m database.reset --yes

The web app cannot do this: its database role has no DELETE rights, which keeps the audit trail append-only.
"""
import sys
from sqlalchemy import delete
from backend.db import engine, metadata
from database.migrate import upgrade
from database.seed import seed


def reset(target=engine):
    upgrade(target)
    with target.begin() as c:
        # Children before parents, so foreign keys hold at every step.
        for table in reversed(metadata.sorted_tables):
            c.execute(delete(table))
    seed(target)


if __name__ == '__main__':
    if '--yes' not in sys.argv:
        raise SystemExit('This deletes all demo data, proposals, AI reviews and audit history, then reseeds the fictional dataset. '
                         'Run again with --yes to confirm.')
    reset()
    print('Demo data reset: fictional dataset reseeded; proposals, reviews, runs and audit history cleared.')
