"""Phase 1: reviewer identities, reevaluation, proposal provenance, reliable live runs, migrations."""
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete, create_engine, inspect, text
from backend.db import engine, employment, proposals, audit, runs, metadata
from backend.logic import propose, decide, Conflict
from backend.main import app
from backend.reviewers import load_reviewers
from tests.test_merges import pair, make_merge, SOURCE, TARGET  # noqa: F401  (pair is a fixture)

HEADERS = {'Authorization': 'Bearer test-analyst-token-000000000000000000'}
ALICE = {**HEADERS, 'X-Review-Token': 'test-alice-token-00000000000000000000'}
BOB = {**HEADERS, 'X-Review-Token': 'test-bob-token-0000000000000000000000'}
LEGACY = {**HEADERS, 'X-Review-Token': 'test-review-token-0000000000000000000'}
JOB = 920001
KEY = f'wage_outlier:{JOB}'
NOTE = 'Wage looks like an annual figure; check the payroll export.'


@pytest.fixture
def job():
    with engine.begin() as c:
        c.execute(employment.insert().values(id=JOB, client_id=1, start_date='2026-07-01', hourly_wage=1500.0, review_required=False))
    yield KEY
    with engine.begin() as c:
        c.execute(delete(proposals).where(proposals.c.table_name == 'employment', proposals.c.record_id == JOB))
        c.execute(delete(employment).where(employment.c.id == JOB))


def wage():
    with engine.connect() as c:
        return c.scalar(select(employment.c.hourly_wage).where(employment.c.id == JOB))


def saved(pid):
    with engine.connect() as c:
        return dict(c.execute(select(proposals).where(proposals.c.id == pid)).mappings().one())


def events(name, pid):
    with engine.connect() as c:
        return [dict(e) for e in c.execute(select(audit).where(audit.c.event == name)).mappings() if e['details'].get('proposal_id') == pid]


# Reviewer identity

def test_each_reviewer_is_recorded_by_name(job):
    with TestClient(app) as client:
        assert client.get('/reviewer', headers=ALICE).json() == {'name': 'alice'}
        assert client.get('/reviewer', headers=LEGACY).json() == {'name': 'reviewer'}
        assert client.get('/reviewer', headers=HEADERS).status_code == 403
        p = client.post('/proposals', headers=HEADERS, json={'issue_key': job}).json()
        assert client.post('/approvals/' + p['id'], headers=BOB, json={'decision': 'approve'}).json()['status'] == 'applied'
    assert saved(p['id'])['decided_by'] == 'bob'
    [event] = events('proposal_applied', p['id'])
    assert event['actor'] == 'bob' and event['details']['proposed_by'] == 'analyst'


def test_analyst_token_cannot_be_used_as_reviewer_token(job):
    with TestClient(app) as client:
        p = client.post('/proposals', headers=HEADERS, json={'issue_key': job}).json()
        as_reviewer = {**HEADERS, 'X-Review-Token': 'test-analyst-token-000000000000000000'}
        assert client.post('/approvals/' + p['id'], headers=as_reviewer, json={'decision': 'approve'}).status_code == 403
        assert client.post('/approvals/' + p['id'], headers={**HEADERS, 'X-Review-Token': 'wrong'}, json={'decision': 'approve'}).status_code == 403
    assert wage() == 1500


@pytest.mark.parametrize('reviewers,legacy,message', [
    ('alice:short', '', 'at least'),
    ('alice:' + 'a' * 30 + ',bob:' + 'a' * 30, '', 'different token'),
    ('analyst:' + 'a' * 30, '', 'reserved'),
    ('agent-x:' + 'a' * 30, '', 'reserved'),
    ('Alice:' + 'a' * 30, '', 'name:token'),
    ('alice', '', 'name:token'),
    ('alice:' + 'a' * 30 + ',alice:' + 'b' * 30, '', 'more than once'),
    ('alice:test-analyst-token-000000000000000000', '', 'analyst and reviewer'),
])
def test_unsafe_reviewer_configuration_is_rejected(monkeypatch, reviewers, legacy, message):
    monkeypatch.setenv('REVIEWERS', reviewers)
    monkeypatch.setenv('REVIEW_TOKEN', legacy)
    with pytest.raises(RuntimeError, match=message):
        load_reviewers()


def test_app_refuses_to_start_without_reviewers(monkeypatch):
    monkeypatch.setenv('REVIEWERS', '')
    monkeypatch.setenv('REVIEW_TOKEN', '')
    with pytest.raises(RuntimeError, match='at least one reviewer'):
        with TestClient(app):
            pass


