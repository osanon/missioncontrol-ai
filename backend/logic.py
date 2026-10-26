import uuid
import math
from decimal import Decimal
from datetime import date, datetime, timezone
from sqlalchemy import text, select, update
from sqlalchemy.exc import IntegrityError
from backend.mutations import serialize_writes
from backend.db import engine, reader, DATA_TABLES, proposals, audit, ai_reviews

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
 ('duplicate','clients',"SELECT DISTINCT b.id FROM clients a JOIN clients b ON a.full_name=b.full_name AND a.birth_date=b.birth_date AND a.id<b.id WHERE NOT EXISTS (SELECT 1 FROM client_merges m WHERE m.source_id=a.id OR m.source_id=b.id)",'Possible duplicate identity','Names and birth dates match another record. Compare both profiles and confirm identity before proposing a merge.','medium'),
 ('invalid_dates','enrollments','SELECT id FROM enrollments WHERE end_date < start_date','Exit precedes entry','Verify the dates against source records.','high'),
 ('missing_exit','enrollments',"SELECT id FROM enrollments WHERE status='exited' AND end_date IS NULL",'Missing exit date','An exited enrollment has no exit date. Confirm with the program.','medium'),
 ('wage_outlier','employment','SELECT id FROM employment WHERE hourly_wage < 1 OR hourly_wage > 200','Implausible hourly wage','Outside the demo $1–$200 plausibility range. A reviewer can clear the unverified wage and flag it.','high'),
 ('negative_units','services','SELECT id FROM services WHERE units < 0','Negative service units','Verify the service record before replacing its value.','medium')
]

def fetch_records(c, table, ids):
    """{id: record} for many rows of one table in a single query."""
    t=DATA_TABLES[table]
    ids=list(ids)
    return {r['id']:dict(r) for r in c.execute(select(t).where(t.c.id.in_(ids))).mappings()} if ids else {}

def contexts(c, items):
    """Client and program names for many (table, record) pairs with two queries in total."""
    client_ids={(r.get('id') if table=='clients' else r.get('client_id')) for table,r in items}-{None}
    program_ids={r.get('program_id') for _,r in items}-{None}
    people=fetch_records(c,'clients',client_ids)
    names={k:v['name'] for k,v in fetch_records(c,'programs',program_ids).items()}
    out=[]
    for table,r in items:
        client_id=r.get('id') if table=='clients' else r.get('client_id')
        person=people.get(client_id)
        out.append({'client_id':client_id,'client_name':person['full_name'] if person else None,
                    'client_identifier':person['external_id'] if person else None,'program':names.get(r.get('program_id'))})
    return out

def issues(kinds=None):
    """Current findings. Batched: one query per check, one per table for the records, two for names."""
    with engine.connect() as c:
        statuses={x.issue_key:x.status for x in c.execute(select(proposals.c.issue_key,proposals.c.status).order_by(proposals.c.created_at,proposals.c.id)) if '@' not in x.issue_key}
    found=[]
    with reader.connect() as c:
        for kind,table,sql,title,reason,severity in CHECKS:
            if kinds and kind not in kinds:continue
            ids=[x['id'] for x in c.execute(text(sql)).mappings()]
            records=fetch_records(c,table,ids)
            found+=[(kind,table,sql,title,reason,severity,records[i]) for i in ids if i in records]
        names=contexts(c,[(f[1],f[6]) for f in found])
    return [dict(key=f'{kind}:{record["id"]}',kind=kind,table=table,record_id=record['id'],title=title,reason=reason,severity=severity,record=record,
                 review_required=bool(record['review_required']),proposal_status=statuses.get(f'{kind}:{record["id"]}'),source_sql=sql,context=context)
            for (kind,table,sql,title,reason,severity,record),context in zip(found,names)]

