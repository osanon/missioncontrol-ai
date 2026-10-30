"""Create client_merges if it is missing.

Databases created before the merge workflow (early October 2026) have no client_merges table, but were stamped at
0001_baseline, which assumes it exists. This creates it for them, including databases already upgraded to 0003.
It does nothing where the table already exists.

Revision ID: 0004_ensure_client_merges
Revises: 0003_ai_reviews
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_ensure_client_merges'
down_revision = '0003_ai_reviews'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('client_merges'):
        return
    op.create_table('client_merges',
                    sa.Column('source_id', sa.Integer, sa.ForeignKey('clients.id'), primary_key=True, autoincrement=False),
                    sa.Column('target_id', sa.Integer, sa.ForeignKey('clients.id'), nullable=False),
                    sa.Column('proposal_id', sa.String, nullable=False), sa.Column('merged_at', sa.String, nullable=False),
                    sa.Column('merged_by', sa.String, nullable=False),
                    sa.CheckConstraint('source_id <> target_id', name='different_merge_profiles'))


def downgrade():
    # The table belongs to the baseline schema; leave it in place.
    pass
