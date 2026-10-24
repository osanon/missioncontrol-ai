"""Phase 2: AI reviews of proposals, agent run kind, and token usage.

Revision ID: 0003_ai_reviews
Revises: 0002_provenance_and_run_status
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_ai_reviews'
down_revision = '0002_provenance_and_run_status'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('agent_runs') as batch:
        batch.add_column(sa.Column('kind', sa.String, nullable=False, server_default='analyst'))
        batch.add_column(sa.Column('input_tokens', sa.Integer))
        batch.add_column(sa.Column('output_tokens', sa.Integer))
    op.create_table('ai_reviews', sa.Column('id', sa.String, primary_key=True),
                    sa.Column('proposal_id', sa.String, sa.ForeignKey('proposed_actions.id'), nullable=False),
                    sa.Column('run_id', sa.String, nullable=False), sa.Column('reviewer', sa.String, nullable=False),
                    sa.Column('mode', sa.String, nullable=False), sa.Column('model', sa.String),
                    sa.Column('verdict', sa.String, nullable=False), sa.Column('confidence', sa.String, nullable=False),
                    sa.Column('summary', sa.String, nullable=False), sa.Column('concerns', sa.JSON, nullable=False),
                    sa.Column('created_at', sa.String, nullable=False))
    op.create_index('ix_ai_reviews_proposal_id', 'ai_reviews', ['proposal_id'])


def downgrade():
    op.drop_index('ix_ai_reviews_proposal_id', 'ai_reviews')
    op.drop_table('ai_reviews')
    with op.batch_alter_table('agent_runs') as batch:
        for name in ('output_tokens', 'input_tokens', 'kind'):
            batch.drop_column(name)
