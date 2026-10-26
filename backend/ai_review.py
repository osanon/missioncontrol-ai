"""One finding per request: a failed run cannot apply changes or approve a proposal."""
import os,json
from sqlalchemy import select
from backend.db import engine,proposals,audit
from backend.logic import issues,Conflict,log
from backend.mutations import serialize_writes

def review(issue_key,feedback='',proposal_id=None):
    if os.getenv('AGENT_MODE','demo')!='live':raise ValueError('AI review requires live mode and a configured model API key. Guided demo does not call a model.')
    finding=next((i for i in issues() if i['key']==issue_key),None)
    if not finding:raise Conflict('This finding no longer applies. Refresh Data Health.')
    previous=None
    with engine.begin() as c:
        serialize_writes(c)
        if proposal_id:
            previous=c.execute(select(proposals).where(proposals.c.id==proposal_id)).mappings().first()
            if not previous or previous['status']!='pending' or (previous['issue_key']!=issue_key and not (previous['after'].get('action')=='merge_clients' and finding['record_id'] in (previous['after'].get('source_id'),previous['after'].get('target_id')) and finding['kind']=='duplicate')):raise Conflict('The proposal changed. Refresh before requesting revision.')
            if len(feedback.strip())<10:raise ValueError('Explain what the AI should reconsider (at least 10 characters).')
            log(c,'ai_revision_requested',{'proposal_id':proposal_id,'issue_key':issue_key,'feedback':feedback},'local-reviewer')
        else:
            pending=next((p for p in c.execute(select(proposals).where(proposals.c.status=='pending')).mappings() if p['issue_key']==issue_key or (finding['kind']=='duplicate' and p['after'].get('action')=='merge_clients' and finding['record_id'] in (p['after'].get('source_id'),p['after'].get('target_id')))),None)
            if pending:raise Conflict('A proposal already exists. Open it to request a revision.')
        log(c,'ai_review_requested',{'issue_key':issue_key,'feedback':feedback},'analyst')
    from agent.runner import run
    prompt='Investigate this Data Health finding and propose a resolution if justified. If evidence is insufficient, propose follow-up if available, or explain precisely what confirmation is needed. Never invent a correction.\nFinding: '+json.dumps(finding,default=str)
    if previous:prompt+='\nPrevious proposal: '+json.dumps(dict(previous),default=str)
    if feedback:prompt+='\nReviewer feedback / confirmation (not permission to approve): '+feedback
    result=run(prompt,'2026-07-01','2026-09-30',review_scope={'issue_key':issue_key,'replaces_id':proposal_id,'record_id':finding['record_id'],'kind':finding['kind']})
    with engine.connect() as c:
        saved=next((p for p in c.execute(select(proposals).where(proposals.c.status=='pending').order_by(proposals.c.created_at.desc())).mappings() if p['issue_key']==issue_key or (finding['kind']=='duplicate' and p['after'].get('action')=='merge_clients' and finding['record_id'] in (p['after'].get('source_id'),p['after'].get('target_id')))),None)
    return {'run':result,'proposal_id':saved['id'] if saved and saved['id']!=proposal_id else None,'revision_requested':bool(proposal_id)}
