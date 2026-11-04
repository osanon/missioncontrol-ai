from agent.runner import run
from tests.test_phase1 import Provider, tool_call, answer

METRICS = tool_call('calculate_metrics', {'start': '2026-07-01', 'end': '2026-09-30'})
FINAL = 'Stop investigating now.'


def test_model_that_never_stops_calling_tools_is_asked_for_its_answer(monkeypatch):
    provider = Provider(monkeypatch, *[METRICS] * 5, answer('581 clients served. [step 1: services]'))
    result = run('How many clients were served?', '2026-07-01', '2026-09-30')
    assert result['status'] == 'completed' and result['answer'] == '581 clients served. [step 1: services]'
    assert len(result['trace']) == 5
    last = provider.requests[-1]
    assert 'tools' not in last and last['messages'][-1]['content'].startswith(FINAL)
    assert all('tools' in r for r in provider.requests[:-1])


def test_blank_reply_after_tools_is_followed_by_a_request_for_the_answer(monkeypatch):
    provider = Provider(monkeypatch, METRICS, answer('\n\n'), answer('\n\n581 clients served. [step 1: services]'))
    result = run('How many clients were served?', '2026-07-01', '2026-09-30')
    assert result['answer'] == '581 clients served. [step 1: services]'
    assert len(provider.requests) == 3 and 'tools' not in provider.requests[2]


def test_no_answer_even_when_asked_keeps_the_existing_message(monkeypatch):
    Provider(monkeypatch, *[METRICS] * 5, answer(''))
    result = run('How many clients were served?', '2026-07-01', '2026-09-30')
    assert result['answer'].startswith('Investigation reached its tool limit')