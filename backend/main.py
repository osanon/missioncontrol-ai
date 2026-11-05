import os,secrets
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI,Depends,Header,HTTPException,Query,Request,Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import text,select
from backend.db import engine,reader,schema,audit,runs
from backend.logic import metrics,cohorts,issues,propose,decide,Conflict,list_proposals
from agent.runner import run
from backend.reviewers import load_reviewers,reviewer_for_token
from backend import sessions
from backend.limits import login_limit,ai_limit

@asynccontextmanager
async def lifespan(app):
    if len(os.getenv('APP_TOKEN',''))<24:raise RuntimeError('Set APP_TOKEN to a random value of at least 24 characters.')
    if not load_reviewers():raise RuntimeError('Configure at least one reviewer in REVIEWERS (run python scripts/configure.py --add-reviewer NAME).')
    yield

app=FastAPI(title='MissionControl AI',version='0.1.0',lifespan=lifespan)

def valid_app_token(value):
    expected=os.getenv('APP_TOKEN','')
    return bool(expected) and secrets.compare_digest(value.encode(),expected.encode())

def current_session(request:Request):
    return sessions.decode(request.cookies.get(sessions.COOKIE,''))

def auth(request:Request,authorization:str=Header(default='')):
    """Analyst access: a Bearer APP_TOKEN (API clients, tests) or a signed browser session."""
    if authorization.startswith('Bearer ') and valid_app_token(authorization[7:]):return
    if current_session(request):
        # Cookie-authenticated writes must carry a custom header, which cross-site pages cannot send without CORS.
        if request.method not in ('GET','HEAD') and request.headers.get(sessions.CSRF_HEADER)!='missioncontrol':
            raise HTTPException(403,'Missing request header. Reload the page and try again.')
        return
    raise HTTPException(401,'Sign in with the analyst access token.')

def reviewer(request:Request,x_review_token:str=Header(default='')):
    name=reviewer_for_token(x_review_token) if x_review_token else sessions.session_reviewer(current_session(request))
    if not name:raise HTTPException(403,'A personal reviewer token is required to decide proposals.')
    return name

class SignIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    app_token: str = Field(max_length=200)
    review_token: str = Field(default='', max_length=200)
class ReviewerSignIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    review_token: str = Field(max_length=200)
class DemoSignIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['analyst','reviewer']
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
class Finding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    issue_key: str = Field(min_length=3, max_length=100)
class ReportPeriod(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    end: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approve','reject','reevaluate']
    note: str = Field(default='', max_length=2000)

@app.exception_handler(ValueError)
async def validation_error(request,exc):
    from fastapi.responses import JSONResponse
    from agent.llm import ProviderError
    from backend.limits import BudgetExceeded
    status=409 if isinstance(exc,Conflict) else 502 if isinstance(exc,ProviderError) else 429 if isinstance(exc,BudgetExceeded) else 400
    return JSONResponse(status_code=status,content={'detail':str(exc)})

@app.get('/health-check')
def health():
    try:
        with reader.connect() as c:c.execute(text('SELECT 1'))
    except Exception:raise HTTPException(503,'Database unavailable.')
    return {'status':'ok','mode':os.getenv('AGENT_MODE','demo'),'dataset':'fictional','database':reader.dialect.name}
@app.get('/session')
def get_session(request:Request):
    payload=current_session(request)
    return {'authenticated':bool(payload),'reviewer':sessions.session_reviewer(payload),'demo':bool(payload and payload.get('demo')),'public_demo':sessions.public_demo()}
@app.post('/session',dependencies=[Depends(login_limit)])
def sign_in(body:SignIn,response:Response):
    if not valid_app_token(body.app_token):raise HTTPException(401,'That analyst access token is not valid.')
    name=None
    if body.review_token:
        name=reviewer_for_token(body.review_token)
        if not name:raise HTTPException(403,'That reviewer token is not valid.')
    sessions.set_cookie(response,sessions.encode(name))
    return {'authenticated':True,'reviewer':name,'demo':False}
@app.post('/session/reviewer',dependencies=[Depends(auth),Depends(login_limit)])
def add_reviewer(body:ReviewerSignIn,request:Request,response:Response):
    name=reviewer_for_token(body.review_token)
    if not name:raise HTTPException(403,'That reviewer token is not valid.')
    payload=current_session(request)
    if payload and payload.get('demo'):raise HTTPException(409,'Demo sessions use the demo reviewer.')
    sessions.set_cookie(response,sessions.encode(name))
    return {'authenticated':True,'reviewer':name,'demo':False}
@app.delete('/session')
def sign_out(response:Response):
    sessions.clear_cookie(response)
    return {'authenticated':False}
@app.post('/demo/session',dependencies=[Depends(login_limit)])
def demo_sign_in(body:DemoSignIn,response:Response):
    if not sessions.public_demo():raise HTTPException(404,'Demo access is not enabled.')
    name=sessions.DEMO_REVIEWER if body.role=='reviewer' else None
    sessions.set_cookie(response,sessions.encode(name,demo=True))
    return {'authenticated':True,'reviewer':name,'demo':True}
@app.get('/schema',dependencies=[Depends(auth)])
def get_schema():return schema()
@app.get('/metrics',dependencies=[Depends(auth)])
def get_metrics(start:str='2026-07-01',end:str='2026-09-30'):return metrics(start,end)
@app.get('/cohorts',dependencies=[Depends(auth)])
def get_cohorts(start:str='2026-07-01',end:str='2026-09-30'):return cohorts(start,end)
@app.get('/issues',dependencies=[Depends(auth)])
def get_issues():return issues()
@app.post('/proposals',dependencies=[Depends(auth)],status_code=201)
def post_proposal(body:Proposal):return propose(**body.model_dump(),actor='analyst',actor_kind='human')
@app.get('/proposals',dependencies=[Depends(auth)])
def get_proposals():
    return list_proposals()
@app.post('/approvals/{proposal_id}',dependencies=[Depends(auth)])
def post_decision(proposal_id:str,body:Decision,actor:str=Depends(reviewer)):return decide(proposal_id,body.decision,actor,body.note)
@app.get('/reviewer',dependencies=[Depends(auth)])
def who_am_i(actor:str=Depends(reviewer)):return {'name':actor}
@app.get('/audit-log',dependencies=[Depends(auth)])
def get_audit(limit:int=Query(100,ge=1,le=500)):
    with engine.connect() as c:return [dict(x) for x in c.execute(select(audit).order_by(audit.c.occurred_at.desc()).limit(limit)).mappings()]
@app.post('/ask',dependencies=[Depends(auth),Depends(ai_limit)])
def ask(body:Ask):
    previous=None
    if body.previous_run_id:
        with engine.connect() as c:previous=c.execute(select(runs).where(runs.c.id==body.previous_run_id)).mappings().first()
        if previous is None:raise HTTPException(404,'Previous investigation not found.')
    return run(body.question,body.start,body.end,previous)
@app.post('/proposals/{proposal_id}/ai-review',dependencies=[Depends(auth),Depends(ai_limit)],status_code=201)
def ai_review(proposal_id:str):
    from agent.reviewer import review_proposal
    return review_proposal(proposal_id)
@app.get('/health-checks/plan',dependencies=[Depends(auth)])
def health_check_plan(limit:int=Query(5,ge=1,le=10)):
    from agent.investigator import plan
    return plan(limit)
@app.post('/health-checks/findings',dependencies=[Depends(auth),Depends(ai_limit)])
def health_check_finding(body:Finding):
    from agent.investigator import investigate_finding
    return investigate_finding(body.issue_key)
@app.get('/ai-trust',dependencies=[Depends(auth)])
def get_ai_trust():
    from backend.trust import ai_trust
    return ai_trust()
@app.post('/funder-report',dependencies=[Depends(auth),Depends(ai_limit)])
def funder_report(body:ReportPeriod):
    from agent.funder_report import draft_report
    return draft_report(body.start,body.end)
@app.get('/runs/{run_id}',dependencies=[Depends(auth)])
def get_run(run_id:str):
    with engine.connect() as c:item=c.execute(select(runs).where(runs.c.id==run_id)).mappings().first()
    if not item:raise HTTPException(404,'Run not found.')
    return dict(item)
@app.get('/reports/{run_id}',dependencies=[Depends(auth)],response_class=PlainTextResponse)
def report(run_id:str):
    with engine.connect() as c:item=c.execute(select(runs).where(runs.c.id==run_id)).mappings().first()
    if not item:raise HTTPException(404,'Report not found.')
    import json
    evidence='\n\n'.join(f"## Step {s['step']}: {s['tool']}\n```json\n{json.dumps(s,indent=2,default=str)}\n```" for s in item['trace'])
    status='' if item['status']=='completed' else f" | Status: {item['status']}"
    title='AI review' if item['kind']=='reviewer' else 'AI investigation'
    return f"# MissionControl {title}\n\nFictional data | Mode: {item['mode']}{status} | {item['created_at']}\n\nQuestion: {item['question']}\n\n{item['answer']}\n\n# Evidence\n\n{evidence}"

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
    return propose_merge(**body.model_dump(),actor='analyst',actor_kind='human')
