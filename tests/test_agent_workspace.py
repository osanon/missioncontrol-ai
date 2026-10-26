import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,update,delete
from backend.main import app
from backend.db import engine,clients,enrollments,proposals,audit
from backend.logic import propose,decide,Conflict,list_proposals
from backend.client_directory import profile,edit
from backend.ai_review import review
from agent import runner
HEADERS={'Authorization':'Bearer test-analyst-token-000000000000000000'}
REVIEW={**HEADERS,'X-Review-Token':'test-review-token-0000000000000000000'}
@pytest.fixture
def finding():
    with engine.begin() as c:c.execute(enrollments.insert().values(id=8801,client_id=1,program_id=1,start_date='2026-01-01',end_date=None,status='exited',review_required=False))
    yield 'missing_exit:8801'
    with engine.begin() as c:
        c.execute(delete(proposals).where(proposals.c.record_id==8801))
        c.execute(delete(enrollments).where(enrollments.c.id==8801))
def mock_model(monkeypatch,responses):
    monkeypatch.setenv('AGENT_MODE','live');monkeypatch.setenv('LLM_API_KEY','fake-test-key');monkeypatch.setenv('LLM_MODEL','test-model')
    it=iter(responses)
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'message':next(it)}]}
    monkeypatch.setattr(runner.httpx,'post',lambda *a,**kw:Response())
