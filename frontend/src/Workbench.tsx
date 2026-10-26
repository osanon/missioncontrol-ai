import { useEffect, useState, type ReactNode } from 'react';
import { ArrowRight, Check, CircleHelp, Clock3, FileSearch, Flag, Search, ShieldCheck } from 'lucide-react';
import { ProposalCard, type Issue, type Proposal } from './CorrectionReview';
import { MergeCard } from './MergeReview';
import { AIChip, AIReviewPanel, reviewRank, verdictOf, verdictLabels, type ReviewRun } from './AIReview';

export const kindLabels:Record<string,string>={missing_exit:'Missing exit dates',invalid_dates:'Date conflicts',wage_outlier:'Wage outliers',negative_units:'Service units',duplicate:'Duplicate profiles'};
const stateLabels:Record<string,string>={new:'Needs a decision',pending:'Proposal pending',followup:'Follow-up flagged',reevaluate:'Sent back for reevaluation'};
const statusLabels:Record<string,string>={pending:'Pending review',applied:'Applied',rejected:'Rejected',superseded:'Superseded',reevaluation_requested:'Sent back'};
export function provenance(p:Proposal){if(!p.created_by)return 'Proposed before authorship was recorded';if(p.created_by_kind==='agent')return `Proposed by AI agent${p.model?` (${p.model})`:''}${p.run_id?` · investigation ${p.run_id.slice(0,8)}`:''}`;return `Proposed by ${p.created_by}`;}
const pretty=(x:unknown)=>JSON.stringify(x,null,2);
export function pendingForIssue(i:Issue,proposals:Proposal[]){
 return proposals.find(p=>p.status==='pending'&&p.proposal_type==='merge'&&i.kind==='duplicate'&&[p.after.source_id,p.after.target_id].includes(i.record_id))??proposals.find(p=>p.status==='pending'&&(p.base_issue_key??p.issue_key)===i.key);
}
function stateFor(i:Issue,proposals:Proposal[]){return pendingForIssue(i,proposals)?'pending':i.proposal_status==='reevaluation_requested'?'reevaluate':i.review_required?'followup':'new';}
// Sent-back findings need a new proposal, so they count under "Needs a decision".
function bucket(i:Issue,proposals:Proposal[]){const s=stateFor(i,proposals);return s==='reevaluate'?'new':s;}
function label(v:unknown){return v===null||v===undefined||v===''?'Missing':typeof v==='boolean'?v?'Yes':'No':String(v);}
function shortRecord(i:Issue){const r=i.record;switch(i.kind){case 'missing_exit':return `Status: ${label(r.status)} · Exit date: ${label(r.end_date)}`;case 'invalid_dates':return `Start: ${label(r.start_date)} · Exit: ${label(r.end_date)}`;case 'wage_outlier':return `Hourly wage: ${typeof r.hourly_wage==='number'?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(r.hourly_wage):label(r.hourly_wage)}`;case 'negative_units':return `Service units: ${label(r.units)} · Date: ${label(r.service_date)}`;default:return `Date of birth: ${label(r.birth_date)} · Identity confirmation required`;}}

