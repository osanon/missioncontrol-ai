import os
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update, delete, func
from backend.db import engine, clients, client_merges, DATA_TABLES, proposals, audit, followups, engine_for, ai_reviews
from backend.main import app
from backend.logic import decide, propose, issues, metrics, Conflict
from backend.merges import duplicate_candidates, merge_preview, propose_merge, LINK_TABLES

SOURCE, TARGET, THIRD = 910101, 910102, 910103
HEADERS = {'Authorization': 'Bearer test-analyst-token-000000000000000000'}
REVIEW = {**HEADERS, 'X-Review-Token': 'test-review-token-0000000000000000000'}
EVIDENCE = 'Simulated identity confirmation: source documents establish the same fictional person.'


@pytest.fixture
def pair():
    with engine.begin() as c:
        for cid in (SOURCE, TARGET, THIRD):
            c.execute(clients.insert().values(id=cid, external_id=f'MERGE-TEST-{cid}', full_name='Merge Test Person',
                      birth_date='1980-01-01', email=f'{cid}@example.invalid', review_required=cid == SOURCE))
        for cid in (SOURCE, TARGET):
            for name in LINK_TABLES:
                row = {'id': cid, 'client_id': cid}
                if name == 'enrollments':
                    row.update(program_id=1, start_date='2026-07-01', end_date=None, status='active', review_required=False)
                elif name == 'services':
                    row.update(program_id=1, service_date='2026-07-01', units=1.0, review_required=False)
                elif name == 'employment':
                    row.update(start_date='2026-07-01', hourly_wage=20.0, review_required=False)
                elif name == 'housing':
                    row.update(entry_date='2026-07-01', exit_date='2026-08-01', destination='stable')
                else:
                    row.update(assessment_date='2026-07-01', kind='test', score=50.0)
                c.execute(DATA_TABLES[name].insert().values(**row))
            c.execute(followups.insert().values(id=cid, employment_id=cid, due_date='2026-10-01', retained=None))
    yield
    with engine.begin() as c:
        c.execute(delete(client_merges).where(client_merges.c.source_id.in_([SOURCE, TARGET, THIRD])))
        ids = [r.id for r in c.execute(select(proposals.c.id).where(proposals.c.record_id.in_([SOURCE, TARGET, THIRD])))]
        c.execute(delete(ai_reviews).where(ai_reviews.c.proposal_id.in_(ids)))
        c.execute(delete(proposals).where(proposals.c.record_id.in_([SOURCE, TARGET, THIRD])))
        c.execute(delete(followups).where(followups.c.id.in_([SOURCE, TARGET])))
        for name in LINK_TABLES:
            t = DATA_TABLES[name]
            c.execute(delete(t).where(t.c.id.in_([SOURCE, TARGET, THIRD])))
        c.execute(delete(clients).where(clients.c.id.in_([SOURCE, TARGET, THIRD])))


def make_merge(source=SOURCE, target=TARGET, replaces_id=None):
    preview = merge_preview(source, target, replaces_id)
    return propose_merge(source, target, preview['preview_token'], EVIDENCE, replaces_id)


def owner(name='services', rid=SOURCE):
    t = DATA_TABLES[name]
    with engine.connect() as c:
        return c.scalar(select(t.c.client_id).where(t.c.id == rid))


def test_merge_preview_approval_auth_links_metrics_and_audit(pair):
    before = metrics()
    with TestClient(app) as c:
        assert c.get(f'/clients/{SOURCE}/duplicates').status_code == 401
        candidates = c.get(f'/clients/{SOURCE}/duplicates', headers=HEADERS).json()
        assert {p['id'] for p in candidates['candidates']} == {TARGET, THIRD}
        preview = c.get(f'/merges/preview?source_id={SOURCE}&target_id={TARGET}', headers=HEADERS).json()
        assert preview['counts']['services'] == {'move': 1, 'keep': 1}
        request = {'source_id': SOURCE, 'target_id': TARGET, 'preview_token': preview['preview_token'], 'evidence': EVIDENCE}
        p = c.post('/merges', headers=HEADERS, json=request).json()
        assert p['status'] == 'pending' and owner() == SOURCE
        assert c.post('/approvals/'+p['id'], headers=HEADERS, json={'decision':'approve'}).status_code == 403
        assert c.post('/approvals/'+p['id'], headers=REVIEW, json={'decision':'approve'}).status_code == 200
        assert c.post('/approvals/'+p['id'], headers=REVIEW, json={'decision':'approve'}).status_code == 409
    for name in LINK_TABLES:
        assert owner(name) == TARGET
    with engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(clients).where(clients.c.id.in_([SOURCE,TARGET]))) == 2
        assert c.scalar(select(client_merges.c.target_id).where(client_merges.c.source_id == SOURCE)) == TARGET
        assert c.scalar(select(clients.c.email).where(clients.c.id == TARGET)) == f'{TARGET}@example.invalid'
        assert c.scalar(select(clients.c.review_required).where(clients.c.id == TARGET)) is True
        assert c.scalar(select(followups.c.employment_id).where(followups.c.id == SOURCE)) == SOURCE
        events = [r['details'] for r in c.execute(select(audit).where(audit.c.event == 'clients_merged')).mappings()]
        assert any(r['proposal_id'] == p['id'] and r['moved_record_ids']['services'] == [SOURCE] for r in events)
    after = metrics()
    assert after['clients_served'] == before['clients_served']-1
    assert (after['new_jobs'],after['total_exits'],after['average_wage']) == (before['new_jobs'],before['total_exits'],before['average_wage'])
    assert not any(x['kind']=='duplicate' and x['record_id']==SOURCE for x in issues())
    assert SOURCE not in {p['id'] for p in duplicate_candidates(TARGET)['candidates']}


