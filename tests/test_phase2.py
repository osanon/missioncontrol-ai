"""Phase 2: independent AI reviewer (demo rules and live model), review history, and decisions recorded against it."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete, update
from backend.db import engine, enrollments, services, proposals, audit, runs, ai_reviews
from backend.logic import propose, decide
from backend.main import app
from tests.test_merges import pair, make_merge  # noqa: F401  (pair is a fixture)
from tests.test_phase1 import Provider, tool_call, answer

HEADERS = {'Authorization': 'Bearer test-analyst-token-000000000000000000'}
ALICE = {**HEADERS, 'X-Review-Token': 'test-alice-token-00000000000000000000'}
ENROLLMENT = 8101
KEY = f'missing_exit:{ENROLLMENT}'
SERVICE = 990101
EVIDENCE = 'Program manager confirmed the discharge date by email.'


@pytest.fixture
def enrollment():
    with engine.begin() as c:
        c.execute(enrollments.insert().values(id=ENROLLMENT, client_id=1, program_id=1, start_date='2026-01-01', end_date=None,
                                              status='exited', review_required=False))
        c.execute(services.insert().values(id=SERVICE, client_id=1, program_id=1, service_date='2026-03-01', units=1.0, review_required=False))
    yield KEY
    with engine.begin() as c:
        ids = [r.id for r in c.execute(select(proposals.c.id).where(proposals.c.table_name == 'enrollments', proposals.c.record_id == ENROLLMENT))]
        c.execute(delete(ai_reviews).where(ai_reviews.c.proposal_id.in_(ids)))
        c.execute(delete(proposals).where(proposals.c.id.in_(ids)))
        c.execute(delete(services).where(services.c.id == SERVICE))
        c.execute(delete(enrollments).where(enrollments.c.id == ENROLLMENT))


def exit_proposal(key, value):
    return propose(key, resolution='set_exit_date', value=value, evidence=EVIDENCE)


def reviews_for(pid):
    with engine.connect() as c:
        return [dict(r) for r in c.execute(select(ai_reviews).where(ai_reviews.c.proposal_id == pid).order_by(ai_reviews.c.created_at)).mappings()]


def usage(prompt, completion):
    return {'usage': {'prompt_tokens': prompt, 'completion_tokens': completion}}


# Demo reviewer

def test_demo_review_disagrees_when_services_follow_exit_date(enrollment):
    p = exit_proposal(enrollment, '2026-02-01')
    with TestClient(app) as client:
        review = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS)
        assert review.status_code == 201
        review = review.json()
        assert (review['verdict'], review['confidence'], review['reviewer'], review['mode']) == ('disagree', 'high', 'agent:reviewer', 'demo')
        assert 'after the proposed exit date' in review['summary']
        listed = next(x for x in client.get('/proposals', headers=HEADERS).json() if x['id'] == p['id'])
        assert listed['ai_review']['id'] == review['id'] and listed['status'] == 'pending'
        run = client.get('/runs/' + review['run_id'], headers=HEADERS).json()
        assert run['kind'] == 'reviewer' and run['status'] == 'completed'
        assert 'services_after_date' in [s['tool'] for s in run['trace']]
        assert '# MissionControl AI review' in client.get('/reports/' + review['run_id'], headers=HEADERS).text
        assert client.get('/runs/missing', headers=HEADERS).status_code == 404
    with engine.connect() as c:
        assert c.scalar(select(enrollments.c.end_date).where(enrollments.c.id == ENROLLMENT)) is None
        assert any(e['details']['run_id'] == review['run_id'] and e['details']['verdict'] == 'disagree' and e['actor'] == 'agent:reviewer'
                   for e in c.execute(select(audit).where(audit.c.event == 'ai_review_completed')).mappings())


def test_demo_review_agrees_when_service_history_is_consistent(enrollment):
    p = exit_proposal(enrollment, '2026-10-01')
    with TestClient(app) as client:
        review = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
    assert review['verdict'] == 'agree' and any('claim' in c for c in review['concerns'])


def test_demo_review_disagrees_when_record_changed(enrollment):
    p = exit_proposal(enrollment, '2026-10-01')
    with engine.begin() as c:
        c.execute(update(enrollments).where(enrollments.c.id == ENROLLMENT).values(status='active'))
    with TestClient(app) as client:
        review = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
    assert (review['verdict'], review['confidence']) == ('disagree', 'high') and 'status' in review['summary']


def test_merge_review_is_uncertain_when_contact_details_differ(pair):
    p = make_merge()
    with TestClient(app) as client:
        review = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
    assert review['verdict'] == 'uncertain' and 'email' in review['concerns'][0]


def test_rerun_keeps_history_and_shows_latest(enrollment):
    p = exit_proposal(enrollment, '2026-02-01')
    with TestClient(app) as client:
        first = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
        second = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
        listed = next(x for x in client.get('/proposals', headers=HEADERS).json() if x['id'] == p['id'])
    assert first['id'] != second['id'] and listed['ai_review']['id'] == second['id']
    assert [r['id'] for r in reviews_for(p['id'])] == [first['id'], second['id']]


def test_only_pending_proposals_can_be_reviewed(enrollment):
    p = exit_proposal(enrollment, '2026-10-01')
    decide(p['id'], 'reject', 'alice')
    with TestClient(app) as client:
        assert client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).status_code == 409
        assert client.post('/proposals/not-a-proposal/ai-review', headers=HEADERS).status_code == 400
        assert client.post(f"/proposals/{p['id']}/ai-review").status_code == 401


def test_decision_records_ai_verdict(enrollment):
    p = exit_proposal(enrollment, '2026-02-01')
    with TestClient(app) as client:
        review = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
        assert client.post(f"/approvals/{p['id']}", headers=ALICE, json={'decision': 'reevaluate', 'note': review['summary']}).status_code == 200
    with engine.connect() as c:
        [event] = [e for e in c.execute(select(audit).where(audit.c.event == 'proposal_reevaluation_requested')).mappings()
                   if e['details']['proposal_id'] == p['id']]
    assert event['details']['ai_verdict'] == 'disagree' and event['details']['ai_review_id'] == review['id']


def test_merge_decision_records_ai_verdict(pair):
    p = make_merge()
    with TestClient(app) as client:
        review = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
    decide(p['id'], 'reject', 'alice')
    with engine.connect() as c:
        [event] = [e for e in c.execute(select(audit).where(audit.c.event == 'proposal_rejected')).mappings()
                   if e['details']['proposal_id'] == p['id']]
    assert event['details']['ai_verdict'] == review['verdict']


# Live reviewer

def submit(verdict='disagree', confidence='high', summary='Services continue after the proposed exit date.', concerns=('Check the service log.',), call_id='call-9'):
    return tool_call('submit_review', {'verdict': verdict, 'confidence': confidence, 'summary': summary, 'concerns': list(concerns)}, call_id)


def test_live_review_uses_read_only_tools_and_records_model_and_tokens(monkeypatch, enrollment):
    monkeypatch.setenv('LLM_REVIEW_MODEL', 'review-model')
    p = exit_proposal(enrollment, '2026-02-01')
    provider = Provider(monkeypatch,
                        {**tool_call('query_sql', {'sql': 'SELECT MAX(service_date) AS latest FROM services WHERE client_id = 1 AND program_id = 1'}), **usage(100, 20)},
                        {**submit(), **usage(150, 40)})
    with TestClient(app) as client:
        review = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
    assert (review['verdict'], review['mode'], review['model']) == ('disagree', 'live', 'review-model')
    first = provider.requests[0]
    assert {t['function']['name'] for t in first['tools']} == {'inspect_schema', 'query_sql', 'submit_review'}
    assert first['model'] == 'review-model' and first['messages'][0]['role'] == 'system'
    assert EVIDENCE in first['messages'][1]['content'] and 'untrusted' in first['messages'][1]['content']
    assert len(provider.requests) == 2  # Stops as soon as the review is submitted.
    with engine.connect() as c:
        run = c.execute(select(runs).where(runs.c.id == review['run_id'])).mappings().one()
    assert (run['input_tokens'], run['output_tokens'], run['kind']) == (250, 60, 'reviewer')
    assert [s['tool'] for s in run['trace']] == ['query_sql', 'submit_review']


def test_live_review_rejects_invalid_submission_then_accepts_valid(monkeypatch, enrollment):
    p = exit_proposal(enrollment, '2026-02-01')
    Provider(monkeypatch, submit(verdict='approve', call_id='bad'), submit(verdict='uncertain', confidence='low'))
    with TestClient(app) as client:
        review = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
        run = client.get('/runs/' + review['run_id'], headers=HEADERS).json()
    assert review['verdict'] == 'uncertain'
    assert [s['status'] for s in run['trace']] == ['failed', 'completed']


def test_live_review_only_first_submission_counts(monkeypatch, enrollment):
    p = exit_proposal(enrollment, '2026-02-01')
    double = submit(verdict='disagree')
    double['choices'][0]['message']['tool_calls'] += submit(verdict='agree', call_id='call-10')['choices'][0]['message']['tool_calls']
    Provider(monkeypatch, double)
    with TestClient(app) as client:
        review = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS).json()
    assert review['verdict'] == 'disagree' and len(reviews_for(p['id'])) == 1


def test_live_review_without_submission_fails_and_is_saved(monkeypatch, enrollment):
    p = exit_proposal(enrollment, '2026-02-01')
    Provider(monkeypatch, answer('Looks fine to me.'))
    with TestClient(app) as client:
        response = client.post(f"/proposals/{p['id']}/ai-review", headers=HEADERS)
    assert response.status_code == 502 and 'without submitting a review' in response.json()['detail']
    assert reviews_for(p['id']) == []
    with engine.connect() as c:
        failed = [r for r in c.execute(select(runs).where(runs.c.kind == 'reviewer', runs.c.status == 'failed')).mappings()
                  if r['question'] == f"Review proposal {p['id']}"]
    assert failed and 'without submitting' in failed[0]['error']


def test_reviewer_has_no_write_tools():
    from agent.reviewer import live_dispatch, REVIEW_TOOLS
    names = {t['function']['name'] for t in REVIEW_TOOLS}
    assert not names & {'propose_correction', 'propose_merge', 'approve', 'reject', 'decide'}
    dispatch = live_dispatch({})
    with pytest.raises(ValueError):
        dispatch('propose_correction', {'issue_key': KEY, 'resolution': 'follow_up', 'value': '', 'evidence': ''})
    with pytest.raises(ValueError):
        dispatch('query_sql', {'sql': f'UPDATE enrollments SET status = \'active\' WHERE id = {ENROLLMENT}'})


def test_analyst_live_run_records_tokens(monkeypatch):
    Provider(monkeypatch, {**answer('No tools needed.'), **usage(30, 5)})
    with TestClient(app) as client:
        result = client.post('/ask', headers=HEADERS, json={'question': 'Say hello.'}).json()
    assert (result['input_tokens'], result['output_tokens'], result['kind']) == (30, 5, 'analyst')
