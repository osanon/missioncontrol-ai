import { useState } from 'react';
import { CircleAlert, Download, FileText, LoaderCircle, ShieldCheck } from 'lucide-react';
import { Markdown } from './Markdown';

type Report = {run_id:string;mode:string;start:string;end:string;markdown:string;check:{unverified_numbers:string[]}};
type Api = <T>(path:string,init?:RequestInit)=>Promise<T>;

// Drafts a funder report for the selected period: verified figures, data-quality notes and a narrative whose numbers are checked.
export function FunderReport({api,start,end,live}:{api:Api;start:string;end:string;live:boolean}){
 const [report,setReport]=useState<Report|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function draft(){
  setBusy(true);setError('');
  try{setReport(await api<Report>('/funder-report',{method:'POST',body:JSON.stringify({start,end})}));}
  catch(e){setError(e instanceof Error?e.message:'The report could not be drafted.');}
  finally{setBusy(false);}
 }
 function download(r:Report){
  const url=URL.createObjectURL(new Blob([r.markdown],{type:'text/markdown'})),a=document.createElement('a');
  a.href=url;a.download=`funder-report-${r.start}-to-${r.end}.md`;a.click();URL.revokeObjectURL(url);
 }
 const flagged=report?.check.unverified_numbers??[];
 return <section className="card funder-report">
  <div className="funder-report-head">
   <div><h2><FileText size={18}/>Funder report</h2><p>Draft a short update for funders for {start} to {end}. The figures come from the verified metrics, every number in the text is checked against them, and a person reviews the draft before sending.</p></div>
   <button className="primary" disabled={busy} onClick={()=>void draft()}>{busy?<LoaderCircle size={15} className="spin"/>:<FileText size={15}/>}{busy?'Drafting…':report?'Draft again':'Draft funder report'}</button>
  </div>
  <small className="funder-report-mode">{live?'Live AI writes the narrative and uses AI tokens.':'Guided demo: a template writes the narrative, no AI cost.'}</small>
  {error&&<p className="funder-report-error">{error}</p>}
  {report&&<>
   <div className={'funder-report-check '+(flagged.length?'warn':'ok')}>{flagged.length
    ?<><CircleAlert size={16}/><span><b>Check before sending:</b> these numbers are not verified figures: {flagged.join(', ')}.</span></>
    :<><ShieldCheck size={16}/><span><b>Number check passed:</b> every number in the text matches the verified figures.</span></>}
    <button className="secondary" onClick={()=>download(report)}><Download size={14}/>Download (.md)</button></div>
   <div className="answer funder-report-preview"><Markdown text={report.markdown}/></div>
  </>}
 </section>;
}