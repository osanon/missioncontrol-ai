from datetime import date, timedelta
import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update, delete, text
from backend.db import engine, enrollments, proposals, audit, engine_for
from backend.logic import propose, decide, Conflict, now, list_proposals, issues
from backend.main import app
HEADERS={'Authorization':'Bearer test-analyst-token-000000000000000000'}
REVIEW={**HEADERS,'X-Review-Token':'test-review-token-0000000000000000000'}

@pytest.fixture
def enrollment():
    with engine.begin() as c:
        c.execute(enrollments.insert().values(id=8001,client_id=1,program_id=1,start_date='2026-01-01',end_date=None,status='exited',review_required=False))
    yield 'missing_exit:8001'
    with engine.begin() as c:
        c.execute(delete(proposals).where(proposals.c.table_name=='enrollments',proposals.c.record_id==8001))
        c.execute(delete(enrollments).where(enrollments.c.id==8001))

def row():
    with engine.connect() as c:
        return dict(c.execute(select(enrollments).where(enrollments.c.id==8001)).mappings().one())

def correction(key, **extra):
    return propose(key,resolution='set_exit_date',value='2026-09-20',evidence='Program confirmed discharge on September 20.',**extra)

def legacy(key, status='pending'):
    p=dict(id=str(uuid.uuid4()),issue_key=key,table_name='enrollments',record_id=8001,
           before={'review_required':False},after={'review_required':True},reason='An exited enrollment has no exit date.',
           status=status,created_at=now(),decided_at=now() if status!='pending' else None,decided_by='old-reviewer' if status!='pending' else None)
    with engine.begin() as c:c.execute(proposals.insert().values(**p))
    return p

def test_exit_correction_is_pending_until_authorized_and_audited(enrollment):
    with TestClient(app) as client:
        p=client.post('/proposals',headers=HEADERS,json={'issue_key':enrollment,'resolution':'set_exit_date','value':'2026-09-20','evidence':'Program verified discharge on September 20.'}).json()
        assert p['before']['end_date'] is None and p['after']['end_date']=='2026-09-20'
        assert row()['end_date'] is None
        assert client.post('/approvals/'+p['id'],headers=HEADERS,json={'decision':'approve'}).status_code==403
        assert client.post('/approvals/'+p['id'],headers=REVIEW,json={'decision':'approve'}).status_code==200
        assert row()['end_date']=='2026-09-20'
        with engine.connect() as c:
            events=list(c.execute(select(audit).where(audit.c.event=='proposal_applied')).mappings())
        assert any(e['details']['proposal_id']==p['id'] for e in events)
        assert client.post('/approvals/'+p['id'],headers=REVIEW,json={'decision':'approve'}).status_code==409

def test_reactivate_only_specific_enrollment(enrollment):
    p=propose(enrollment,resolution='reactivate_enrollment',evidence='Program staff confirmed enrollment remains active.')
    assert row()['status']=='exited'
    decide(p['id'],'approve','tester')
    assert row()['status']=='active' and row()['end_date'] is None
    assert not any(x['key']==enrollment for x in issues())

def test_reject_does_not_mutate_source_and_can_create_new_proposal(enrollment):
    p=correction(enrollment)
    decide(p['id'],'reject','tester')
    assert row()['end_date'] is None
    new=correction(enrollment)
    assert new['id']!=p['id']
    with engine.connect() as c:
        old=c.execute(select(proposals).where(proposals.c.id==p['id'])).mappings().one()
    assert old['status']=='rejected' and old['decided_by']=='tester'

def test_legacy_flag_can_be_replaced_without_deleting_history(enrollment):
    old=legacy(enrollment)
    view=next(p for p in list_proposals() if p['id']==old['id'])
    assert not view['snapshot_complete'] and view['current_record']['end_date'] is None
    assert view['context']['client_name'] and view['context']['program']
    new=correction(enrollment,replaces_id=old['id'])
    assert row()['end_date'] is None and not row()['review_required']
    with engine.connect() as c:
        old_saved=c.execute(select(proposals).where(proposals.c.id==old['id'])).mappings().one()
        events=list(c.execute(select(audit).where(audit.c.event=='proposal_superseded')).mappings())
    assert old_saved['status']=='superseded' and old_saved['before']=={'review_required':False}
    assert any(e['details']['replacement_id']==new['id'] for e in events)
    with pytest.raises(Conflict):decide(old['id'],'approve','tester')
    decide(new['id'],'approve','tester')
    assert row()['end_date']=='2026-09-20'

def test_already_applied_flag_still_allows_correction(enrollment):
    old=legacy(enrollment,'applied')
    with engine.begin() as c:c.execute(update(enrollments).where(enrollments.c.id==8001).values(review_required=True))
    p=correction(enrollment)
    decide(p['id'],'approve','tester')
    assert row()['review_required'] is True  # Do not silently clear a flag that could concern another issue.
    with engine.connect() as c:assert c.scalar(select(proposals.c.status).where(proposals.c.id==old['id']))=='applied'

def test_stale_status_blocks_approval_and_rolls_back_audit(enrollment):
    p=correction(enrollment)
    with engine.begin() as c:c.execute(update(enrollments).where(enrollments.c.id==8001).values(status='active'))
    with pytest.raises(Conflict):decide(p['id'],'approve','tester')
    with engine.connect() as c:
        assert c.scalar(select(proposals.c.status).where(proposals.c.id==p['id']))=='pending'
        assert not any(e['details'].get('proposal_id')==p['id'] for e in c.execute(select(audit).where(audit.c.event=='proposal_applied')).mappings())
    assert row()['end_date'] is None

