import uuid
from decimal import Decimal
from datetime import date, datetime, timezone
from sqlalchemy import text, select, update
from sqlalchemy.exc import IntegrityError
from backend.db import engine, reader, DATA_TABLES, proposals, audit

def now(): return datetime.now(timezone.utc).isoformat()
def log(c, event, details, actor='system'):
    c.execute(audit.insert().values(id=str(uuid.uuid4()),occurred_at=now(),actor=actor,event=event,details=details))

def query(sql, params=None):
    with reader.connect() as c:
        return [{k:float(v) if isinstance(v,Decimal) else v for k,v in x.items()} for x in c.execute(text(sql), params or {}).mappings()]

def period(start,end):
    a,b=date.fromisoformat(start),date.fromisoformat(end)
    if a>b: raise ValueError('Start date must be on or before end date.')
    if (b-a).days>1095: raise ValueError('Choose a period of at most three years.')
    return {'start':start,'end':end}

METRIC_SQL={
 'clients_served': 'SELECT COUNT(DISTINCT client_id) AS value FROM services WHERE service_date BETWEEN :start AND :end AND units > 0',
 'new_jobs': 'SELECT COUNT(*) AS value FROM employment WHERE start_date BETWEEN :start AND :end',
 'average_wage': 'SELECT ROUND(CAST(AVG(hourly_wage) AS NUMERIC),2) AS value FROM employment WHERE start_date BETWEEN :start AND :end AND hourly_wage BETWEEN 1 AND 200',
 'stable_exits': "SELECT COUNT(*) AS exits, SUM(CASE WHEN destination='stable' THEN 1 ELSE 0 END) AS stable FROM housing WHERE exit_date BETWEEN :start AND :end AND exit_date >= entry_date",
 'programs': 'SELECT p.name, COUNT(DISTINCT s.client_id) AS clients, COUNT(*) AS contacts FROM services s JOIN programs p ON p.id=s.program_id WHERE s.service_date BETWEEN :start AND :end AND s.units>0 GROUP BY p.name ORDER BY clients DESC'
}

def metrics(start='2026-07-01',end='2026-09-30'):
    p=period(start,end)
    result={k:query(sql,p) for k,sql in METRIC_SQL.items()}
    exits=result['stable_exits'][0]
    return {'period':p,'clients_served':result['clients_served'][0]['value'],'new_jobs':result['new_jobs'][0]['value'],'average_wage':result['average_wage'][0]['value'], 'stable_exits':exits['stable'] or 0,'total_exits':exits['exits'], 'stable_exit_rate': round(100*(exits['stable'] or 0)/exits['exits'],1) if exits['exits'] else None,'programs':result['programs'], 'definitions': {'clients_served':'Distinct clients with a positive-unit service in the selected period. Program counts overlap.', 'new_jobs':'Employment records starting during the selected period; multiple jobs per person count separately.', 'average_wage':'Mean hourly wage across jobs starting during the period, excluding null values and values outside $1–$200. This is a demo plausibility rule, not a wage standard.', 'stable_exit_rate':'Stable housing exits divided by all chronologically valid housing exits during the period. Unknown destinations stay in the denominator.'}, 'sources':METRIC_SQL}

COHORT_SQL="""WITH cohorts AS (
 SELECT s.client_id, MAX(CASE WHEN s.program_id=2 THEN 1 ELSE 0 END) AS housing_support
 FROM services s WHERE s.service_date BETWEEN :start AND :end AND s.units>0
 GROUP BY s.client_id
 HAVING MAX(CASE WHEN s.program_id=1 THEN 1 ELSE 0 END)=1
), outcomes AS (
 SELECT DISTINCT client_id FROM employment WHERE start_date BETWEEN :start AND :end
) SELECT CASE WHEN c.housing_support=1 THEN 'Employment + housing' ELSE 'Employment only' END AS cohort,
 COUNT(*) AS clients, COUNT(o.client_id) AS obtained_employment
 FROM cohorts c LEFT JOIN outcomes o ON o.client_id=c.client_id GROUP BY c.housing_support ORDER BY c.housing_support DESC"""

def cohorts(start='2026-07-01',end='2026-09-30'):
    rows=query(COHORT_SQL,period(start,end))
    for row in rows: row['rate']=round(100*row['obtained_employment']/row['clients'],1) if row['clients'] else None
    return {'rows':rows,'sql':COHORT_SQL,'period':period(start,end),'definition':'Positive employment services in the period; housing cohort also has positive housing services in the same period. Outcome: at least one job starting in the period. Counts distinct clients. Association does not establish causation or service-before-job timing.'}

