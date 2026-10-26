"""Browser sessions, public demo access, rate limits and the daily AI budget."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, delete
from backend.db import engine, employment, proposals, runs
from backend.main import app
from backend import sessions
from tests.test_phase1 import Provider, answer

APP = 'test-analyst-token-000000000000000000'
ALICE_TOKEN = 'test-alice-token-00000000000000000000'
CSRF = {'X-Requested-With': 'missioncontrol'}
JOB = 930001


@pytest.fixture
def job():
    with engine.begin() as c:
        c.execute(employment.insert().values(id=JOB, client_id=1, start_date='2026-07-01', hourly_wage=1500.0, review_required=False))
    yield f'wage_outlier:{JOB}'
    with engine.begin() as c:
        c.execute(delete(proposals).where(proposals.c.table_name == 'employment', proposals.c.record_id == JOB))
        c.execute(delete(employment).where(employment.c.id == JOB))


def signed_in(client, review_token=''):
    response = client.post('/session', json={'app_token': APP, 'review_token': review_token})
    assert response.status_code == 200
    return response


def test_session_cookie_signs_in_and_survives_reload(job):
    with TestClient(app) as client:
        assert client.get('/session').json()['authenticated'] is False
        assert client.get('/issues').status_code == 401
        response = signed_in(client)
        cookie = response.headers['set-cookie'].lower()
        assert 'httponly' in cookie and 'samesite=strict' in cookie and APP not in cookie
        assert client.get('/session').json() == {'authenticated': True, 'reviewer': None, 'demo': False, 'public_demo': False}
        assert client.get('/issues').status_code == 200  # A "reload" is just another request with the cookie.
        assert client.post('/proposals', json={'issue_key': job}).status_code == 403  # Cookie writes need the CSRF header.
        assert client.post('/proposals', json={'issue_key': job}, headers=CSRF).status_code == 201
        client.delete('/session')
        assert client.get('/issues').status_code == 401


def test_wrong_tokens_are_rejected():
    with TestClient(app) as client:
        assert client.post('/session', json={'app_token': 'wrong'}).status_code == 401
        assert client.post('/session', json={'app_token': APP, 'review_token': 'wrong'}).status_code == 403
        assert client.post('/session', json={'app_token': 'tést'}).status_code == 401  # Non-ASCII must not crash.
        assert client.get('/issues', headers={'Authorization': 'Bearer tést'.encode()}).status_code == 401


def test_reviewer_session_decides_under_their_name(job):
    with TestClient(app) as client:
        signed_in(client)
        p = client.post('/proposals', json={'issue_key': job}, headers=CSRF).json()
        assert client.post(f"/approvals/{p['id']}", json={'decision': 'approve'}, headers=CSRF).status_code == 403
        assert client.post('/session/reviewer', json={'review_token': 'wrong'}, headers=CSRF).status_code == 403
        assert client.post('/session/reviewer', json={'review_token': ALICE_TOKEN}, headers=CSRF).json()['reviewer'] == 'alice'
        assert client.post(f"/approvals/{p['id']}", json={'decision': 'approve'}, headers=CSRF).json()['status'] == 'applied'
    with engine.connect() as c:
        assert c.scalar(select(proposals.c.decided_by).where(proposals.c.id == p['id'])) == 'alice'


def test_removed_reviewer_loses_access_immediately(job, monkeypatch):
    with TestClient(app) as client:
        signed_in(client, ALICE_TOKEN)
        p = client.post('/proposals', json={'issue_key': job}, headers=CSRF).json()
        monkeypatch.setenv('REVIEWERS', 'bob:test-bob-token-0000000000000000000000')
        assert client.get('/session').json()['reviewer'] is None
        assert client.post(f"/approvals/{p['id']}", json={'decision': 'approve'}, headers=CSRF).status_code == 403


def test_tampered_or_expired_cookies_are_rejected():
    forged = sessions.encode('alice')
    body, sig = forged.split('.')
    assert sessions.decode(forged)['reviewer'] == 'alice'
    assert sessions.decode(body + '.' + sig[::-1]) is None
    assert sessions.decode(sessions.encode('alice', now=1)) is None
    with TestClient(app) as client:
        client.cookies.set(sessions.COOKIE, 'not-a-session')
        assert client.get('/issues').status_code == 401


def test_demo_access_only_when_enabled(job, monkeypatch):
    with TestClient(app) as client:
        assert client.post('/demo/session', json={'role': 'reviewer'}).status_code == 404
        monkeypatch.setenv('PUBLIC_DEMO', 'true')
        assert client.get('/session').json()['public_demo'] is True
        assert client.post('/demo/session', json={'role': 'reviewer'}).json() == {'authenticated': True, 'reviewer': 'demo-reviewer', 'demo': True}
        p = client.post('/proposals', json={'issue_key': job}, headers=CSRF).json()
        assert client.post(f"/approvals/{p['id']}", json={'decision': 'reject'}, headers=CSRF).status_code == 200
        assert client.post('/session/reviewer', json={'review_token': ALICE_TOKEN}, headers=CSRF).status_code == 409
        monkeypatch.setenv('PUBLIC_DEMO', 'false')  # Turning the demo off ends demo sessions.
        assert client.get('/issues').status_code == 401
    with engine.connect() as c:
        assert c.scalar(select(proposals.c.decided_by).where(proposals.c.id == p['id'])) == 'demo-reviewer'


def test_demo_reviewer_name_is_reserved(monkeypatch):
    from backend.reviewers import load_reviewers
    monkeypatch.setenv('REVIEWERS', 'demo-reviewer:' + 'x' * 30)
    with pytest.raises(RuntimeError, match='reserved'):
        load_reviewers()


def test_sign_in_attempts_are_rate_limited(monkeypatch):
    monkeypatch.setenv('LOGIN_RATE_PER_MINUTE', '3')
    with TestClient(app) as client:
        codes = [client.post('/session', json={'app_token': 'wrong'}).status_code for _ in range(4)]
        assert codes == [401, 401, 401, 429]
        assert client.post('/session', json={'app_token': APP}).status_code == 429
        other = client.post('/session', json={'app_token': APP}, headers={'X-Real-IP': '203.0.113.9'})
        assert other.status_code == 200 and 'Retry-After' not in other.headers


def test_live_ai_requests_are_rate_limited_per_ip(monkeypatch):
    Provider(monkeypatch, answer('One.'), answer('Two.'))
    monkeypatch.setenv('AI_RATE_PER_HOUR', '1')
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer ' + APP}
        assert client.post('/ask', headers=headers, json={'question': 'First question'}).status_code == 200
        limited = client.post('/ask', headers=headers, json={'question': 'Second question'})
        assert limited.status_code == 429 and 'Retry-After' in limited.headers


def test_demo_mode_ai_requests_are_not_limited(monkeypatch):
    monkeypatch.setenv('AI_RATE_PER_HOUR', '1')
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer ' + APP}
        assert [client.post('/ask', headers=headers, json={'question': 'Check data quality'}).status_code for _ in range(3)] == [200] * 3


def test_daily_ai_budget_stops_live_runs(monkeypatch):
    Provider(monkeypatch, {**answer('Used some tokens.'), 'usage': {'prompt_tokens': 900, 'completion_tokens': 200}})
    with engine.connect() as c:
        from sqlalchemy import func
        used = c.scalar(select(func.coalesce(func.sum(func.coalesce(runs.c.input_tokens, 0) + func.coalesce(runs.c.output_tokens, 0)), 0)))
    monkeypatch.setenv('AI_DAILY_TOKEN_BUDGET', str(used + 1000))
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer ' + APP}
        assert client.post('/ask', headers=headers, json={'question': 'First question'}).status_code == 200
        blocked = client.post('/ask', headers=headers, json={'question': 'Second question'})
        assert blocked.status_code == 429 and 'budget' in blocked.json()['detail']


def test_reset_restores_the_planted_findings(tmp_path):
    from sqlalchemy import create_engine, func
    from backend.db import clients, audit, ai_reviews
    from database.migrate import upgrade
    from database.seed import seed
    from database.reset import reset
    other = create_engine(f'sqlite:///{tmp_path}/reset.db')
    upgrade(other)
    seed(other)
    with other.begin() as c:
        c.execute(employment.update().where(employment.c.id == 1).values(hourly_wage=20.0))
        c.execute(audit.insert().values(id='x', occurred_at='2026-01-01', actor='alice', event='test', details={}))
    reset(other)
    with other.connect() as c:
        assert c.scalar(select(func.count()).select_from(clients)) == 2000
        assert c.scalar(select(employment.c.hourly_wage).where(employment.c.id == 1)) == 1500
        assert c.scalar(select(func.count()).select_from(audit)) == 0
        assert c.scalar(select(func.count()).select_from(ai_reviews)) == 0
    other.dispose()


def test_reset_requires_confirmation():
    import subprocess, sys
    out = subprocess.run([sys.executable, '-m', 'database.reset'], capture_output=True, text=True)
    assert out.returncode != 0 and '--yes' in out.stderr
