import httpx
import pytest
from agent import llm

CFG = llm.LLMConfig('fake-test-key', 'test-model', 'https://provider.test/v1')
OK = {'choices': [{'message': {'role': 'assistant', 'content': 'Done.'}}]}


def status(code, headers=None):
    request = httpx.Request('POST', CFG.base + '/chat/completions')
    return httpx.HTTPStatusError('error', request=request, response=httpx.Response(code, headers=headers, request=request))


@pytest.fixture
def provider(monkeypatch):
    """Scripted provider: each entry is a response body or an exception. Records requests and waits."""
    state = {'script': [], 'calls': 0, 'waits': []}

    class Response:
        def __init__(self, item):
            self.item = item

        def raise_for_status(self):
            if isinstance(self.item, httpx.HTTPStatusError):
                raise self.item

        def json(self):
            return self.item

    def post(url, **kwargs):
        state['calls'] += 1
        item = state['script'].pop(0)
        if isinstance(item, httpx.TransportError):
            raise item
        return Response(item)

    monkeypatch.setattr(llm.httpx, 'post', post)
    monkeypatch.setattr(llm, 'sleep', state['waits'].append)
    return state


def deadline(seconds=100):
    return llm.time.monotonic() + seconds


@pytest.mark.parametrize('failure', [status(429), status(500), status(503), httpx.ConnectError('down'), httpx.ReadTimeout('slow')])
def test_temporary_failures_are_retried(provider, failure):
    provider['script'] = [failure, OK]
    assert llm.complete(CFG, {}, deadline()) == OK
    assert provider['calls'] == 2 and provider['waits'] == [1]


def test_gives_up_after_three_attempts(provider):
    provider['script'] = [status(503), status(503), status(503), OK]
    with pytest.raises(llm.ProviderError, match='Inference request failed'):
        llm.complete(CFG, {}, deadline())
    assert provider['calls'] == 3 and provider['waits'] == [1, 3]


@pytest.mark.parametrize('code', [400, 401, 403, 404])
def test_permanent_failures_are_not_retried(provider, code):
    provider['script'] = [status(code), OK]
    with pytest.raises(llm.ProviderError):
        llm.complete(CFG, {}, deadline())
    assert provider['calls'] == 1 and provider['waits'] == []


def test_retry_after_header_is_respected_up_to_ten_seconds(provider):
    provider['script'] = [status(429, {'retry-after': '4'}), status(429, {'retry-after': '120'}), OK]
    assert llm.complete(CFG, {}, deadline()) == OK
    assert provider['waits'] == [4, 10]


def test_no_retry_that_would_pass_the_run_time_limit(provider):
    provider['script'] = [status(503), OK]
    with pytest.raises(llm.ProviderError, match='Inference request failed'):
        llm.complete(CFG, {}, deadline(1.5))
    assert provider['calls'] == 1


def test_no_request_once_the_run_time_limit_is_used_up(provider):
    with pytest.raises(llm.ProviderError, match='took too long'):
        llm.complete(CFG, {}, deadline(0))
    assert provider['calls'] == 0
