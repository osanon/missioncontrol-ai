"""Human-only, audited editing of synthetic profiles; never exposed as agent tools."""
import hashlib,json,math
from datetime import date
from sqlalchemy import select,func,or_,update
from backend.db import engine,clients,client_merges,DATA_TABLES,proposals
from backend.logic import Conflict,log
from backend.mutations import serialize_writes
EDITABLE={'clients':['full_name','birth_date','email'],'enrollments':['status','start_date','end_date'],'employment':['start_date','end_date','hourly_wage'],'services':['service_date','units'],'housing':['entry_date','exit_date','destination']}
def version(row):return hashlib.sha256(json.dumps(dict(row),sort_keys=True,default=str).encode()).hexdigest()
def directory(q='',page=0,archived=False):
    with engine.connect() as c:
        filt=or_(clients.c.full_name.ilike('%'+q+'%'),clients.c.external_id.ilike('%'+q+'%'),clients.c.email.ilike('%'+q+'%'))
        stmt=select(clients,client_merges.c.target_id).outerjoin(client_merges,clients.c.id==client_merges.c.source_id).where(filt)
        if not archived:stmt=stmt.where(client_merges.c.source_id.is_(None))
        total=c.scalar(select(func.count()).select_from(stmt.subquery()))
        rows=[dict(r) for r in c.execute(stmt.order_by(clients.c.full_name,clients.c.id).offset(page*25).limit(25)).mappings()]
    return {'rows':rows,'total':total,'page':page}
def profile(client_id):
    with engine.connect() as c:
        person=c.execute(select(clients).where(clients.c.id==client_id)).mappings().first()
        if not person:raise ValueError('Client not found.')
        target=c.scalar(select(client_merges.c.target_id).where(client_merges.c.source_id==client_id))
        groups={}; counts={}
        for name in ['enrollments','employment','services','housing','assessments']:
            t=DATA_TABLES[name];stmt=select(t).where(t.c.client_id==client_id)
            counts[name]=c.scalar(select(func.count()).select_from(stmt.subquery()))
            groups[name]=[{'record':dict(r),'version':version(r)} for r in c.execute(stmt.order_by(t.c.id.desc()).limit(100)).mappings()]
        t=DATA_TABLES['followups'];jobs=DATA_TABLES['employment']
        stmt=select(t).join(jobs,t.c.employment_id==jobs.c.id).where(jobs.c.client_id==client_id)
        counts['followups']=c.scalar(select(func.count()).select_from(stmt.subquery()))
        groups['followups']=[{'record':dict(r),'version':version(r)} for r in c.execute(stmt.order_by(t.c.id.desc()).limit(100)).mappings()]
        program_names={r.id:r.name for r in c.execute(select(DATA_TABLES['programs']))}
    return {'client':dict(person),'version':version(person),'merged_into':target,'groups':groups,'counts':counts,'programs':program_names,'editable':EDITABLE}
def edit(client_id,table,record_id,expected,patch,note,actor):
    if table not in EDITABLE or not patch or set(patch)-set(EDITABLE[table]):raise ValueError('Unsupported field or table.')
    if len(note.strip())<10:raise ValueError('Describe why this synthetic record is being edited.')
    clean={}
    for k,v in patch.items():
        if k in ('hourly_wage','units'):
            if v is None and k=='hourly_wage':clean[k]=None;continue
            if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v):raise ValueError('Enter a finite number.')
        elif v is not None and (not isinstance(v,str) or len(v)>200):raise ValueError('Text must be at most 200 characters.')
        if k.endswith('_date') and v is not None:
            if date.fromisoformat(v).isoformat()!=v:raise ValueError('Use YYYY-MM-DD dates.')
        if k in ('full_name','start_date','service_date','entry_date','status') and not v:raise ValueError('Required fields cannot be blank.')
        if k=='status' and v not in ('active','exited'):raise ValueError('Choose active or exited.')
        if k=='destination' and v not in (None,'stable','unstable','unknown'):raise ValueError('Choose stable, unstable, unknown, or blank.')
        clean[k]=v
    t=DATA_TABLES[table]
    with engine.begin() as c:
        serialize_writes(c)
        if c.scalar(select(client_merges.c.source_id).where(client_merges.c.source_id==client_id)):raise Conflict('Archived profile: open the retained profile to edit.')
        row=c.execute(select(t).where(t.c.id==record_id).with_for_update()).mappings().first()
        if not row or (row['id'] if table=='clients' else row['client_id'])!=client_id:raise ValueError('Record does not belong to this client.')
        if version(row)!=expected:raise Conflict('Record changed. Reload the profile before editing.')
        # Pending corrections/merges must be decided before direct human edits.
        for p in c.execute(select(proposals).where(proposals.c.status=='pending')).mappings():
            if (p['table_name']==table and p['record_id']==record_id) or (p['after'].get('action')=='merge_clients' and client_id in (p['after'].get('source_id'),p['after'].get('target_id'))):raise Conflict('A pending proposal affects this record. Reject or resolve it before direct editing.')
        c.execute(update(t).where(t.c.id==record_id).values(**clean))
        log(c,'test_record_edited',{'client_id':client_id,'table':table,'record_id':record_id,'before':dict(row),'after':{**dict(row),**clean},'note':note},actor)
    return profile(client_id)