def test_author_cannot_decide_own_proposal(job):
    p = propose(job, actor='alice', actor_kind='human')
    with pytest.raises(Conflict, match='other than their author'):
        decide(p['id'], 'approve', 'alice')
    assert decide(p['id'], 'approve', 'bob')['status'] == 'applied'


# Reevaluation

def test_reevaluate_requires_note_and_changes_nothing(job):
    with TestClient(app) as client:
        p = client.post('/proposals', headers=HEADERS, json={'issue_key': job}).json()
        assert client.post('/approvals/' + p['id'], headers=ALICE, json={'decision': 'reevaluate'}).status_code == 400
        assert client.post('/approvals/' + p['id'], headers=ALICE, json={'decision': 'reevaluate', 'note': 'too short'}).status_code == 400
        assert client.post('/approvals/' + p['id'], headers=ALICE, json={'decision': 'maybe'}).status_code == 422
        out = client.post('/approvals/' + p['id'], headers=ALICE, json={'decision': 'reevaluate', 'note': NOTE}).json()
        assert out['status'] == 'reevaluation_requested'
        assert client.post('/approvals/' + p['id'], headers=BOB, json={'decision': 'approve'}).status_code == 409
        finding = next(i for i in client.get('/issues', headers=HEADERS).json() if i['key'] == job)
        assert finding['proposal_status'] == 'reevaluation_requested'
    assert wage() == 1500
    row = saved(p['id'])
    assert row['decided_by'] == 'alice' and row['decision_note'] == NOTE
    [event] = events('proposal_reevaluation_requested', p['id'])
    assert event['details']['note'] == NOTE and event['actor'] == 'alice'


def test_reevaluated_proposal_is_revised_with_history(job):
    old = propose(job)
    decide(old['id'], 'reevaluate', 'alice', NOTE)
    with pytest.raises(Conflict):
        propose(job, resolution='correct_wage', value='15', evidence='Payroll export shows $15.00 per hour.', replaces_id='wrong-id')
    new = propose(job, resolution='correct_wage', value='15', evidence='Payroll export shows $15.00 per hour.', replaces_id=old['id'])
    assert new['supersedes_id'] == old['id'] and new['status'] == 'pending'
    previous = saved(old['id'])
    assert previous['status'] == 'reevaluation_requested' and previous['issue_key'] == job + '@' + old['id']
    assert any(e['details']['replacement_id'] == new['id'] for e in events('proposal_revised', old['id']))
    decide(new['id'], 'approve', 'bob')
    assert wage() == 15


def test_merge_can_be_sent_back_and_replaced(pair):
    with TestClient(app) as client:
        p = make_merge()
        assert client.post('/approvals/' + p['id'], headers=ALICE, json={'decision': 'reevaluate', 'note': NOTE}).json()['status'] == 'reevaluation_requested'
        assert client.get(f'/merges/preview?source_id={SOURCE}&target_id={TARGET}&replaces_id={p["id"]}', headers=HEADERS).status_code == 200
    replacement = make_merge(replaces_id=p['id'])
    assert replacement['supersedes_id'] == p['id']
    assert saved(p['id'])['status'] == 'reevaluation_requested'
    assert decide(replacement['id'], 'approve', 'bob')['status'] == 'applied'


# Provenance and live runs

class Provider:
    """Scripted chat-completions provider: each entry is a response body or an exception."""
    def __init__(self, monkeypatch, *script):
        self.script, self.requests = list(script), []
        from agent import runner
        monkeypatch.setenv('AGENT_MODE', 'live')
        monkeypatch.setenv('LLM_API_KEY', 'fake-test-key')
        monkeypatch.setenv('LLM_MODEL', 'test-model')
        monkeypatch.setattr(runner.httpx, 'post', self.post)

    def post(self, url, **kwargs):
        self.requests.append(kwargs['json'])
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        body = item

        class Response:
            def raise_for_status(self): pass
            def json(self): return body
        return Response()


def tool_call(name, args, call_id='call-1'):
    return {'choices': [{'message': {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}}]}


def answer(text):
    return {'choices': [{'message': {'role': 'assistant', 'content': text}}]}


def test_agent_proposal_records_run_and_model(monkeypatch, job):
    Provider(monkeypatch, tool_call('propose_correction', {'issue_key': job, 'resolution': 'clear_wage', 'value': '', 'evidence': ''}),
             answer('Proposed clearing the wage for review. [step 1: employment]'))
    with TestClient(app) as client:
        result = client.post('/ask', headers=HEADERS, json={'question': 'Flag the implausible wage.'}).json()
        assert result['status'] == 'completed' and result['model'] == 'test-model'
        listed = next(p for p in client.get('/proposals', headers=HEADERS).json() if p['record_id'] == JOB)
    assert listed['created_by'] == 'agent:analyst' and listed['created_by_kind'] == 'agent'
    assert listed['run_id'] == result['id'] and listed['model'] == 'test-model'
    with engine.connect() as c:
        assert c.scalar(select(runs.c.status).where(runs.c.id == result['id'])) == 'completed'


