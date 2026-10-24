import json
from agent.runner import run

def test_live_tool_loop_with_mock_provider(monkeypatch):
    monkeypatch.setenv('AGENT_MODE','live')
    monkeypatch.setenv('LLM_API_KEY','fake-test-key')
    monkeypatch.setenv('LLM_MODEL','gpt-5.4-mini')
    from agent import llm
    requests=[]
    class Response:
        def raise_for_status(self): pass
        def json(self):
            if len(requests)==1:
                return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'call-1','type':'function','function':{'name':'calculate_metrics','arguments':json.dumps({'start':'2026-07-01','end':'2026-09-30'})}}]}}]}
            return {'choices':[{'message':{'role':'assistant','content':'581 clients served. [step 1: services]'}}]}
    def fake_post(url,**kwargs):
        requests.append(kwargs['json'])
        return Response()
    monkeypatch.setattr(llm.httpx,'post',fake_post)
    result=run('How many clients were served?','2026-07-01','2026-09-30')
    assert result['mode']=='live'
    assert result['trace'][0]['result']['clients_served']==581
    assert '581' in requests[1]['messages'][-1]['content']
    names=[t['function']['name'] for t in requests[0]['tools']]
    assert 'approve' not in names and 'propose_correction' in names
