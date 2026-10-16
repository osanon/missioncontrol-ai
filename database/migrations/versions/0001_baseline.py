"""Baseline: the v0.1 schema as created by metadata.create_all before migrations existed.

Revision ID: 0001_baseline
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Col, I, S, F, B, FK = sa.Column, sa.Integer, sa.String, sa.Float, sa.Boolean, sa.ForeignKey
    op.create_table('clients', Col('id', I, primary_key=True), Col('external_id', S, unique=True), Col('full_name', S, nullable=False),
                    Col('birth_date', S(10)), Col('email', S), Col('review_required', B, nullable=False))
    op.create_table('programs', Col('id', I, primary_key=True), Col('name', S, nullable=False))
    op.create_table('enrollments', Col('id', I, primary_key=True), Col('client_id', I, FK('clients.id'), nullable=False),
                    Col('program_id', I, FK('programs.id'), nullable=False), Col('start_date', S(10), nullable=False), Col('end_date', S(10)),
                    Col('status', S, nullable=False), Col('review_required', B, nullable=False))
    op.create_table('services', Col('id', I, primary_key=True), Col('client_id', I, FK('clients.id'), nullable=False),
                    Col('program_id', I, FK('programs.id'), nullable=False), Col('service_date', S(10), nullable=False),
                    Col('units', F, nullable=False), Col('review_required', B, nullable=False))
    op.create_table('employment', Col('id', I, primary_key=True), Col('client_id', I, FK('clients.id'), nullable=False),
                    Col('start_date', S(10), nullable=False), Col('end_date', S(10)), Col('hourly_wage', F), Col('review_required', B, nullable=False))
    op.create_table('housing', Col('id', I, primary_key=True), Col('client_id', I, FK('clients.id'), nullable=False),
                    Col('entry_date', S(10), nullable=False), Col('exit_date', S(10)), Col('destination', S))
    op.create_table('assessments', Col('id', I, primary_key=True), Col('client_id', I, FK('clients.id'), nullable=False),
                    Col('assessment_date', S(10)), Col('kind', S), Col('score', F))
    op.create_table('followups', Col('id', I, primary_key=True), Col('employment_id', I, FK('employment.id'), nullable=False),
                    Col('due_date', S(10)), Col('completed_date', S(10)), Col('retained', B))
    op.create_table('surveys', Col('id', I, primary_key=True), Col('program_id', I, FK('programs.id'), nullable=False),
                    Col('response_date', S(10)), Col('rating', I), Col('comment', S))
    op.create_table('proposed_actions', Col('id', S, primary_key=True), Col('issue_key', S, unique=True), Col('table_name', S, nullable=False),
                    Col('record_id', I, nullable=False), Col('before', sa.JSON, nullable=False), Col('after', sa.JSON, nullable=False),
                    Col('reason', S, nullable=False), Col('status', S, nullable=False), Col('created_at', S, nullable=False),
                    Col('decided_at', S), Col('decided_by', S))
    op.create_table('audit_records', Col('id', S, primary_key=True), Col('occurred_at', S, nullable=False), Col('actor', S, nullable=False),
                    Col('event', S, nullable=False), Col('details', sa.JSON, nullable=False))
    op.create_table('agent_runs', Col('id', S, primary_key=True), Col('created_at', S, nullable=False), Col('question', S, nullable=False),
                    Col('answer', S, nullable=False), Col('mode', S, nullable=False), Col('trace', sa.JSON, nullable=False))
    op.create_table('client_merges', Col('source_id', I, FK('clients.id'), primary_key=True, autoincrement=False),
                    Col('target_id', I, FK('clients.id'), nullable=False), Col('proposal_id', S, nullable=False),
                    Col('merged_at', S, nullable=False), Col('merged_by', S, nullable=False),
                    sa.CheckConstraint('source_id <> target_id', name='different_merge_profiles'))


def downgrade():
    for table in ('client_merges', 'agent_runs', 'audit_records', 'proposed_actions', 'surveys', 'followups', 'assessments',
                  'housing', 'employment', 'services', 'enrollments', 'programs', 'clients'):
        op.drop_table(table)