def test_human_proposal_records_analyst(job):
    with TestClient(app) as client:
        p = client.post('/proposals', headers=HEADERS, json={'issue_key': job}).json()
    assert (p['created_by'], p['created_by_kind'], p['run_id']) == ('analyst', 'human', None)


def test_failed_live_run_is_saved_with_partial_trace(monkeypatch, job):
    Provider(monkeypatch, tool_call('propose_correction', {'issue_key': job, 'resolution': 'follow_up', 'value': '', 'evidence': ''}),
             httpx.ConnectError('provider down'))
    with TestClient(app) as client:
        result = client.post('/ask', headers=HEADERS, json={'question': 'Flag the implausible wage.'}).json()
        assert result['status'] == 'failed' and 'Inference request failed' in result['error']
        assert 'stopped before finishing' in result['answer'] and '1 proposal(s)' in result['answer']
        assert [s['tool'] for s in result['trace']] == ['propose_correction']
        report = client.get('/reports/' + result['id'], headers=HEADERS).text
        assert 'Status: failed' in report and 'propose_correction' in report
    with engine.connect() as c:
        stored = c.execute(select(runs).where(runs.c.id == result['id'])).mappings().one()
        assert stored['status'] == 'failed' and len(stored['trace']) == 1
        assert c.scalar(select(proposals.c.run_id).where(proposals.c.record_id == JOB, proposals.c.table_name == 'employment')) == result['id']
        failed = [e for e in c.execute(select(audit).where(audit.c.event == 'analysis_failed')).mappings() if e['details']['run_id'] == result['id']]
    assert failed and failed[0]['actor'] == 'agent:analyst'


@pytest.mark.parametrize('body', [
    {'choices': []},
    {'error': {'message': 'quota'}},
    {'choices': [{'message': 'not an object'}]},
    {'choices': [{'message': {'content': None, 'tool_calls': [{'type': 'function', 'function': {'name': 'inspect_schema', 'arguments': '{}'}}]}}]},
    {'choices': [{'message': {'content': None, 'tool_calls': [{'id': 'x', 'function': 'inspect_schema'}]}}]},
    {'choices': [{'message': {'content': None, 'tool_calls': 'inspect_schema'}}]},
])
def test_malformed_provider_response_fails_cleanly(monkeypatch, body):
    Provider(monkeypatch, body)
    with TestClient(app) as client:
        response = client.post('/ask', headers=HEADERS, json={'question': 'How many clients were served?'})
    assert response.status_code == 200
    result = response.json()
    assert result['status'] == 'failed' and ('unexpected response' in result['answer'] or 'malformed' in result['answer'])


def test_non_object_tool_arguments_become_a_failed_step(monkeypatch):
    bad = tool_call('calculate_metrics', {})
    bad['choices'][0]['message']['tool_calls'][0]['function']['arguments'] = '[1, 2]'
    Provider(monkeypatch, bad, answer('Could not compute metrics.'))
    with TestClient(app) as client:
        result = client.post('/ask', headers=HEADERS, json={'question': 'How many clients were served?'}).json()
    assert result['status'] == 'completed' and result['trace'][0]['status'] == 'failed'


# Migrations

def test_migrations_match_models(tmp_path):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from database.migrate import upgrade
    fresh = create_engine(f'sqlite:///{tmp_path}/fresh.db')
    upgrade(fresh)
    with fresh.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c), metadata)
    fresh.dispose()
    assert diff == []


def test_pre_migration_database_is_stamped_and_upgraded(tmp_path):
    from alembic import command
    from database.migrate import upgrade, config, BASELINE
    legacy = create_engine(f'sqlite:///{tmp_path}/legacy.db')
    with legacy.begin() as c:
        command.upgrade(config(c), BASELINE)
        c.execute(text('DROP TABLE alembic_version'))  # As left by v0.1 metadata.create_all.
        c.execute(text("INSERT INTO agent_runs VALUES ('old-run', '2026-01-01', 'q', 'a', 'demo', '[]')"))
    upgrade(legacy)
    with legacy.connect() as c:
        assert {col['name'] for col in inspect(c).get_columns('proposed_actions')} >= {'created_by', 'run_id', 'decision_note', 'supersedes_id'}
        assert c.execute(text("SELECT status FROM agent_runs WHERE id='old-run'")).scalar() == 'completed'
    upgrade(legacy)  # Idempotent.
    legacy.dispose()
