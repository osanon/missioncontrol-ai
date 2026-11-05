"""AI reviewer track record: decisions counted against what the AI reviewer had said."""
from fastapi.testclient import TestClient
from backend.db import engine
from backend.logic import log, propose, decide
from backend.main import app
from agent.reviewer import review_proposal
from tests.test_phase2 import enrollment  # noqa: F401  (fixture)

HEADERS = {'Authorization': 'Bearer test-analyst-token-000000000000000000'}


def trust(client):
    return client.get('/ai-trust', headers=HEADERS).json()


def test_trust_counts_followed_overruled_and_unsure():
    with TestClient(app) as client:
        before = trust(client)
        with engine.begin() as c:
            log(c, 'proposal_applied', {'ai_verdict': 'agree'}, 'alice')
            log(c, 'proposal_rejected', {'ai_verdict': 'disagree'}, 'alice')
            log(c, 'proposal_reevaluation_requested', {'ai_verdict': 'agree'}, 'bob')
            log(c, 'proposal_applied', {'ai_verdict': 'uncertain'}, 'bob')
            log(c, 'proposal_rejected', {'ai_verdict': None}, 'bob')
            log(c, 'proposal_superseded', {'ai_verdict': 'agree'}, 'bob')  # not a decision
        after = trust(client)
    assert after['decisions'] - before['decisions'] == 5 and after['reviewed'] - before['reviewed'] == 4
    assert (after['followed'] - before['followed'], after['overruled'] - before['overruled'], after['unsure'] - before['unsure']) == (2, 1, 1)
    assert after['by_verdict']['agree']['sent_back'] - before['by_verdict']['agree']['sent_back'] == 1
    assert after['by_verdict']['none']['rejected'] - before['by_verdict']['none']['rejected'] == 1
    assert after['agreement_rate'] is not None and 0 <= after['agreement_rate'] <= 100


def test_real_decision_is_counted_against_its_review(enrollment):
    p = propose(enrollment, actor='analyst', actor_kind='human')
    review = review_proposal(p['id'])
    with TestClient(app) as client:
        before = trust(client)['by_verdict'][review['verdict']]['rejected']
        decide(p['id'], 'reject', 'alice', 'Not supported by the service history.')
        assert trust(client)['by_verdict'][review['verdict']]['rejected'] == before + 1


def test_trust_requires_sign_in():
    with TestClient(app) as client:
        assert client.get('/ai-trust').status_code == 401