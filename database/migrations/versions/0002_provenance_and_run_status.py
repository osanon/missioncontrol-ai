"""Phase 1: proposal provenance, reevaluation notes, and agent run status.

Revision ID: 0002_provenance_and_run_status
Revises: 0001_baseline
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_provenance_and_run_status'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None

PROPOSAL_COLUMNS = ('created_by', 'created_by_kind', 'run_id', 'model', 'supersedes_id', 'decision_note')


def upgrade():
    with op.batch_alter_table('proposed_actions') as batch:
        for name in PROPOSAL_COLUMNS:
            batch.add_column(sa.Column(name, sa.String))
    with op.batch_alter_table('agent_runs') as batch:
        batch.add_column(sa.Column('status', sa.String, nullable=False, server_default='completed'))
        batch.add_column(sa.Column('error', sa.String))
        batch.add_column(sa.Column('model', sa.String))


def downgrade():
    with op.batch_alter_table('agent_runs') as batch:
        for name in ('model', 'error', 'status'):
            batch.drop_column(name)
    with op.batch_alter_table('proposed_actions') as batch:
        for name in reversed(PROPOSAL_COLUMNS):
            batch.drop_column(name)
