"""Deterministic, fictional data; no real client information. Run on a migrated DB (database.migrate)."""
import random
from datetime import date, timedelta
from sqlalchemy import select, func
from backend.db import *

ANOMALIES = {'likely_duplicate_clients':12, 'enrollment_end_before_start':10, 'missing_exit_dates':10, 'invalid_wages':8, 'negative_service_units':6}

def seed(target=engine):
    r=random.Random(42)
    with target.begin() as c:
        if c.scalar(select(func.count()).select_from(clients)): return False
        c.execute(programs.insert(), [{'id':i,'name':n} for i,n in enumerate(['Employment','Housing','Family Support','Early Learning','Youth Programs','Wellbeing'],1)])
        people=[{'id':i,'external_id':f'DEMO-{i:05}', 'full_name':f'Fictional Client {i:04}', 'birth_date':f'{1970+i%35}-06-{1+i%27:02}', 'email':f'client{i}@example.invalid','review_required':False} for i in range(1,2001)]
        for i in range(12):
            people[1988+i].update({k:people[i][k] for k in ('full_name','birth_date','email')})
        c.execute(clients.insert(),people)
        ens=[]; sv=[]; jobs=[]; homes=[]; ass=[]; fus=[]; ss=[]
        for i in range(1,2001):
            # Each client has an employment enrollment and real service evidence.
            start=date(2026,1,1)+timedelta(days=r.randrange(240))
            eid=len(ens)+1
            end=(start+timedelta(days=25)).isoformat() if i%3==0 else None
            ens.append(dict(id=eid,client_id=i,program_id=1,start_date=start.isoformat(),end_date=end,status='exited' if end else 'active',review_required=False))
            pids=[1]
            if i%2==0:
                pids.append(2)
                ens.append(dict(id=len(ens)+1,client_id=i,program_id=2,start_date=start.isoformat(),end_date=end,status='exited' if end else 'active',review_required=False))
                hd=(start+timedelta(days=40)).isoformat() if i%4==0 else None
                # Synthetic quarter effect, not a causal finding.
                stable=r.random() < (.78 if start.month<6 else .59)
                homes.append(dict(id=len(homes)+1,client_id=i,entry_date=start.isoformat(),exit_date=hd,destination=('stable' if stable else 'unstable') if hd else None))
            if i%3==0: pids.append(3+i%4)
            for p in pids:
                for j in range(3):
                    sv.append(dict(id=len(sv)+1,client_id=i,program_id=p,service_date=(start+timedelta(days=j*7)).isoformat(),units=1.0,review_required=False))
            if r.random() < (.62 if i%2==0 else .43):
                jd=start+timedelta(days=20)
                jobs.append(dict(id=len(jobs)+1,client_id=i,start_date=jd.isoformat(),end_date=None,hourly_wage=round(r.uniform(12,25),2),review_required=False))
                fus.append(dict(id=len(fus)+1,employment_id=len(jobs),due_date=(jd+timedelta(days=90)).isoformat(),completed_date=None,retained=None))
            ass.append(dict(id=i,client_id=i,assessment_date=start.isoformat(),kind='work_readiness',score=r.randrange(30,101)))
        for i in range(10): ens[i]['end_date']='2025-01-01';ens[i]['status']='exited'
        for i in range(10,20): ens[i]['end_date']=None;ens[i]['status']='exited'
        for i in range(8): jobs[i]['hourly_wage']=-15.0 if i%2 else 1500.0
        for i in range(6): sv[i]['units']=-1.0
        for i in range(1,301): ss.append(dict(id=i,program_id=1+i%6,response_date='2026-09-15',rating=r.randrange(4,11),comment='Fictional survey response for demonstration.'))
        for t,rows in [(enrollments,ens),(services,sv),(employment,jobs),(housing,homes),(assessments,ass),(followups,fus),(surveys,ss)]: c.execute(t.insert(),rows)
    return True

if __name__=='__main__':
    from database.migrate import upgrade
    upgrade()
    print('Seeded fictional dataset.' if seed() else 'Existing dataset preserved.')
