import os
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, Boolean, ForeignKey, JSON, CheckConstraint

metadata = MetaData()
clients = Table('clients', metadata, Column('id', Integer, primary_key=True), Column('external_id', String, unique=True), Column('full_name', String, nullable=False), Column('birth_date', String(10)), Column('email', String), Column('review_required', Boolean, nullable=False, default=False))
programs = Table('programs', metadata, Column('id', Integer, primary_key=True), Column('name', String, nullable=False))
enrollments = Table('enrollments', metadata, Column('id', Integer, primary_key=True), Column('client_id', ForeignKey('clients.id'), nullable=False), Column('program_id', ForeignKey('programs.id'), nullable=False), Column('start_date', String(10), nullable=False), Column('end_date', String(10)), Column('status', String, nullable=False), Column('review_required', Boolean, nullable=False, default=False))
services = Table('services', metadata, Column('id', Integer, primary_key=True), Column('client_id', ForeignKey('clients.id'), nullable=False), Column('program_id', ForeignKey('programs.id'), nullable=False), Column('service_date', String(10), nullable=False), Column('units', Float, nullable=False), Column('review_required', Boolean, nullable=False, default=False))
employment = Table('employment', metadata, Column('id', Integer, primary_key=True), Column('client_id', ForeignKey('clients.id'), nullable=False), Column('start_date', String(10), nullable=False), Column('end_date', String(10)), Column('hourly_wage', Float), Column('review_required', Boolean, nullable=False, default=False))
housing = Table('housing', metadata, Column('id', Integer, primary_key=True), Column('client_id', ForeignKey('clients.id'), nullable=False), Column('entry_date', String(10), nullable=False), Column('exit_date', String(10)), Column('destination', String))
assessments = Table('assessments', metadata, Column('id', Integer, primary_key=True), Column('client_id', ForeignKey('clients.id'), nullable=False), Column('assessment_date', String(10)), Column('kind', String), Column('score', Float))
followups = Table('followups', metadata, Column('id', Integer, primary_key=True), Column('employment_id', ForeignKey('employment.id'), nullable=False), Column('due_date', String(10)), Column('completed_date', String(10)), Column('retained', Boolean))
surveys = Table('surveys', metadata, Column('id', Integer, primary_key=True), Column('program_id', ForeignKey('programs.id'), nullable=False), Column('response_date', String(10)), Column('rating', Integer), Column('comment', String))
proposals = Table('proposed_actions', metadata, Column('id', String, primary_key=True), Column('issue_key', String, unique=True), Column('table_name', String, nullable=False), Column('record_id', Integer, nullable=False), Column('before', JSON, nullable=False), Column('after', JSON, nullable=False), Column('reason', String, nullable=False), Column('status', String, nullable=False), Column('created_at', String, nullable=False), Column('decided_at', String), Column('decided_by', String),
    # Provenance: who proposed it (person or agent), from which agent run and model, and what it replaced.
    Column('created_by', String), Column('created_by_kind', String), Column('run_id', String), Column('model', String),
    Column('supersedes_id', String), Column('decision_note', String))
audit = Table('audit_records', metadata, Column('id', String, primary_key=True), Column('occurred_at', String, nullable=False), Column('actor', String, nullable=False), Column('event', String, nullable=False), Column('details', JSON, nullable=False))
runs = Table('agent_runs', metadata, Column('id', String, primary_key=True), Column('created_at', String, nullable=False), Column('question', String, nullable=False), Column('answer', String, nullable=False), Column('mode', String, nullable=False), Column('trace', JSON, nullable=False),
    Column('status', String, nullable=False, server_default='completed'), Column('error', String), Column('model', String),
    Column('kind', String, nullable=False, server_default='analyst'), Column('input_tokens', Integer), Column('output_tokens', Integer))
# Independent AI reviews of proposals. A review never changes data or decides; people do.
ai_reviews = Table('ai_reviews', metadata, Column('id', String, primary_key=True), Column('proposal_id', ForeignKey('proposed_actions.id'), nullable=False, index=True),
    Column('run_id', String, nullable=False), Column('reviewer', String, nullable=False), Column('mode', String, nullable=False), Column('model', String),
    Column('verdict', String, nullable=False), Column('confidence', String, nullable=False), Column('summary', String, nullable=False),
    Column('concerns', JSON, nullable=False), Column('created_at', String, nullable=False))
client_merges = Table('client_merges', metadata, Column('source_id', ForeignKey('clients.id'), primary_key=True), Column('target_id', ForeignKey('clients.id'), nullable=False), Column('proposal_id', String, nullable=False), Column('merged_at', String, nullable=False), Column('merged_by', String, nullable=False), CheckConstraint('source_id <> target_id', name='different_merge_profiles'))
DATA_TABLES = {t.name:t for t in [clients, programs, enrollments, services, employment, housing, assessments, followups, surveys, client_merges]}

def engine_for(url):
    return create_engine(url, pool_pre_ping=True, **({'connect_args': {'check_same_thread':False}} if url.startswith('sqlite') else {}))

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./missioncontrol.db')
engine = engine_for(DATABASE_URL)
reader = engine_for(os.getenv('READ_DATABASE_URL', DATABASE_URL))

def schema():
    return {name: [{'name': c.name, 'type': str(c.type), 'nullable': c.nullable} for c in t.columns] for name,t in DATA_TABLES.items()}