def test_reject_preserves_all_links_and_can_repropose(pair):
    p = make_merge()
    decide(p['id'], 'reject', 'tester')
    assert owner() == SOURCE
    assert make_merge()['id'] != p['id']


@pytest.mark.parametrize('change', ['source', 'target', 'link', 'new_link', 'deleted_link', 'followup'])
def test_stale_approval_is_atomic_and_audited_only_on_success(pair, change):
    p = make_merge()
    with engine.begin() as c:
        if change in ('source','target'):
            c.execute(update(clients).where(clients.c.id == (SOURCE if change=='source' else TARGET)).values(email='changed@example.invalid'))
        elif change=='link':
            c.execute(update(DATA_TABLES['services']).where(DATA_TABLES['services'].c.id==SOURCE).values(units=2))
        elif change=='new_link':
            c.execute(DATA_TABLES['services'].insert().values(id=THIRD,client_id=SOURCE,program_id=1,service_date='2026-08-01',units=1,review_required=False))
        elif change=='deleted_link':
            c.execute(delete(DATA_TABLES['services']).where(DATA_TABLES['services'].c.id==TARGET))
        else:
            c.execute(update(followups).where(followups.c.id==SOURCE).values(retained=True))
    with pytest.raises(Conflict):
        decide(p['id'], 'approve', 'tester')
    assert owner() == SOURCE
    with engine.connect() as c:
        assert c.scalar(select(proposals.c.status).where(proposals.c.id==p['id'])) == 'pending'
        assert not c.scalar(select(client_merges.c.source_id).where(client_merges.c.source_id==SOURCE))
        assert not any(r['details'].get('proposal_id')==p['id'] for r in c.execute(select(audit).where(audit.c.event=='clients_merged')).mappings())
    replacement = make_merge(replaces_id=p['id'])
    decide(replacement['id'], 'approve', 'tester')
    assert owner() == TARGET


def test_stale_preview_cannot_create_proposal(pair):
    preview = merge_preview(SOURCE,TARGET)
    with engine.begin() as c:
        c.execute(update(clients).where(clients.c.id==TARGET).values(email='edited@example.invalid'))
    with pytest.raises(Conflict,match='after preview'):
        propose_merge(SOURCE,TARGET,preview['preview_token'],EVIDENCE)


def test_pending_link_correction_blocks_merge_until_decided(pair):
    t=DATA_TABLES['services']
    with engine.begin() as c:
        c.execute(update(t).where(t.c.id==SOURCE).values(units=-1))
    p=propose(f'negative_units:{SOURCE}',resolution='correct_units',value='1',evidence=EVIDENCE)
    with pytest.raises(Conflict,match='pending correction'):
        merge_preview(SOURCE,TARGET)
    decide(p['id'],'reject','tester')
    assert merge_preview(SOURCE,TARGET)['snapshot']['source']['id']==SOURCE


def test_new_pending_correction_blocks_existing_merge_approval(pair):
    t=DATA_TABLES['services']
    with engine.begin() as c:c.execute(update(t).where(t.c.id==SOURCE).values(units=-1))
    p=make_merge()
    correction=propose(f'negative_units:{SOURCE}',resolution='correct_units',value='1',evidence=EVIDENCE)
    with pytest.raises(Conflict):decide(p['id'],'approve','tester')
    assert owner()==SOURCE
    decide(correction['id'],'reject','tester')
    decide(p['id'],'approve','tester')


def test_pending_profile_flag_preserved_in_history(pair):
    flag=propose(f'duplicate:{TARGET}',resolution='follow_up')
    p=make_merge()
    decide(p['id'],'approve','tester')
    with engine.connect() as c:
        assert c.scalar(select(proposals.c.status).where(proposals.c.id==flag['id']))=='superseded'
    with pytest.raises(Conflict):decide(flag['id'],'approve','tester')


def test_overlap_and_invalid_replacement_blocked(pair):
    p=make_merge()
    with pytest.raises(Conflict,match='overlapping'):merge_preview(TARGET,SOURCE)
    with pytest.raises(Conflict,match='overlapping'):merge_preview(SOURCE,THIRD)
    with pytest.raises(Conflict):merge_preview(SOURCE,THIRD,p['id'])
    replacement=make_merge(source=TARGET,target=SOURCE,replaces_id=p['id'])
    with pytest.raises(Conflict):decide(p['id'],'approve','tester')
    decide(replacement['id'],'approve','tester')
    assert owner(rid=TARGET)==SOURCE