CHECKS=[
 ('duplicate','clients',"SELECT b.id FROM clients a JOIN clients b ON a.full_name=b.full_name AND a.birth_date=b.birth_date AND a.id<b.id",'Possible duplicate identity','Names and birth dates match another record. Review source documents; no automatic merge.','medium'),
 ('invalid_dates','enrollments','SELECT id FROM enrollments WHERE end_date < start_date','Exit precedes entry','Verify the dates against source records.','high'),
 ('missing_exit','enrollments',"SELECT id FROM enrollments WHERE status='exited' AND end_date IS NULL",'Missing exit date','An exited enrollment has no exit date. Confirm with the program.','medium'),
 ('wage_outlier','employment','SELECT id FROM employment WHERE hourly_wage < 1 OR hourly_wage > 200','Implausible hourly wage','Outside the demo $1–$200 plausibility range. A reviewer can clear the unverified wage and flag it.','high'),
 ('negative_units','services','SELECT id FROM services WHERE units < 0','Negative service units','Verify the service record before replacing its value.','medium')
]

def issues():
    out=[]
    with engine.connect() as c:
        statuses={x.issue_key:x.status for x in c.execute(select(proposals)).mappings()}
    for kind,table,sql,title,reason,severity in CHECKS:
        for x in query(sql):
            key=f'{kind}:{x["id"]}'
            record=query(f'SELECT * FROM {table} WHERE id=:id',{'id':x['id']})[0]
            out.append(dict(key=key,kind=kind,table=table,record_id=x['id'],title=title,reason=reason,severity=severity,record=record,review_required=bool(record['review_required']),proposal_status=statuses.get(key),source_sql=sql))
    return out

class Conflict(ValueError): pass

def propose(issue_key, actor='analyst'):
    # The model supplies only an issue key. Targets and patch are created by trusted code.
    with engine.connect() as c:
        existing=c.execute(select(proposals).where(proposals.c.issue_key==issue_key)).mappings().first()
        if existing:return dict(existing)
    issue=next((x for x in issues() if x['key']==issue_key),None)
    if not issue:raise ValueError('Issue does not exist or no longer applies.')
    before={'review_required':bool(issue['record']['review_required'])}
    after={'review_required':True}
    if issue['kind']=='wage_outlier':
        before['hourly_wage']=issue['record']['hourly_wage'];after['hourly_wage']=None
    item=dict(id=str(uuid.uuid4()),issue_key=issue_key,table_name=issue['table'],record_id=issue['record_id'],before=before,after=after,reason=issue['reason'],status='pending',created_at=now(),decided_at=None,decided_by=None)
    try:
        with engine.begin() as c:
            c.execute(proposals.insert().values(**item));log(c,'proposal_created',item,actor)
    except IntegrityError:
        with engine.connect() as c: return dict(c.execute(select(proposals).where(proposals.c.issue_key==issue_key)).mappings().one())
    return item

def decide(proposal_id,decision,actor):
    if decision not in ('approve','reject'):raise ValueError('Invalid decision.')
    with engine.begin() as c:
        item=c.execute(select(proposals).where(proposals.c.id==proposal_id).with_for_update()).mappings().first()
        if not item:raise ValueError('Proposal not found.')
        if item['status']!='pending':raise Conflict('This proposal has already been decided.')
        status='applied' if decision=='approve' else 'rejected'
        # Compare-and-swap also protects the SQLite test fallback.
        claim=c.execute(update(proposals).where(proposals.c.id==proposal_id,proposals.c.status=='pending').values(status=status,decided_at=now(),decided_by=actor))
        if claim.rowcount!=1:raise Conflict('Another reviewer already decided this proposal.')
        if decision=='approve':
            t=DATA_TABLES[item['table_name']]
            stmt=update(t).where(t.c.id==item['record_id'])
            for key,val in item['before'].items():stmt=stmt.where(t.c[key]==val)
            changed=c.execute(stmt.values(**item['after']))
            if changed.rowcount!=1:raise Conflict('Record changed after this proposal was created. No changes applied.')
        log(c,'proposal_'+status,{'proposal_id':proposal_id,'table':item['table_name'],'record_id':item['record_id'],'before':item['before'],'after':item['after'] if decision=='approve' else item['before']},actor)
    return {'id':proposal_id,'status':status}
