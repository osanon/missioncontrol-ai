import os,secrets
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI,Depends,Header,HTTPException,Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import text,select
from backend.db import engine,reader,schema,proposals,audit,runs
from backend.logic import metrics,cohorts,issues,propose,decide,Conflict,list_proposals
from agent.runner import run

@asynccontextmanager
async def lifespan(app):
    for key in ('APP_TOKEN','REVIEW_TOKEN'):
        if len(os.getenv(key,''))<24:raise RuntimeError(f'Set {key} to a random value of at least 24 characters.')
    if os.environ['APP_TOKEN']==os.environ['REVIEW_TOKEN']:raise RuntimeError('Use different analyst and reviewer tokens.')
    yield

app=FastAPI(title='MissionControl AI',version='0.1.0',lifespan=lifespan)

def auth(authorization: str=Header(default='')):
    expected=os.getenv('APP_TOKEN','')
    if not expected or not secrets.compare_digest(authorization,'Bearer '+expected):raise HTTPException(401,'Enter the analyst access token.')

def reviewer(x_review_token: str=Header(default='')):
    expected=os.getenv('REVIEW_TOKEN','')
    if not expected or not secrets.compare_digest(x_review_token,expected):raise HTTPException(403,'A reviewer token is required to decide proposals.')
    return 'local-reviewer'

class Ask(BaseModel):
    question:str=Field(min_length=3,max_length=2000)
    start:str='2026-07-01'
    end:str='2026-09-30'
    previous_run_id:str|None=None
class Proposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    issue_key: str = Field(min_length=3, max_length=100)
    resolution: Literal['follow_up','set_exit_date','reactivate_enrollment','correct_wage','clear_wage','correct_units'] | None = None
    value: str = Field(default='', max_length=100)
    evidence: str = Field(default='', max_length=2000)
    replaces_id: str | None = Field(default=None, max_length=100)
class MergeProposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_id: int = Field(gt=0, strict=True)
    target_id: int = Field(gt=0, strict=True)
    preview_token: str = Field(pattern=r'^[a-f0-9]{64}$')
    evidence: str = Field(min_length=10, max_length=2000)
    replaces_id: str | None = Field(default=None, max_length=100)
class Decision(BaseModel):decision:Literal['approve','reject']

@app.exception_handler(ValueError)
async def validation_error(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=409 if isinstance(exc,Conflict) else 400,content={'detail':str(exc)})

@app.get('/health-check')
def health():
    try:
        with reader.connect() as c:c.execute(text('SELECT 1'))
    except Exception:raise HTTPException(503,'Database unavailable.')
    return {'status':'ok','mode':os.getenv('AGENT_MODE','demo'),'dataset':'fictional','database':reader.dialect.name}
@app.get('/schema',dependencies=[Depends(auth)])
def get_schema():return schema()
@app.get('/metrics',dependencies=[Depends(auth)])
def get_metrics(start:str='2026-07-01',end:str='2026-09-30'):return metrics(start,end)
@app.get('/cohorts',dependencies=[Depends(auth)])
def get_cohorts(start:str='2026-07-01',end:str='2026-09-30'):return cohorts(start,end)
@app.get('/issues',dependencies=[Depends(auth)])
def get_issues():return issues()
@app.post('/proposals',dependencies=[Depends(auth)],status_code=201)
def post_proposal(body:Proposal):return propose(**body.model_dump())
@app.get('/proposals',dependencies=[Depends(auth)])
def get_proposals():
    return list_proposals()
@app.post('/approvals/{proposal_id}',dependencies=[Depends(auth)])
def post_decision(proposal_id:str,body:Decision,actor:str=Depends(reviewer)):return decide(proposal_id,body.decision,actor)
@app.get('/audit-log',dependencies=[Depends(auth)])
def get_audit(limit:int=Query(100,ge=1,le=500)):
    with engine.connect() as c:return [dict(x) for x in c.execute(select(audit).order_by(audit.c.occurred_at.desc()).limit(limit)).mappings()]
@app.post('/ask',dependencies=[Depends(auth)])
def ask(body:Ask):
    previous=None
    if body.previous_run_id:
        with engine.connect() as c:previous=c.execute(select(runs).where(runs.c.id==body.previous_run_id)).mappings().first()
        if previous is None:raise HTTPException(404,'Previous investigation not found.')
    return run(body.question,body.start,body.end,previous)
@app.get('/reports/{run_id}',dependencies=[Depends(auth)],response_class=PlainTextResponse)
def report(run_id:str):
    with engine.connect() as c:item=c.execute(select(runs).where(runs.c.id==run_id)).mappings().first()
    if not item:raise HTTPException(404,'Report not found.')
    import json
    evidence='\n\n'.join(f"## Step {s['step']}: {s['tool']}\n```json\n{json.dumps(s,indent=2,default=str)}\n```" for s in item['trace'])
    return f"# MissionControl AI investigation\n\nFictional data | Mode: {item['mode']} | {item['created_at']}\n\nQuestion: {item['question']}\n\n{item['answer']}\n\n# Evidence\n\n{evidence}"

@app.get('/clients/{client_id}/duplicates',dependencies=[Depends(auth)])
def candidates(client_id:int):
    from backend.merges import duplicate_candidates
    return duplicate_candidates(client_id)
@app.get('/merges/preview',dependencies=[Depends(auth)])
def preview_merge(source_id:int=Query(gt=0),target_id:int=Query(gt=0),replaces_id:str|None=None):
    from backend.merges import merge_preview
    return merge_preview(source_id,target_id,replaces_id)
@app.post('/merges',dependencies=[Depends(auth)],status_code=201)
def create_merge(body:MergeProposal):
    from backend.merges import propose_merge
    return propose_merge(**body.model_dump())
