import { useState, type ReactNode } from 'react';
import { Bot, LoaderCircle, RefreshCw } from 'lucide-react';

export type AIReview = {id:string;proposal_id:string;run_id:string;reviewer:string;mode:string;model:string|null;verdict:'agree'|'disagree'|'uncertain';confidence:'low'|'medium'|'high';summary:string;concerns:string[];created_at:string};
export type ReviewRun = {id:string;trace:{step:number;tool:string;arguments:Record<string,unknown>;status:string;result:unknown;duration_ms:number}[]};

export const verdictLabels:Record<string,string>={agree:'AI agrees',disagree:'AI disagrees',uncertain:'AI unsure',none:'Not AI-reviewed'};
export function verdictOf(review?:AIReview|null){return review?review.verdict:'none';}
// Queue order: put AI dissent in front of people, then unreviewed work, then agreement (least confident first).
export function reviewRank(review?:AIReview|null){if(!review)return 2;if(review.verdict==='disagree')return 0;if(review.verdict==='uncertain')return 1;return review.confidence==='low'?3:4;}
export function AIChip({review}:{review?:AIReview|null}){const v=verdictOf(review);return <span className={'ai-chip '+v}>{verdictLabels[v]}{review&&` · ${review.confidence}`}</span>;}

export function AIReviewPanel({review,pending,live,running,onRun,loadRun,renderTrail}:{review?:AIReview|null;pending:boolean;live:boolean;running:boolean;onRun:()=>void;loadRun:(id:string)=>Promise<ReviewRun>;renderTrail:(steps:ReviewRun['trace'])=>ReactNode}){
 const [trail,setTrail]=useState<{run:string;steps:ReviewRun['trace']}|null>(null),[loading,setLoading]=useState(false),[failed,setFailed]=useState('');
 async function openTrail(open:boolean){if(!open||!review||trail?.run===review.run_id)return;setLoading(true);setFailed('');try{const run=await loadRun(review.run_id);setTrail({run:review.run_id,steps:run.trace});}catch(e){setFailed((e as Error).message);}finally{setLoading(false);}}
 const cost=live?'Uses AI tokens.':'Demo rules; no AI tokens.';
 const button=pending&&<button className="secondary" disabled={running} onClick={onRun}>{running?<LoaderCircle size={15} className="spin"/>:review?<RefreshCw size={15}/>:<Bot size={15}/>}{running?'Reviewing…':review?'Re-run AI review':'Run AI review'}</button>;
 if(!review)return <section className="card ai-review empty-review"><div className="ai-review-head"><Bot size={18}/><h3>AI reviewer</h3><AIChip/></div><p>{pending?`An independent AI reviewer can check this proposal against the data before you decide. ${cost}`:'This proposal was decided without an AI review.'}</p>{button}</section>;
 return <section className={'card ai-review '+review.verdict}><div className="ai-review-head"><Bot size={18}/><h3>AI reviewer</h3><AIChip review={review}/></div>
  <p className="ai-summary">{review.summary}</p>
  {review.concerns.length>0&&<ul className="ai-concerns">{review.concerns.map((c,i)=><li key={i}>{c}</li>)}</ul>}
  <div className="ai-review-foot"><small>{review.mode==='demo'?'Demo rules':review.model} · {new Date(review.created_at).toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})} · Advisory only; you decide.</small>{button}</div>
  <details className="ai-trail" onToggle={e=>void openTrail((e.target as HTMLDetailsElement).open)}><summary>How the reviewer checked this</summary>{loading?<p>Loading…</p>:failed?<p>{failed}</p>:trail&&renderTrail(trail.steps)}</details>
 </section>;
}
