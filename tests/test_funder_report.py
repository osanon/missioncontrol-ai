"""Funder report: verified figures, data-quality notes, and a narrative whose numbers are checked against the figures."""
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.db import engine, runs
from backend.main import app
from agent.funder_report import facts, unverified_numbers
from tests.test_phase1 import Provider, answer

HEADERS = {'Authorization': 'Bearer test-analyst-token-000000000000000000'}
PERIOD = {'start': '2026-07-01', 'end': '2026-09-30'}
FULL = '## Summary\nA good quarter.\n## Highlights\n- Steady.\n## Data quality\nSee the notes.'


def draft(client, body=PERIOD):
    return client.post('/funder-report', headers=HEADERS, json=body)


def cut_off(text):
    return {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'length'}]}


def test_demo_report_uses_verified_figures_and_passes_the_number_check():
    with TestClient(app) as client:
        metrics = client.get('/metrics?start=2026-07-01&end=2026-09-30', headers=HEADERS).json()
        report = draft(client).json()
    assert report['mode'] == 'demo' and report['check'] == {'unverified_numbers': [], 'missing_sections': []}
    assert str(metrics['clients_served']) in report['narrative'] and str(metrics['new_jobs']) in report['narrative']
    labels = {f['label']: f['value'] for f in report['figures']}
    assert labels['Clients served (distinct people)'] == metrics['clients_served']
    assert any('open data finding' in n for n in report['notes'])
    assert report['markdown'].startswith('# Funder report draft: 2026-07-01 to 2026-09-30') and 'Review before sending' in report['markdown']


def test_number_check_flags_invented_or_recalculated_numbers():
    figures, notes = facts('2026-07-01', '2026-09-30')
    served = next(f['value'] for f in figures if f['label'].startswith('Clients served'))
    text = f'We served {served:,} people in 2026, roughly 1.7 times last year, and placed 9999 people in jobs.'
    assert unverified_numbers(text, figures, notes, '2026-07-01', '2026-09-30') == ['1.7', '9999']


def test_live_report_sends_figures_without_tools_and_flags_made_up_numbers(monkeypatch):
    provider = Provider(monkeypatch, {**answer('## Summary\nWe served 123456 people.'), 'usage': {'prompt_tokens': 400, 'completion_tokens': 60}})
    with TestClient(app) as client:
        report = draft(client).json()
    sent = provider.requests[0]
    assert 'tools' not in sent and 'Clients served (distinct people)' in sent['messages'][1]['content']
    assert 'Quote each number exactly' in sent['messages'][0]['content'] and '2026-07-01 to 2026-09-30' in sent['messages'][0]['content']
    assert report['mode'] == 'live' and report['check']['unverified_numbers'] == ['123456']
    assert 'not verified figures: 123456' in report['markdown'] and report['check']['missing_sections'] == ['Highlights', 'Data quality']
    with engine.connect() as c:
        run = c.execute(select(runs).where(runs.c.id == report['run_id'])).mappings().one()
    assert (run['kind'], run['status'], run['input_tokens'], run['output_tokens']) == ('reporter', 'completed', 400, 60)


def test_cut_off_report_is_retried_with_a_bigger_allowance(monkeypatch):
    provider = Provider(monkeypatch, cut_off('## Summary\nFor'), answer(FULL))
    with TestClient(app) as client:
        report = draft(client).json()
    assert [r['max_completion_tokens'] for r in provider.requests] == [4000, 8000]
    assert report['narrative'] == FULL and report['check'] == {'unverified_numbers': [], 'missing_sections': []}


def test_report_cut_off_twice_fails_instead_of_showing_half_a_report(monkeypatch):
    Provider(monkeypatch, cut_off('## Summary\nFor'), cut_off('## Summary\nFor the'))
    with TestClient(app) as client:
        response = draft(client)
    assert response.status_code == 502 and 'cut off' in response.json()['detail']


def test_blank_live_report_fails_cleanly_and_is_saved(monkeypatch):
    Provider(monkeypatch, answer('\n\n'))
    with TestClient(app) as client:
        response = draft(client)
    assert response.status_code == 502 and 'did not finish' in response.json()['detail']
    with engine.connect() as c:
        assert c.execute(select(runs.c.status).where(runs.c.kind == 'reporter').order_by(runs.c.created_at.desc())).first()[0] == 'failed'


def test_report_requires_sign_in_and_a_valid_period():
    with TestClient(app) as client:
        assert client.post('/funder-report', json=PERIOD).status_code == 401
        assert draft(client, {'start': '2026-09-30', 'end': '2026-07-01'}).status_code == 400
        assert draft(client, {'start': 'last quarter', 'end': '2026-07-01'}).status_code == 422