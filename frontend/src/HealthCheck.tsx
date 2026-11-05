import { useRef, useState } from 'react';
import { ArrowRight, Check, CircleAlert, Clock3, LoaderCircle, Play, Sparkles, Square } from 'lucide-react';
import { AIChip, type AIReview } from './AIReview';
import { kindLabels } from './Workbench';

type Planned = {key:string;kind:string;title:string;severity:string;record_id:number};
type Result = {proposal:{id:string;after:Record<string,unknown>;reason:string};review:AIReview|null;review_error:string|null};
type Row = Planned&{state:'waiting'|'working'|'done'|'failed';result?:Result;error?:string};
type Api = <T>(path:string,init?:RequestInit)=>Promise<T>;

function describe(after:Record<string,unknown>){
 if('hourly_wage' in after&&after.hourly_wage===null)return 'Clear the wage and flag for follow-up';
 const keys=Object.keys(after);
 if(keys.length===1&&keys[0]==='review_required')return 'Flag for follow-up';
 return 'Set '+keys.filter(k=>k!=='review_required').map(k=>`${k.replaceAll('_',' ')} to ${String(after[k])}`).join(', ');
}

// The browser asks for one finding at a time: the AI investigator proposes a fix, then the independent AI reviewer checks it.
export function HealthCheckPanel({api,live,onChanged,onOpen}:{api:Api;live:boolean;onChanged:()=>void;onOpen:(proposalId:string)=>void}){
 const [rows,setRows]=useState<Row[]>([]),[running,setRunning]=useState(false),[stopping,setStopping]=useState(false),[message,setMessage]=useState('');
 const stop=useRef(false);
 const update=(key:string,patch:Partial<Row>)=>setRows(rs=>rs.map(r=>r.key===key?{...r,...patch}:r));
 async function run(){
  stop.current=false;setStopping(false);setRunning(true);setMessage('');setRows([]);
  try{
   const plan=await api<Planned[]>('/health-checks/plan?limit=5');
   setRows(plan.map(p=>({...p,state:'waiting'})));
   if(!plan.length)setMessage('No open findings: every finding already has a proposal or a follow-up flag.');
   for(const p of plan){
    if(stop.current){setMessage('Stopped. Findings that were not checked stay open in Data Health.');break;}
    update(p.key,{state:'working'});
    try{update(p.key,{state:'done',result:await api<Result>('/health-checks/findings',{method:'POST',body:JSON.stringify({issue_key:p.key})})});}
    catch(e){update(p.key,{state:'failed',error:e instanceof Error?e.message:'The check failed.'});}
   }
  }catch(e){setMessage(e instanceof Error?e.message:'The health check could not start.');}
  finally{setRunning(false);setStopping(false);onChanged();}
 }
 const done=rows.filter(r=>r.state==='done'),disagree=done.filter(r=>r.result?.review?.verdict==='disagree').length;
 return <section className="card health-check">
  <div className="health-check-head">
   <div><h2><Sparkles size={18}/>AI health check</h2><p>An AI investigator proposes the safest fix for up to five open findings, one of each kind first. An independent AI reviewer then checks every proposal. Nothing changes until a person approves it.</p></div>
   {running?<button className="secondary" disabled={stopping} onClick={()=>{stop.current=true;setStopping(true);}}><Square size={14}/>{stopping?'Stopping…':'Stop after this finding'}</button>
    :<button className="primary" onClick={()=>void run()}><Play size={15}/>Run health check</button>}
  </div>
  <small className="health-check-mode">{live?'Live AI: each finding takes about 20–60 seconds and uses AI tokens.':'Guided demo: rule-based proposals and reviews, no AI cost.'}</small>
  {rows.length>0&&<ol className="health-check-list">{rows.map(r=><li key={r.key} className={r.state}>
   <span className="health-check-icon">{r.state==='working'?<LoaderCircle size={16} className="spin"/>:r.state==='done'?<Check size={16}/>:r.state==='failed'?<CircleAlert size={16}/>:<Clock3 size={16}/>}</span>
   <div className="health-check-finding"><b>{r.title}</b><small>{kindLabels[r.kind]??r.kind} · record #{r.record_id}</small>
    {r.error&&<p className="health-check-error">{r.error}</p>}
    {r.result?.review_error&&<p className="health-check-error">The proposal was created, but the AI review did not finish. You can rerun it from Approvals.</p>}</div>
   <div className="health-check-result">{r.state==='waiting'&&<span className="muted">Waiting</span>}
    {r.state==='working'&&<span className="muted">Investigating, then reviewing…</span>}
    {r.state==='failed'&&<span className="muted">Not proposed</span>}
    {r.result&&<><span>{describe(r.result.proposal.after)}</span><AIChip review={r.result.review}/><button className="text-button" onClick={()=>onOpen(r.result!.proposal.id)}>Open<ArrowRight size={13}/></button></>}</div>
  </li>)}</ol>}
  {!running&&done.length>0&&<p className="health-check-summary"><b>{done.length} {done.length===1?'proposal':'proposals'} ready for your decision</b>{disagree>0&&` · the AI reviewer disagrees with ${disagree}, so check ${disagree===1?'it':'them'} first`}.</p>}
  {message&&<p className="muted">{message}</p>}
 </section>;
}