def find_issue(issue_key):
    """Look up one finding by key, running only that finding's check."""
    kind=issue_key.split(':',1)[0]
    return next((x for x in issues({kind}) if x['key']==issue_key),None) if any(kind==k[0] for k in CHECKS) else None

class Conflict(ValueError): pass

# A human reviewer can send a proposal back; the agent (or analyst) then submits a replacement.
REPLACEABLE = ('pending', 'reevaluation_requested')
DECISION_STATUS = {'approve': 'applied', 'reject': 'rejected', 'reevaluate': 'reevaluation_requested'}


def check_decision(found, decision, actor, note):
    if decision not in DECISION_STATUS:
        raise ValueError('Invalid decision.')
    if decision == 'reevaluate' and len(note.strip()) < 10:
        raise ValueError('Explain what should be reevaluated (at least 10 characters).')
    if found.get('created_by') and found['created_by'] == actor:
        raise Conflict('Proposals must be decided by someone other than their author.')


def provenance(actor, actor_kind, run_id, model):
    if actor_kind not in ('human', 'agent'):
        raise ValueError('Unknown proposal author type.')
    return {'created_by': actor, 'created_by_kind': actor_kind, 'run_id': run_id, 'model': model}


def latest_reviews(c, proposal_ids=None):
    """Latest AI review per proposal, in one query."""
    stmt = select(ai_reviews).order_by(ai_reviews.c.created_at, ai_reviews.c.id)
    if proposal_ids is not None:
        stmt = stmt.where(ai_reviews.c.proposal_id.in_(list(proposal_ids)))
    return {r['proposal_id']: dict(r) for r in c.execute(stmt).mappings()}


def proposal_views(c, items, reviews):
    """Build review views for many proposals: current records batched per table, names batched once."""
    by_table = {}
    for item in items:
        by_table.setdefault(item['table_name'], set()).add(item['record_id'])
    current = {table: fetch_records(c, table, ids) for table, ids in by_table.items()}
    records = [current[item['table_name']].get(item['record_id'], {}) for item in items]
    names = contexts(c, [(item['table_name'], record) for item, record in zip(items, records)])
    return [proposal_view(item, reviews.get(item['id']), record, context) for item, record, context in zip(items, records, names)]


def proposal_view(item, review, record, context):
    result = dict(item)
    result['ai_review'] = review
    result['current_record'] = record
    result['context'] = context
    result['snapshot_complete'] = 'id' in result['before']
    result['proposal_type'] = 'merge' if result['after'].get('action') == 'merge_clients' else 'follow_up' if set(result['after']) == {'review_required'} else 'correction'
    result['base_issue_key'] = result['issue_key'].split('@', 1)[0]
    return result


def list_proposals():
    with engine.connect() as c:
        rows = [dict(r) for r in c.execute(select(proposals).order_by(proposals.c.created_at.desc())).mappings()]
        return proposal_views(c, rows, latest_reviews(c))


def get_proposal_view(proposal_id):
    with engine.connect() as c:
        row = c.execute(select(proposals).where(proposals.c.id == proposal_id)).mappings().first()
        if not row:
            raise ValueError('Proposal not found.')
        return proposal_views(c, [dict(row)], latest_reviews(c, [proposal_id]))[0]


