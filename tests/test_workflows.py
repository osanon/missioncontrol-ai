from collections import Counter
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,update,text
from backend.main import app
from backend.db import engine,employment,proposals,audit,reader
from backend.logic import metrics,issues,cohorts,propose,decide,Conflict
from agent.sql_guard import safe_query,validate_sql

HEADERS={'Authorization':'Bearer test-analyst-token-000000000000000000'}
REVIEW={**HEADERS,'X-Review-Token':'test-review-token-0000000000000000000'}


def test_seed_and_known_anomalies():
    assert Counter(x['kind'] for x in issues())=={'duplicate':12,'invalid_dates':10,'missing_exit':10,'wage_outlier':8,'negative_units':6}
    m=metrics()
    assert (m['clients_served'],m['new_jobs'],m['stable_exits'],m['total_exits'])==(581,321,104,184)
    assert m['average_wage']==18.58
    assert cohorts()['rows']==[{'cohort':'Employment + housing','clients':290,'obtained_employment':188,'rate':64.8},{'cohort':'Employment only','clients':291,'obtained_employment':111,'rate':38.1}]

@pytest.mark.parametrize('sql',[
 'DELETE FROM clients', 'UPDATE clients SET full_name=\'x\'','SELECT * FROM clients; DROP TABLE clients',
 'SELECT pg_sleep(10)','SELECT * FROM pg_catalog.pg_user','SELECT * FROM audit_records',
 'WITH changed AS (DELETE FROM clients RETURNING *) SELECT * FROM changed',
 'SELECT * INTO stolen FROM clients', 'SELECT * FROM clients FOR UPDATE',
 "SELECT pg_read_file('/etc/passwd')",'SELECT * FROM generate_series(1,10000000)',
 "COPY clients TO '/tmp/leak'",'SELECT 1; SELECT 2',
 "SELECT set_config('statement_timeout','0',false)",
 'WITH clients AS (SELECT 1) SELECT * FROM clients',
 'SELECT id FROM clients WHERE id = 1 AND pg_sleep(1) IS NULL'
])
def test_unsafe_sql_rejected(sql):
    with pytest.raises(ValueError):validate_sql(sql)

@pytest.mark.parametrize('sql',[
 'SELECT id FROM clients WHERE id < 5 AND review_required = false',
 'SELECT id FROM clients WHERE id = 1 OR id = 2',
 'SELECT c.id FROM clients c JOIN enrollments e ON e.client_id = c.id AND e.program_id = 1',
 'SELECT c.id FROM clients c WHERE EXISTS (SELECT 1 FROM enrollments e WHERE e.client_id = c.id)'
])
def test_conditions_with_and_or_exists_allowed(sql):
    assert safe_query(sql)['rows']

@pytest.mark.parametrize('sql',[
 "SELECT to_char(exit_date,'YYYY-MM') AS month, count(*) FROM enrollments GROUP BY 1",
 "SELECT date_trunc('month',exit_date) AS month, count(*) FROM enrollments GROUP BY 1",
 'SELECT extract(year FROM exit_date) AS year FROM enrollments',
 "SELECT count(*) FROM enrollments WHERE exit_date >= DATE '2026-07-01' - INTERVAL '90 days'"
])
def test_date_functions_allowed(sql):
    assert validate_sql(sql)

def test_safe_select_and_row_cap():
    out=safe_query('SELECT id FROM clients ORDER BY id')
    assert len(out['rows'])==200 and out['truncated']
    assert list(safe_query('SELECT COUNT(*) AS total FROM clients')['rows'][0].values())==[2000]
    assert safe_query('WITH cohort AS (SELECT id FROM clients WHERE id < 5) SELECT COUNT(*) AS total FROM cohort')['rows'][0]['total']==4

def test_auth_and_validation():
    with TestClient(app) as c:
        assert c.get('/metrics').status_code==401
        assert c.get('/metrics?start=2026-09-30&end=2026-07-01',headers=HEADERS).status_code==400
        assert c.get('/health-check').json()['status']=='ok'
        assert c.get('/schema',headers=HEADERS).status_code==200
        assert c.post('/proposals',headers=HEADERS,json={'issue_key':'nonexistent:1'}).status_code==400

def test_approval_is_required_atomic_and_once():
    with TestClient(app) as c:
        p=c.post('/proposals',headers=HEADERS,json={'issue_key':'wage_outlier:1'}).json()
        with engine.connect() as db: assert db.scalar(select(employment.c.hourly_wage).where(employment.c.id==1))==1500
        assert c.post(f"/approvals/{p['id']}",headers=HEADERS,json={'decision':'approve'}).status_code==403
        assert c.post(f"/approvals/{p['id']}",headers=REVIEW,json={'decision':'approve'}).json()['status']=='applied'
        assert c.post(f"/approvals/{p['id']}",headers=REVIEW,json={'decision':'approve'}).status_code==409
        with engine.connect() as db:
            assert db.scalar(select(employment.c.hourly_wage).where(employment.c.id==1)) is None
            assert any(row.details.get('proposal_id')==p['id'] for row in db.execute(select(audit).where(audit.c.event=='proposal_applied')).mappings())

def test_reject_preserves_source_and_idempotent_proposal():
    p=propose('wage_outlier:2')
    assert propose('wage_outlier:2')['id']==p['id']
    decide(p['id'],'reject','reviewer-test')
    with engine.connect() as c:assert c.scalar(select(employment.c.hourly_wage).where(employment.c.id==2))==-15

def test_stale_proposal_rolls_back_decision():
    p=propose('wage_outlier:3')
    with engine.begin() as c:c.execute(update(employment).where(employment.c.id==3).values(hourly_wage=22))
    with pytest.raises(Conflict):decide(p['id'],'approve','reviewer-test')
    with engine.connect() as c:
        assert c.scalar(select(proposals.c.status).where(proposals.c.id==p['id']))=='pending'
        assert c.scalar(select(employment.c.hourly_wage).where(employment.c.id==3))==22

def test_investigation_report_and_followup():
    with TestClient(app) as c:
        first=c.post('/ask',headers=HEADERS,json={'question':'How did we perform this quarter?'}).json()
        assert first['mode']=='demo'
        assert first['trace'][1]['tool']=='compare_periods'
        assert first['trace'][1]['result']['previous']['period']['start']=='2026-04-01'
        assert '581' in first['answer']
        assert 'Evidence' in c.get('/reports/'+first['id'],headers=HEADERS).text
        second=c.post('/ask',headers=HEADERS,json={'question':'Compare employment only and combined housing','previous_run_id':first['id']}).json()
        assert second['trace'][1]['tool']=='compare_cohorts'
        assert c.post('/ask',headers=HEADERS,json={'question':'Check data quality'}).status_code==200
        unknown=c.post('/ask',headers=HEADERS,json={'question':'Hello there'}).json()
        assert 'Demo mode supports' in unknown['answer']

@pytest.mark.skipif(reader.dialect.name!='postgresql',reason='PostgreSQL role test')
def test_postgres_reader_cannot_write():
    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError):
        with reader.begin() as c:c.execute(text("UPDATE clients SET full_name='changed' WHERE id=1"))