def call(name,args):return {'content':None,'tool_calls':[{'id':'call1','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
def args(key):return {'issue_key':key,'resolution':'reactivate_enrollment','value':'','evidence':'Reviewer confirms the enrollment is still active.'}
def test_directory_auth_search_profile():
    with TestClient(app) as c:
        assert c.get('/clients').status_code==401
        data=c.get('/clients',headers=HEADERS,params={'q':'DEMO-00001'}).json()
        assert len(data['rows'])>=1 and len(data['rows'])<=25
        p=c.get('/clients/1',headers=HEADERS).json()
        assert 'enrollments' in p['groups'] and p['editable']['clients']==['full_name','birth_date','email']
def test_edit_auth_stale_and_audit():
    p=profile(1);old=p['client']['email']
    payload={'table':'clients','record_id':1,'version':p['version'],'patch':{'email':'synthetic@example.test'},'note':'Create a synthetic email test case.'}
    with TestClient(app) as c:
        assert c.post('/clients/1/edit',headers=HEADERS,json=payload).status_code==403
        assert c.post('/clients/1/edit',headers=REVIEW,json=payload).status_code==200
        assert c.post('/clients/1/edit',headers=REVIEW,json=payload).status_code==409
    with engine.begin() as c:
        assert c.execute(select(audit).where(audit.c.event=='test_record_edited')).first()
        c.execute(update(clients).where(clients.c.id==1).values(email=old))
def test_edit_rejects_ids_ownership_nonfinite_and_pending(finding):
    p=profile(1);row=next(r for r in p['groups']['enrollments'] if r['record']['id']==8801)
    for patch in [{'client_id':2},{'start_date':None},{'status':'invented'}]:
        with pytest.raises(ValueError):edit(1,'enrollments',8801,row['version'],patch,'Synthetic test edit.','tester')
    with pytest.raises(ValueError):edit(2,'enrollments',8801,row['version'],{'status':'active'},'Synthetic test edit.','tester')
    propose(finding,resolution='follow_up')
    with pytest.raises(Conflict):edit(1,'enrollments',8801,row['version'],{'status':'active'},'Synthetic test edit.','tester')
def test_demo_and_token_gates(finding):
    with TestClient(app) as c:
        assert c.post('/ai-review',headers=HEADERS,json={'issue_key':finding}).status_code==403
        assert c.post('/ai-review',headers=REVIEW,json={'issue_key':finding}).status_code==400

def test_ai_proposal_does_not_apply_and_revision_preserves_history(monkeypatch,finding):
    mock_model(monkeypatch,[call('propose_correction',args(finding)),{'content':'Proposed reactivation based on reviewer confirmation.'}])
    result=review(finding,'Program staff confirm the enrollment is still active.')
    pid=result['proposal_id'];assert pid
    with engine.connect() as c:assert c.scalar(select(enrollments.c.status).where(enrollments.c.id==8801))=='exited'
    mock_model(monkeypatch,[call('propose_correction',{'issue_key':finding,'resolution':'set_exit_date','value':'2026-09-10','evidence':'Reviewer confirms exit date September 10.'}),{'content':'Revised to the confirmed exit date.'}])
    revised=review(finding,'Correction: staff confirmed the exit date was September 10, 2026.',pid)
    assert revised['proposal_id']!=pid
    with engine.connect() as c:assert c.scalar(select(proposals.c.status).where(proposals.c.id==pid))=='superseded'
    decide(revised['proposal_id'],'approve','tester')
    with engine.connect() as c:assert c.scalar(select(enrollments.c.end_date).where(enrollments.c.id==8801))=='2026-09-10'
def test_revision_without_proposal_blocks_old_approval_but_allows_rejection(monkeypatch,finding):
    p=propose(finding,resolution='follow_up')
    mock_model(monkeypatch,[{'content':'Need confirmed exit date. No new proposal.'}])
    result=review(finding,'Please reassess using the enrollment history.',p['id'])
    assert not result['proposal_id']
    viewed=next(x for x in list_proposals() if x['id']==p['id']);assert viewed['revision_requested']
    with pytest.raises(Conflict):decide(p['id'],'approve','tester')
    assert decide(p['id'],'reject','tester')['status']=='rejected'
def test_ai_cannot_propose_other_finding_or_approve(monkeypatch,finding):
    mock_model(monkeypatch,[call('propose_correction',args('missing_exit:999999')),call('approve',{'id':'anything'}),{'content':'Cannot make that change.'}])
    result=review(finding)
    assert not result['proposal_id']
    assert all(s['status']=='failed' for s in result['run']['trace'])

def test_provider_failure_preserves_revision_block(monkeypatch,finding):
    import httpx
    p=propose(finding,resolution='follow_up')
    monkeypatch.setenv('AGENT_MODE','live');monkeypatch.setenv('LLM_API_KEY','test');monkeypatch.setenv('LLM_MODEL','test')
    def fail(*a,**kw):raise httpx.ConnectError('simulation')
    monkeypatch.setattr(runner.httpx,'post',fail)
    with pytest.raises(ValueError,match='Inference request failed'):review(finding,'Please investigate the missing date again.',p['id'])
    with pytest.raises(Conflict):decide(p['id'],'approve','tester')
    decide(p['id'],'reject','tester')

def test_merge_ai_revision_and_block(monkeypatch):
    from backend.merges import duplicate_candidates,merge_preview,propose_merge
    source=1989;target=duplicate_candidates(source)['candidates'][0]['id']
    p=propose_merge(source,target,merge_preview(source,target)['preview_token'],'Synthetic identity confirmed for test.')
    try:
        token=merge_preview(source,target,p['id'])['preview_token']
        mock_model(monkeypatch,[call('preview_merge',{'source_id':str(source),'target_id':str(target)}),call('propose_merge',{'source_id':str(source),'target_id':str(target),'preview_token':token,'evidence':'Reviewer reconfirmed matching identity and retention choice.'}),{'content':'Replacement merge awaits approval.'}])
        result=review('duplicate:'+str(source),'Identity reconfirmed; please retain the same target profile.',p['id'])
        assert result['proposal_id'] and result['proposal_id']!=p['id']
        assert all(s['status']=='completed' for s in result['run']['trace'])
        decide(result['proposal_id'],'reject','tester')
    finally:
        with engine.begin() as c:c.execute(delete(proposals).where(proposals.c.record_id==source,proposals.c.table_name=='clients'))

def test_postgres_directory_column_grants():
    import os
    from backend.db import engine_for
    url=os.getenv('MC_TEST_APP_DATABASE_URL')
    if not url:pytest.skip('PostgreSQL application-role check requires Codespaces test project.')
    from sqlalchemy import text
    db=engine_for(url)
    with db.connect() as c:
        for table,column in [('clients','email'),('enrollments','start_date'),('employment','end_date'),('services','service_date'),('housing','destination')]:
            assert c.scalar(text('SELECT has_column_privilege(current_user,:t,:col,\'UPDATE\')'),{'t':table,'col':column})
    db.dispose()
