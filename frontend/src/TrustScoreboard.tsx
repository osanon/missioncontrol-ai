import { useEffect, useState } from 'react';
import { Gauge } from 'lucide-react';

type Counts = {approved:number;rejected:number;sent_back:number};
type Trust = {decisions:number;reviewed:number;followed:number;overruled:number;unsure:number;agreement_rate:number|null;by_verdict:Record<'agree'|'disagree'|'uncertain'|'none',Counts>};
type Api = <T>(path:string,init?:RequestInit)=>Promise<T>;
const verdictRows:['agree'|'disagree'|'uncertain'|'none',string][]=[['agree','AI agreed'],['disagree','AI disagreed'],['uncertain','AI unsure'],['none','Not AI-reviewed']];

// How often people follow or overrule the independent AI reviewer, from the verdict recorded with each decision.
export function TrustScoreboard({api,refreshKey}:{api:Api;refreshKey:string}){
 const [trust,setTrust]=useState<Trust|null>(null);
 useEffect(()=>{api<Trust>('/ai-trust').then(setTrust).catch(()=>setTrust(null));},[refreshKey]);
 if(!trust)return null;
 return <section className="card trust">
  <div className="trust-head"><h2><Gauge size={18}/>AI reviewer track record</h2><p>Every decision records what the independent AI reviewer had said, so you can see how often people follow it and when they overrule it.</p></div>
  {trust.reviewed===0?<p className="muted">No decisions on AI-reviewed proposals yet. Approve, reject or send back a reviewed proposal to start the record.</p>:<>
   <div className="trust-stats">
    <div><strong>{trust.agreement_rate===null?'–':`${trust.agreement_rate}%`}</strong><span>of clear AI verdicts followed</span></div>
    <div><strong>{trust.followed}</strong><span>followed the AI</span></div>
    <div><strong>{trust.overruled}</strong><span>overruled the AI</span></div>
    <div><strong>{trust.unsure}</strong><span>AI unsure, a person decided</span></div>
   </div>
   <table className="trust-table"><thead><tr><th>AI reviewer said</th><th>Approved</th><th>Rejected</th><th>Sent back</th></tr></thead>
    <tbody>{verdictRows.map(([v,label])=>{const c=trust.by_verdict[v];return <tr key={v}><td>{label}</td><td>{c.approved}</td><td>{c.rejected}</td><td>{c.sent_back}</td></tr>;})}</tbody></table>
   <small className="muted">{trust.decisions} decisions in total, {trust.reviewed} with an AI review. Followed means approved when the AI agreed, or rejected or sent back when it disagreed.</small>
  </>}
 </section>;
}