def test_self_nonmatching_archived_and_chains_blocked(pair):
    with pytest.raises(ValueError):merge_preview(SOURCE,SOURCE)
    with pytest.raises(ValueError):merge_preview(SOURCE,1)
    p=make_merge();decide(p['id'],'approve','tester')
    with pytest.raises(Conflict):merge_preview(SOURCE,THIRD)
    with pytest.raises(Conflict,match='earlier merges'):merge_preview(TARGET,THIRD)
    assert merge_preview(THIRD,TARGET)['snapshot']['target']['id']==TARGET


def test_api_rejects_missing_evidence_untrusted_fields_and_bad_token(pair):
    preview=merge_preview(SOURCE,TARGET)
    body={'source_id':SOURCE,'target_id':TARGET,'preview_token':preview['preview_token'],'evidence':EVIDENCE}
    with TestClient(app) as c:
        for change in ({'evidence':''},{'delete_source':True},{'target_id':False},{'preview_token':'fake'}):
            assert c.post('/merges',headers=HEADERS,json={**body,**change}).status_code==422
        assert c.post('/merges',headers=HEADERS,json={**body,'preview_token':'0'*64}).status_code==409
        assert c.post('/merges',json=body).status_code==401


def test_agent_merge_tools_propose_only(pair):
    from agent.runner import dispatch,TOOLS
    ids={'source_id':str(SOURCE),'target_id':str(TARGET)}
    preview=dispatch('preview_merge',ids)
    p=dispatch('propose_merge',{**ids,'preview_token':preview['preview_token'],'evidence':EVIDENCE})
    assert p['status']=='pending' and owner()==SOURCE
    assert not any('approve' in t['function']['name'] for t in TOOLS)
    with pytest.raises(ValueError):dispatch('approve_merge',{'id':p['id']})


def test_live_model_loop_can_preview_and_propose_merge_without_applying(pair,monkeypatch):
    import json
    from agent import runner, llm
    monkeypatch.setenv('AGENT_MODE','live')
    monkeypatch.setenv('LLM_API_KEY','synthetic-test-key')
    monkeypatch.setenv('LLM_MODEL','mock-model')
    calls=[]
    class Response:
        def raise_for_status(self):pass
        def json(self):
            n=len(calls)
            if n==1:name,args='inspect_schema',{}
            elif n==2:name,args='preview_merge',{'source_id':str(SOURCE),'target_id':str(TARGET)}
            elif n==3:
                preview=json.loads(calls[-1]['messages'][-1]['content'])
                name,args='propose_merge',{'source_id':str(SOURCE),'target_id':str(TARGET),'preview_token':preview['preview_token'],'evidence':EVIDENCE}
            else:return {'choices':[{'message':{'content':'Merge proposal is pending reviewer approval.'}}]}
            return {'choices':[{'message':{'content':None,'tool_calls':[{'id':f'call-{n}','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}}]}
    def fake_post(url,**kwargs):
        calls.append(kwargs['json']);return Response()
    monkeypatch.setattr(llm.httpx,'post',fake_post)
    result=runner.run(f'Propose merging {SOURCE} into {TARGET}. {EVIDENCE}','2026-07-01','2026-09-30')
    assert [s['tool'] for s in result['trace']]==['inspect_schema','preview_merge','propose_merge']
    assert all(s['status']=='completed' for s in result['trace'])
    assert result['trace'][-1]['result']['status']=='pending' and owner()==SOURCE


@pytest.mark.skipif(not os.getenv('MC_TEST_APP_DATABASE_URL'),reason='PostgreSQL app-role merge test')
def test_postgres_merge_grants_and_identity_protection(pair,monkeypatch):
    from backend import logic,merges
    from sqlalchemy.exc import DBAPIError
    e=engine_for(os.environ['MC_TEST_APP_DATABASE_URL'])
    monkeypatch.setattr(logic,'engine',e);monkeypatch.setattr(merges,'engine',e)
    try:
        p=make_merge();decide(p['id'],'approve','tester')
        for name in LINK_TABLES:assert owner(name)==TARGET
        for stmt in (update(clients).where(clients.c.id==TARGET).values(email='forbidden@example.invalid'),delete(clients).where(clients.c.id==SOURCE)):
            with pytest.raises(DBAPIError):
                with e.begin() as c:c.execute(stmt)
    finally:e.dispose()


@pytest.mark.skipif(engine.dialect.name!='postgresql',reason='PostgreSQL concurrent reviewer test')
def test_concurrent_reviewers_apply_merge_once(pair):
    p=make_merge()
    def attempt(actor):
        try:return decide(p['id'],'approve',actor)['status']
        except Conflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,['reviewer-a','reviewer-b']))==['applied','conflict']
    with engine.connect() as c:
        events=[r for r in c.execute(select(audit).where(audit.c.event=='clients_merged')).mappings() if r['details']['proposal_id']==p['id']]
        assert len(events)==1