def test_missing_exit_cannot_infer_date_without_confirmation(enrollment):
    with pytest.raises(ValueError,match='confirmation'):propose(enrollment,resolution='set_exit_date',value='2026-09-20')
    with pytest.raises(ValueError,match='confirmation'):propose(enrollment,resolution='reactivate_enrollment')

@pytest.mark.parametrize('value',['2025-12-31','2026-02-30','20260920',(date.today()+timedelta(days=1)).isoformat()])
def test_invalid_dates_rejected(enrollment,value):
    with pytest.raises(ValueError):propose(enrollment,resolution='set_exit_date',value=value,evidence='Confirmed date from program record.')

def test_followup_is_explicit_and_keeps_missing_exit(enrollment):
    p=propose(enrollment,resolution='follow_up')
    assert p['before']['status']=='exited' and p['before']['end_date'] is None
    assert p['after']=={'review_required':True}
    assert propose(enrollment,resolution='follow_up')['id']==p['id']
    decide(p['id'],'approve','tester')
    assert row()['end_date'] is None and row()['review_required']
    with pytest.raises(ValueError,match='already flagged'):propose(enrollment,resolution='follow_up')

def test_cannot_replace_without_exact_pending_id(enrollment):
    old=legacy(enrollment)
    with pytest.raises(Conflict):correction(enrollment)
    with pytest.raises(Conflict):correction(enrollment,replaces_id='wrong-id')
    with engine.connect() as c:assert c.scalar(select(proposals.c.status).where(proposals.c.id==old['id']))=='pending'

def test_api_disallows_arbitrary_fields_and_resolution(enrollment):
    with TestClient(app) as c:
        assert c.post('/proposals',headers=HEADERS,json={'issue_key':enrollment,'after':{'status':'active'}}).status_code==422
        assert c.post('/proposals',headers=HEADERS,json={'issue_key':enrollment,'resolution':'delete'}).status_code==422
        assert c.post('/proposals',headers=HEADERS,json={'issue_key':enrollment,'resolution':'correct_wage','value':'20','evidence':'Confirmed by program staff.'}).status_code==400

@pytest.mark.parametrize('resolution,value',[('correct_wage','nan'),('correct_wage','inf'),('correct_wage','0'),('correct_units','-1')])
def test_numeric_validation(resolution,value):
    from backend.logic import correction_patch
    issue={'kind':'wage_outlier' if resolution=='correct_wage' else 'negative_units','record':{'review_required':False}}
    with pytest.raises(ValueError):correction_patch(issue,resolution,value,'Verified source document.')

def test_agent_can_propose_but_has_no_approval_tool(enrollment):
    from agent.runner import dispatch,TOOLS
    p=dispatch('propose_correction',{'issue_key':enrollment,'resolution':'set_exit_date','value':'2026-09-20','evidence':'User explicitly confirmed the discharge date.'})
    assert p['status']=='pending' and row()['end_date'] is None
    with pytest.raises(ValueError):dispatch('approve',{'id':p['id']})
    assert not any('approve' in t['function']['name'] for t in TOOLS)

@pytest.mark.skipif(not os.getenv('MC_TEST_APP_DATABASE_URL'),reason='PostgreSQL app-role test')
def test_postgres_app_role_can_apply_correction_but_not_change_client_identifier(enrollment,monkeypatch):
    from backend import logic
    from sqlalchemy.exc import DBAPIError
    app_engine=engine_for(os.environ['MC_TEST_APP_DATABASE_URL'])
    monkeypatch.setattr(logic,'engine',app_engine)
    try:
        old=legacy(enrollment)
        p=correction(enrollment,replaces_id=old['id'])
        decide(p['id'],'approve','tester')
        assert row()['end_date']=='2026-09-20'
        with pytest.raises(DBAPIError):
            with app_engine.begin() as c:c.execute(text("UPDATE clients SET external_id='forbidden' WHERE id=1"))
    finally:app_engine.dispose()

@pytest.mark.parametrize('table_name,kind,resolution,field,old_value,new_value',[
    ('employment','wage_outlier','correct_wage','hourly_wage',1500,22.5),
    ('services','negative_units','correct_units','units',-2,2.5),
])
def test_confirmed_numeric_correction_changes_only_target(table_name,kind,resolution,field,old_value,new_value):
    from backend.db import DATA_TABLES
    t=DATA_TABLES[table_name]
    record=dict(id=900001,client_id=1,review_required=False)
    if table_name=='employment':record.update(start_date='2026-01-01',hourly_wage=old_value)
    else:record.update(program_id=1,service_date='2026-01-01',units=old_value)
    with engine.begin() as c:c.execute(t.insert().values(**record))
    try:
        p=propose(f'{kind}:900001',resolution=resolution,value=str(new_value),evidence='Program verified against the original source record.')
        with engine.connect() as c:assert c.scalar(select(t.c[field]).where(t.c.id==900001))==old_value
        decide(p['id'],'approve','tester')
        with engine.connect() as c:
            saved=c.execute(select(t).where(t.c.id==900001)).mappings().one()
        assert saved[field]==new_value and saved['client_id']==1 and not saved['review_required']
    finally:
        with engine.begin() as c:
            c.execute(delete(proposals).where(proposals.c.table_name==table_name,proposals.c.record_id==900001))
            c.execute(delete(t).where(t.c.id==900001))