def correction_patch(issue, resolution, value, evidence):
    record = issue['record']
    allowed = {
        'missing_exit': {'follow_up', 'set_exit_date', 'reactivate_enrollment'},
        'invalid_dates': {'follow_up', 'set_exit_date'},
        'wage_outlier': {'follow_up', 'correct_wage', 'clear_wage'},
        'negative_units': {'follow_up', 'correct_units'},
        'duplicate': {'follow_up'},
    }
    if resolution not in allowed.get(issue['kind'], set()):
        raise ValueError('This resolution is not available for this finding.')
    if resolution not in ('follow_up', 'clear_wage') and len(evidence.strip()) < 10:
        raise ValueError('Describe the source or confirmation supporting this correction (at least 10 characters).')
    if resolution in ('follow_up', 'reactivate_enrollment', 'clear_wage') and value:
        raise ValueError('This resolution does not accept a value.')
    if resolution == 'follow_up':
        if record['review_required']:
            raise ValueError('This record is already flagged for follow-up. Choose a confirmed correction when available.')
        return {'review_required': True}, 'Flag for follow-up; the underlying data issue remains unresolved.'
    if resolution == 'reactivate_enrollment':
        return {'status': 'active', 'end_date': None}, 'Reactivate this program enrollment after confirmation.'
    if resolution == 'set_exit_date':
        try:
            exit_date = date.fromisoformat(value)
            start_date = date.fromisoformat(record['start_date'])
        except (ValueError, TypeError):
            raise ValueError('Enter a valid exit date; the enrollment start date must also be valid.')
        if exit_date.isoformat() != value:
            raise ValueError('Use YYYY-MM-DD for the exit date.')
        if exit_date < start_date:
            raise ValueError('The exit date cannot be before the enrollment start date.')
        if exit_date > datetime.now(timezone.utc).date():
            raise ValueError('A confirmed exit date cannot be in the future.')
        return {'end_date': value, 'status': 'exited'}, 'Record the confirmed exit date for this enrollment.'
    if resolution == 'clear_wage':
        return {'hourly_wage': None, 'review_required': True}, 'Clear the unverified wage and flag for follow-up. This does not establish the correct wage.'
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError('Enter a valid number.')
    if not math.isfinite(number):
        raise ValueError('Enter a finite number.')
    if resolution == 'correct_wage':
        if not 1 <= number <= 200:
            raise ValueError('The confirmed wage must be within the demo plausibility range of $1 to $200. Otherwise use follow-up.')
        return {'hourly_wage': number}, 'Record the confirmed hourly wage.'
    if number < 0:
        raise ValueError('Service units cannot be negative.')
    return {'units': number}, 'Record the confirmed service units.'


def propose(issue_key, actor='analyst', resolution=None, value='', evidence='', replaces_id=None,
            actor_kind='human', run_id=None, model=None):
    if '@' in issue_key:
        raise ValueError('Use the original finding key, not a historical proposal key.')
    issue = find_issue(issue_key)
    if not issue:
        raise ValueError('Issue does not exist or no longer applies. Refresh Data Health.')
    resolution = resolution or ('clear_wage' if issue['kind'] == 'wage_outlier' else 'follow_up')
    after, explanation = correction_patch(issue, resolution, value, evidence)
    before = dict(issue['record'])
    reason = issue['reason'] + '\nAction: ' + explanation
    if evidence.strip():
        reason += '\nEvidence / confirmation: ' + evidence.strip()
    item = dict(id=str(uuid.uuid4()), issue_key=issue_key, table_name=issue['table'], record_id=issue['record_id'],
                before=before, after=after, reason=reason, status='pending', created_at=now(), decided_at=None, decided_by=None,
                supersedes_id=None, decision_note=None, **provenance(actor, actor_kind, run_id, model))
    try:
        with engine.begin() as c:
            serialize_writes(c)
            # Lock the source before proposal rows, consistently with decide().
            t = DATA_TABLES[issue['table']]
            if issue['table'] == 'clients':
                from backend.merges import active
                active(c, issue['record_id'])
            current = c.execute(select(t).where(t.c.id == issue['record_id']).with_for_update()).mappings().one()
            if dict(current) != before:
                raise Conflict('Record changed while creating the proposal. Refresh and try again.')
            old = c.execute(select(proposals).where(proposals.c.issue_key == issue_key).with_for_update()).mappings().first()
            if replaces_id and (not old or old['id'] != replaces_id or old['status'] not in REPLACEABLE):
                raise Conflict('The pending proposal has changed. Refresh before replacing it.')
            if old and old['status'] == 'pending' and not replaces_id:
                if old['after'] == after and old['reason'] == reason and old['before'] == before:
                    return dict(old)
                raise Conflict('A pending proposal already exists. Open it and choose Replace proposal.')
            if old:
                # Keep old IDs, decisions and audit events. Free the unique finding key for its new revision.
                item['supersedes_id'] = old['id']
                changes = {'issue_key': issue_key + '@' + old['id']}
                if old['status'] == 'pending':
                    changes.update(status='superseded', decided_at=now(), decided_by=actor)
                changed = c.execute(update(proposals).where(proposals.c.id == old['id'], proposals.c.status == old['status'],
                                                           proposals.c.issue_key == issue_key).values(**changes))
                if changed.rowcount != 1:
                    raise Conflict('Another request changed this proposal. Refresh and try again.')
                log(c, {'pending': 'proposal_superseded', 'reevaluation_requested': 'proposal_revised'}.get(old['status'], 'proposal_reopened'),
                    {'proposal_id': old['id'], 'replacement_id': item['id'], 'issue_key': issue_key,
                     'previous_status': old['status'], 'before': old['before'], 'after': old['after']}, actor)
            c.execute(proposals.insert().values(**item))
            log(c, 'proposal_created', item, actor)
    except IntegrityError as exc:
        raise Conflict('A proposal was created by another request. Refresh before continuing.') from exc
    return item


