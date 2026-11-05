"""Health check: the investigator proposes a fix for one finding, then the independent reviewer checks it."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete
from backend.db import engine, employment, proposals, audit, runs, ai_reviews
from backend.main import app
from tests.test_phase1 import Provider, tool_call
from tests.test_phase2 import submit

HEADERS = {'Authorization': 'Bearer test-analyst-token-000000000000000000'}
JOB = 990201
KEY = f'wage_outlier:{JOB}'


@pytest.fixture
def wage():
    with engine.begin() as c:
        c.execute(employment.insert().values(id=JOB, client_id=1, start_date='2026-07-15', end_date=None, hourly_wage=2500.0,
                                             review_required=False))
    yield KEY
    with engine.begin() as c:
        ids = [r.id for r in c.execute(select(proposals.c.id).where(proposals.c.table_name == 'employment', proposals.c.record_id == JOB))]
        c.execute(delete(ai_reviews).where(ai_reviews.c.proposal_id.in_(ids)))
        c.execute(delete(proposals).where(proposals.c.id.in_(ids)))
        c.execute(delete(employment).where(employment.c.id == JOB))


def check(client, key=KEY):
    return client.post('/health-checks/findings', headers=HEADERS, json={'issue_key': key})


def test_plan_mixes_kinds_most_severe_first_in_record_order(wage):
    with TestClient(app) as client:
        found = client.get('/health-checks/plan?limit=10', headers=HEADERS).json()
    assert 0 < len(found) <= 10 and {'key', 'kind', 'title', 'severity'} <= set(found[0])
    kinds = list(dict.fromkeys(f['kind'] for f in found))
    assert len(kinds) > 1 and found[0]['severity'] == 'high'
    assert [f['kind'] for f in found[:len(kinds)]] == kinds  # one of each kind before any repeats
    for kind in kinds:
        ids = [f['record_id'] for f in found if f['kind'] == kind]
        assert ids == sorted(ids)


def test_demo_health_check_proposes_safe_fix_and_reviews_it(wage):
    with TestClient(app) as client:
        result = check(client).json()
        again = check(client)
        planned = client.get('/health-checks/plan?limit=10', headers=HEADERS).json()
    assert result['proposal']['after'] == {'hourly_wage': None, 'review_required': True}
    assert result['review']['verdict'] in ('agree', 'disagree', 'uncertain') and result['review_error'] is None
    assert again.status_code == 409 and KEY not in [f['key'] for f in planned]
    with engine.connect() as c:
        proposal = c.execute(select(proposals).where(proposals.c.issue_key == KEY)).mappings().one()
        run = c.execute(select(runs).where(runs.c.id == result['run_id'])).mappings().one()
        events = [e['event'] for e in c.execute(select(audit)).mappings() if e['details'].get('run_id') == result['run_id']]
    assert (proposal['created_by'], proposal['created_by_kind'], proposal['run_id']) == ('agent:investigator', 'agent', result['run_id'])
    assert (run['kind'], run['status']) == ('investigator', 'completed') and 'investigation_completed' in events


def test_live_health_check_investigates_then_reviews(monkeypatch, wage):
    provider = Provider(monkeypatch,
                        tool_call('query_sql', {'sql': f'SELECT * FROM employment WHERE id = {JOB}'}),
                        tool_call('propose_correction', {'resolution': 'clear_wage', 'value': '', 'evidence': ''}),
                        submit(verdict='agree', confidence='high', summary='The wage is implausible and clearing it is safe.'))
    with TestClient(app) as client:
        result = check(client).json()
    assert result['proposal']['after'] == {'hourly_wage': None, 'review_required': True}
    assert result['review']['verdict'] == 'agree'
    first = provider.requests[0]
    assert {t['function']['name'] for t in first['tools']} == {'inspect_schema', 'query_sql', 'propose_correction'}
    assert KEY in first['messages'][1]['content'] and 'untrusted' in first['messages'][1]['content']
    with engine.connect() as c:
        proposal = c.execute(select(proposals).where(proposals.c.issue_key == KEY)).mappings().one()
    assert (proposal['created_by'], proposal['model']) == ('agent:investigator', 'test-model')


def test_live_investigator_is_asked_to_propose_on_its_last_turn(monkeypatch, wage):
    look = tool_call('query_sql', {'sql': f'SELECT * FROM employment WHERE id = {JOB}'})
    provider = Provider(monkeypatch, *[look] * 5, tool_call('propose_correction', {'resolution': 'clear_wage', 'value': '', 'evidence': ''}),
                        submit(verdict='agree', confidence='medium'))
    with TestClient(app) as client:
        result = check(client).json()
    assert result['proposal']['after']['hourly_wage'] is None
    assert [t['function']['name'] for t in provider.requests[5]['tools']] == ['propose_correction']


def test_live_investigator_cannot_invent_a_confirmed_wage(monkeypatch, wage):
    Provider(monkeypatch, tool_call('propose_correction', {'resolution': 'correct_wage', 'value': '25', 'evidence': ''}),
             tool_call('propose_correction', {'resolution': 'clear_wage', 'value': '', 'evidence': ''}),
             submit(verdict='agree'))
    with TestClient(app) as client:
        result = check(client).json()
        run = client.get('/runs/' + result['run_id'], headers=HEADERS).json()
    assert [s['status'] for s in run['trace']] == ['failed', 'completed']
    assert result['proposal']['after'] == {'hourly_wage': None, 'review_required': True}


def test_failed_review_keeps_the_proposal(monkeypatch, wage):
    Provider(monkeypatch, tool_call('propose_correction', {'resolution': 'clear_wage', 'value': '', 'evidence': ''}),
             *[tool_call('query_sql', {'sql': 'SELECT 1 AS one'})] * 6)
    with TestClient(app) as client:
        result = check(client).json()
    assert result['review'] is None and 'did not finish' in result['review_error']
    with engine.connect() as c:
        assert c.execute(select(proposals.c.status).where(proposals.c.issue_key == KEY)).scalar() == 'pending'


def test_unknown_finding_is_rejected():
    with TestClient(app) as client:
        assert check(client, 'wage_outlier:999999999').status_code == 400