export function DataHealthBoard({issues,proposals,disabled,onResolve,onReview}:{issues:Issue[];proposals:Proposal[];disabled:boolean;onResolve:(i:Issue)=>void;onReview:(p:Proposal)=>void}){
 const [search,setSearch]=useState(''),[kind,setKind]=useState('all'),[state,setState]=useState('all'),[priority,setPriority]=useState('all'),[page,setPage]=useState(0);
 useEffect(()=>setPage(0),[search,kind,state,priority]);
 const visible=issues.filter(i=>(kind==='all'||kind===i.kind)&&(priority==='all'||priority===i.severity)&&(state==='all'||state===bucket(i,proposals))&&[i.title,i.reason,i.table,i.record_id,i.context?.client_name,i.context?.client_identifier,i.context?.program].join(' ').toLowerCase().includes(search.toLowerCase())).sort((a,b)=>(a.severity==='high'?0:1)-(b.severity==='high'?0:1)||a.record_id-b.record_id);
 const maxPage=Math.max(0,Math.ceil(visible.length/8)-1),current=Math.min(page,maxPage),rows=visible.slice(current*8,current*8+8);
 function clear(){setSearch('');setKind('all');setState('all');setPriority('all');setPage(0);}
 return <><div className="queue-summary">{[['all','All findings',issues.length,FileSearch],['new','Needs a decision',issues.filter(i=>bucket(i,proposals)==='new').length,CircleHelp],['pending','Proposal pending',issues.filter(i=>stateFor(i,proposals)==='pending').length,Clock3],['followup','Follow-up flagged',issues.filter(i=>stateFor(i,proposals)==='followup').length,Flag]].map(([id,title,count,Icon])=>{const Glyph=Icon as typeof Flag;return <button key={String(id)} aria-pressed={state===id} className={'queue-stat '+(state===id?'selected':'')} onClick={()=>setState(String(id))}><Glyph size={18}/><strong>{Number(count)}</strong><span>{String(title)}</span></button>;})}</div>
 <div className="scope-note"><ShieldCheck size={17}/><span>Findings cover all records. A follow-up flag keeps an issue visible; it does not fix the underlying data.</span></div>
 <section className="card queue-card"><div className="queue-toolbar"><label className="queue-search"><Search size={18}/><input aria-label="Search findings" placeholder="Search client, ID, program or issue…" value={search} onChange={e=>setSearch(e.target.value)}/></label><label className="filter-label">Issue type<select aria-label="Issue type" value={kind} onChange={e=>setKind(e.target.value)}><option value="all">All issue types</option>{Object.entries(kindLabels).map(([id,title])=><option key={id} value={id}>{title} ({issues.filter(i=>i.kind===id).length})</option>)}</select></label><label className="filter-label">Priority<select aria-label="Priority" value={priority} onChange={e=>setPriority(e.target.value)}><option value="all">All priorities</option><option value="high">High priority</option><option value="medium">Medium priority</option></select></label></div>
 <div className="queue-caption"><span><b>{visible.length}</b> matching findings <span className="muted">· High priority first</span></span>{(search||kind!=='all'||priority!=='all'||state!=='all')&&<button className="text-button" onClick={clear}>Clear filters</button>}</div>
 <div className="triage-list">{rows.map(i=>{const pending=pendingForIssue(i,proposals),status=stateFor(i,proposals);return <article className="triage-item" key={i.key}><div className={'triage-mark '+i.severity}><FileSearch size={20}/></div><div className="triage-content"><div className="triage-title"><h3>{i.title}</h3><span className={'severity '+i.severity}>{i.severity} priority</span></div><p className="triage-person">{i.context?.client_name??i.table} <span>· {i.context?.client_identifier??`Record #${i.record_id}`}{i.context?.program?` · ${i.context.program}`:''}</span></p><p className="record-glance">{shortRecord(i)}</p><div className="triage-meta"><span className={'workflow-state '+status}>{stateLabels[status]}</span><span>{i.table} #{i.record_id}</span></div><details className="source-details"><summary>Why this was flagged</summary><p>{i.reason}</p><details><summary>Source record & query</summary><pre>{pretty(i.record)}</pre><code>{i.source_sql}</code></details></details></div><button className="secondary triage-action" disabled={disabled} onClick={()=>pending?onReview(pending):onResolve(i)}>{pending?'Review proposal':i.kind==='duplicate'?'Compare profiles':'Choose resolution'}<ArrowRight size={15}/></button></article>;})}</div>
 {!rows.length&&<div className="empty"><Search size={28}/><h3>{issues.length?'No matching findings':'No current findings'}</h3><p>{issues.length?'Try another client, issue type or workflow status.':'The current quality checks found no exceptions.'}</p>{issues.length>0&&<button className="secondary" onClick={clear}>Clear filters</button>}</div>}
 <div className="pagination"><span>{visible.length?`${current*8+1}–${Math.min((current+1)*8,visible.length)} of ${visible.length}`:'0 findings'}</span><div><button className="secondary" disabled={!current} onClick={()=>setPage(current-1)}>Previous</button><span>Page {current+1} of {maxPage+1}</span><button className="secondary" disabled={current>=maxPage} onClick={()=>setPage(current+1)}>Next</button></div></div></section></>;
}

export function proposalTitle(p:Proposal){if(p.proposal_type==='merge')return 'Merge duplicate profiles';if(p.proposal_type==='follow_up')return 'Flag for follow-up';const kind=(p.base_issue_key??p.issue_key).split(':')[0];return ({missing_exit:p.after.status==='active'?'Reactivate enrollment':'Confirm exit date',invalid_dates:'Correct exit date',wage_outlier:p.after.hourly_wage===null?'Clear unverified wage':'Correct hourly wage',negative_units:'Correct service units'} as Record<string,string>)[kind]??'Record correction';}
function proposalSearch(p:Proposal){return [proposalTitle(p),p.record_id,p.context?.client_name,p.context?.client_identifier,p.context?.program,p.status,p.reason,p.after.source_id,p.after.target_id].join(' ').toLowerCase();}
const money=(v:unknown)=>typeof v==='number'?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(v):'an unknown amount';
const aiSentence:Record<string,string>={agree:' The AI reviewer agrees.',disagree:' The AI reviewer disagrees; read its concerns.',uncertain:' The AI reviewer is unsure; read its concerns.'};
const recordNames:Record<string,string>={enrollments:'enrollment',services:'service record',employment:'job record',clients:'client profile'};
/** One plain sentence: what approving this proposal would change. */
export function plainSummary(p:Proposal){
 const who=p.context?.client_name??`record #${p.record_id}`,program=p.context?.program?`${p.context.program} `:'',a=p.after,b=p.before;
 let text:string;
 if(p.proposal_type==='merge')text=`Merge duplicate profile #${String(a.source_id)} into #${String(a.target_id)} (${who}); the duplicate's linked records move to the kept profile.`;
 else if(p.proposal_type==='follow_up')text=`Flag ${who}'s ${recordNames[p.table_name]??'record'} #${p.record_id} for follow-up; no values change.`;
 else if('units' in a)text=`Change service units on ${who}'s record from ${String(b.units)} to ${String(a.units)}.`;
 else if('hourly_wage' in a)text=a.hourly_wage==null?`Clear the ${money(b.hourly_wage)} hourly wage on ${who}'s job and flag it for follow-up.`:`Change ${who}'s hourly wage from ${money(b.hourly_wage)} to ${money(a.hourly_wage)}.`;
 else if(a.status==='active')text=`Reactivate ${who}'s ${program}enrollment.`;
 else text=`Set the exit date of ${who}'s ${program}enrollment to ${String(a.end_date)}.`;
 return text+(p.status==='pending'&&p.ai_review?aiSentence[p.ai_review.verdict]??'':'');
}
function typing(e:KeyboardEvent){const t=e.target as HTMLElement|null;return !!t&&(['INPUT','TEXTAREA','SELECT'].includes(t.tagName)||t.isContentEditable);}
function time(v?:string|null){return v?new Date(v).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'Time unavailable';}

export function ReviewWorkspace({proposals,issues,history,selectedId,onSelect,working,reviewer,live,reviewing,onAIReview,loadRun,onDecide,onResolve,onMerge,onHealth}:{proposals:Proposal[];issues:Issue[];history:boolean;selectedId:string|null;onSelect:(id:string)=>void;working:boolean;reviewer:boolean;live:boolean;reviewing:string;onAIReview:(p:Proposal)=>void;loadRun:(id:string)=>Promise<ReviewRun>;onDecide:(p:Proposal,d:'approve'|'reject'|'reevaluate',next?:string)=>void;onResolve:(i:Issue,p:Proposal)=>void;onMerge:(source:number,target:number,id:string)=>void;onHealth:()=>void}){
 const [search,setSearch]=useState(''),[status,setStatus]=useState('all'),[ai,setAI]=useState('all');
 useEffect(()=>{setSearch('');setStatus('all');setAI('all');},[history]);
 const matching=proposals.filter(p=>(history?p.status!=='pending':p.status==='pending')&&(status==='all'||p.status===status)&&(ai==='all'||verdictOf(p.ai_review)===ai)&&proposalSearch(p).includes(search.toLowerCase()));
 // Pending work: AI disagreements first so dissent is never buried. History keeps decision order.
 const rows=history?matching:[...matching].sort((a,b)=>reviewRank(a.ai_review)-reviewRank(b.ai_review));
 const selected=rows.find(p=>p.id===selectedId)??rows[0];
 const index=selected?rows.indexOf(selected):-1;
 // After a decision, move to the next proposal in the queue (or the previous one at the end).
 const nextId=(rows[index+1]??rows[index-1])?.id;
 const decide=(d:'approve'|'reject'|'reevaluate')=>{if(selected)onDecide(selected,d,nextId);};
 useEffect(()=>{
  if(history)return;
  function onKey(e:KeyboardEvent){
   if(e.metaKey||e.ctrlKey||e.altKey||typing(e)||document.querySelector('dialog[open]')||!selected)return;
   const key=e.key.toLowerCase();
   if(key==='j'||key==='k'){const target=rows[index+(key==='j'?1:-1)];if(target){e.preventDefault();onSelect(target.id);}return;}
   if(!reviewer||working||selected.status!=='pending')return;
   // Merges move linked records, so they are approved with a click only.
   if(key==='a'&&selected.proposal_type!=='merge'){e.preventDefault();decide('approve');}
   else if(key==='r'){e.preventDefault();decide('reject');}
   else if(key==='s'){e.preventDefault();decide('reevaluate');}
  }
  window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
 });
 return <><div className="review-filter"><label className="queue-search"><Search size={18}/><input aria-label="Search proposals" placeholder="Search client, record or proposed action…" value={search} onChange={e=>setSearch(e.target.value)}/></label>{history&&<label className="filter-label">Decision<select aria-label="Decision filter" value={status} onChange={e=>setStatus(e.target.value)}><option value="all">All decisions</option><option value="applied">Applied</option><option value="rejected">Rejected</option><option value="superseded">Superseded</option><option value="reevaluation_requested">Sent back for reevaluation</option></select></label>}<label className="filter-label">AI review<select aria-label="AI review filter" value={ai} onChange={e=>setAI(e.target.value)}><option value="all">All</option>{['disagree','uncertain','none','agree'].map(v=><option key={v} value={v}>{verdictLabels[v]}</option>)}</select></label><span>{rows.length} proposal{rows.length===1?'':'s'}{!history&&rows.length>1&&' · AI disagreements first'}</span></div>{!history&&rows.length>0&&<p className="shortcut-hint">Keyboard: <kbd>J</kbd>/<kbd>K</kbd> next/previous{reviewer&&<> · <kbd>A</kbd> approve · <kbd>R</kbd> reject · <kbd>S</kbd> send back (merges are approved by click)</>}</p>}
 {selected?<div className="review-workspace"><aside className="review-queue card" aria-label="Proposal queue"><div className="review-queue-heading">{history?'Decision history':'Waiting for a decision'}</div>{rows.map(p=><button className={'review-choice '+(selected.id===p.id?'selected':'')} aria-pressed={selected.id===p.id} key={p.id} onClick={()=>onSelect(p.id)}><span className={'workflow-state '+p.status}>{statusLabels[p.status]??p.status}</span><AIChip review={p.ai_review}/><strong>{proposalTitle(p)}</strong><span>{p.context?.client_name??`Record #${p.record_id}`}</span><small>{p.context?.client_identifier??p.table_name} · #{p.record_id}</small><small>{time(history?p.decided_at:p.created_at)}</small></button>)}</aside><div className="review-detail" aria-live="polite"><div className="review-detail-kicker"><span>{history?'Saved decision':'Review before applying'}</span><span>{time(history?selected.decided_at:selected.created_at)}</span></div><p className="plain-summary">{plainSummary(selected)}</p><p className="provenance">{provenance(selected)}</p><AIReviewPanel key={selected.id} review={selected.ai_review} pending={selected.status==='pending'} live={live} running={reviewing===selected.id} onRun={()=>onAIReview(selected)} loadRun={loadRun} renderTrail={steps=><InvestigationTrail steps={steps}/>}/>{selected.proposal_type==='merge'?<MergeCard proposal={selected} reviewer={reviewer} working={working} onDecide={(_,d)=>decide(d)} onReplace={onMerge}/>:<ProposalCard proposal={selected} issue={issues.find(i=>i.key===(selected.base_issue_key??selected.issue_key))} working={working} reviewer={reviewer} onDecide={(_,d)=>decide(d)} onResolve={onResolve}/>}</div></div>:<div className="card empty"><ShieldCheck size={32}/><h3>{search||status!=='all'?'No matching proposals':history?'No decisions yet':'Nothing waiting on you.'}</h3><p>{search||status!=='all'?'Change your search or filter to see other proposals.':history?'Applied, rejected and replaced proposals will appear here.':'Choose an issue in Data Health to prepare a correction or merge.'}</p><button className="secondary" onClick={onHealth}>Explore Data Health<ArrowRight size={16}/></button></div>}</>;
}

export type AuditEvent={id:string;occurred_at:string;actor:string;event:string;details:unknown};
export function AuditTimeline({events}:{events:AuditEvent[]}){
 const [search,setSearch]=useState('');
 const rows=events.filter(e=>[e.event,e.actor,pretty(e.details)].join(' ').toLowerCase().includes(search.toLowerCase()));
 const titles:Record<string,string>={analysis_completed:'Investigation completed',proposal_created:'Correction proposed',merge_proposed:'Merge proposed',proposal_applied:'Proposal approved and applied',proposal_rejected:'Proposal rejected',proposal_superseded:'Proposal replaced',proposal_reopened:'New proposal for an existing issue',proposal_reevaluation_requested:'Sent back for reevaluation',ai_review_completed:'AI review completed',ai_review_failed:'AI review failed',proposal_revised:'Revised after reevaluation',analysis_failed:'Investigation failed',clients_merged:'Client profiles merged'};
 return <section className="card audit-timeline"><div className="queue-toolbar"><label className="queue-search"><Search size={18}/><input aria-label="Search audit log" placeholder="Search action, reviewer or record ID…" value={search} onChange={e=>setSearch(e.target.value)}/></label><span className="muted">Latest {events.length} events loaded · up to 100</span></div>{rows.map(e=>{const d=e.details&&typeof e.details==='object'?e.details as Record<string,unknown>:{};return <article className="audit-event" key={e.id}><span className="audit-icon"><Check size={16}/></span><div><h3>{titles[e.event]??e.event.replaceAll('_',' ')}</h3><p>{e.actor} · {time(e.occurred_at)}</p>{d.source_id!==undefined&&<p>Profile #{label(d.source_id)} → #{label(d.target_id)}</p>}{d.table!==undefined&&<p>{label(d.table)} · Record #{label(d.record_id)}</p>}{typeof d.note==='string'&&<p>Note: “{d.note}”</p>}{typeof d.verdict==='string'&&<p>{verdictLabels[d.verdict]??d.verdict}</p>}{typeof d.ai_verdict==='string'&&<p>AI reviewer had said: {verdictLabels[d.ai_verdict]??d.ai_verdict}</p>}<details><summary>View saved evidence</summary><pre>{pretty(e.details)}</pre></details></div></article>;})}{!rows.length&&<div className="empty"><h3>No matching activity</h3><p>Investigations and review decisions are recorded here.</p></div>}</section>;
}

export type TraceStep={step:number;tool:string;arguments:Record<string,unknown>;status:string;result:unknown;duration_ms:number};
function traceSummary(s:TraceStep):ReactNode{
 const r=s.result&&typeof s.result==='object'?s.result as Record<string,unknown>:{};
 if(s.status==='failed')return typeof r.error==='string'?r.error:'This step could not be completed.';
 if(s.tool==='inspect_schema')return `${Object.keys(r).length} tables available for investigation.`;
 if(s.tool==='check_quality')return `${Array.isArray(r.issues)?r.issues.length:0} findings across the full dataset.`;
 if(s.tool==='query_sql')return `${Array.isArray(r.rows)?r.rows.length:0} rows returned${r.truncated?' (result limited)':''}.`;
 if(s.tool==='calculate_metrics')return `${label(r.clients_served)} clients served · ${label(r.new_jobs)} job records.`;
 if(s.tool==='compare_periods')return 'Compared the selected period with the preceding period.';
 if(s.tool==='compare_cohorts')return 'Compared outcomes across service groups.';
 if(s.tool.startsWith('propose'))return r.status==='pending'?'Proposal saved for review. No source changes applied.':`Proposal status: ${label(r.status)}.`;
 if(s.tool==='preview_merge')return 'Compared profiles and linked records; no changes applied.';
 return 'Evidence returned. Expand to inspect the details.';
}
export function InvestigationTrail({steps}:{steps:TraceStep[]}){return <div>{steps.map(s=><details key={s.step} className="trace"><summary><span className={'step-icon '+(s.status==='failed'?'failed':'')}>{s.status==='completed'?<Check size={14}/>:<CircleHelp size={14}/>}</span><div><b>{s.tool.replaceAll('_',' ')}</b><small>Step {s.step} · {s.duration_ms} ms · {s.status}</small><p>{traceSummary(s)}</p></div></summary><pre>{pretty({arguments:s.arguments,result:s.result})}</pre></details>)}</div>;}