def decide(proposal_id, decision, actor, note=''):
    if decision not in DECISION_STATUS:
        raise ValueError('Invalid decision.')
    note = (note or '').strip()
    with engine.begin() as c:
        serialize_writes(c)
        found = c.execute(select(proposals).where(proposals.c.id == proposal_id)).mappings().first()
        if not found:
            raise ValueError('Proposal not found.')
        check_decision(found, decision, actor, note)
        # Record what the AI reviewer said when the person decided, to measure agreement and overrides later.
        ai = latest_reviews(c, [proposal_id]).get(proposal_id)
        ai_details = {'ai_review_id': ai and ai['id'], 'ai_verdict': ai and ai['verdict']}
        if found['after'].get('action') == 'merge_clients':
            from backend.merges import decide_merge
            return decide_merge(c, found, decision, actor, note, ai_details)
        if decision == 'approve' and found['table_name'] == 'clients':
            from backend.db import client_merges
            if c.scalar(select(client_merges.c.source_id).where(client_merges.c.source_id == found['record_id'])):
                raise Conflict('This profile was merged. Refresh and review the active profile.')
        t = DATA_TABLES[found['table_name']]
        c.execute(select(t.c.id).where(t.c.id == found['record_id']).with_for_update()).first()
        item = c.execute(select(proposals).where(proposals.c.id == proposal_id).with_for_update()).mappings().one()
        if item['status'] != 'pending':
            raise Conflict('This proposal has already been decided or replaced.')
        status = DECISION_STATUS[decision]
        claim = c.execute(update(proposals).where(proposals.c.id == proposal_id, proposals.c.status == 'pending')
                          .values(status=status, decided_at=now(), decided_by=actor, decision_note=note or None))
        if claim.rowcount != 1:
            raise Conflict('Another reviewer already decided this proposal.')
        if decision == 'approve':
            stmt = update(t).where(t.c.id == item['record_id'])
            for key, val in item['before'].items():
                stmt = stmt.where(t.c[key] == val)
            changed = c.execute(stmt.values(**item['after']))
            if changed.rowcount != 1:
                raise Conflict('Record changed after this proposal was created. No changes applied. Replace the proposal using current information.')
        log(c, 'proposal_' + status, {'proposal_id': proposal_id, 'table': item['table_name'], 'record_id': item['record_id'],
                                     'before': item['before'], 'after': item['after'] if decision == 'approve' else item['before'],
                                     'note': note or None, 'proposed_by': item['created_by'], 'run_id': item['run_id'], **ai_details}, actor)
    return {'id': proposal_id, 'status': status}
