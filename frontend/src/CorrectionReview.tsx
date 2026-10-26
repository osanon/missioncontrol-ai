import { useEffect, useRef, useState, type FormEvent } from 'react';

type Context = {client_id:number|null;client_name:string|null;client_identifier:string|null;program:string|null};
export type Issue = {key:string;kind:string;title:string;reason:string;severity:string;table:string;record_id:number;record:Record<string,unknown>;proposal_status:string|null;review_required:boolean;source_sql:string;context?:Context};
export type Proposal = {id:string;revision_requested?:boolean;revision_feedback?:string[];created_at?:string;decided_at?:string|null;table_name:string;record_id:number;before:Record<string,unknown>;after:Record<string,unknown>;reason:string;status:string;issue_key:string;decided_by:string|null;context?:Context;current_record?:Record<string,unknown>;snapshot_complete?:boolean;proposal_type?:string;base_issue_key?:string};
export type CorrectionRequest = {issue_key:string;resolution:string;value:string;evidence:string;replaces_id?:string};
const labels:Record<string,string> = {status:'Enrollment status',start_date:'Start date',end_date:'Exit / end date',hourly_wage:'Hourly wage',review_required:'Follow-up required',units:'Service units',service_date:'Service date',full_name:'Client name',birth_date:'Date of birth',client_id:'Client ID',program_id:'Program ID'};
const fields:Record<string,string[]> = {missing_exit:['status','start_date','end_date'],invalid_dates:['status','start_date','end_date'],wage_outlier:['hourly_wage'],negative_units:['service_date','units'],duplicate:['full_name','birth_date']};
function valueText(key:string,value:unknown){
 if(value===null||value===undefined||value==='')return 'Missing';
 if(typeof value==='boolean')return value?'Yes':'No';
 if(key==='hourly_wage'&&typeof value==='number')return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value);
 if(key==='status')return String(value).replace(/^./,x=>x.toUpperCase());
 return String(value);
}
function ContextLine({context,recordId}:{context?:Context;recordId:number}){
 return <p className="record-context">{context?.client_name??'Client'}{context?.client_identifier?` · ${context.client_identifier}`:context?.client_id?` · Client #${context.client_id}`:''}{context?.program?` · ${context.program}`:''} · Record #{recordId}</p>;
}
export function Comparison({before,after,kind,preview=false,status='pending'}:{before:Record<string,unknown>;after:Record<string,unknown>;kind:string;preview?:boolean;status?:string}){
 const keys=[...new Set([...(fields[kind]??[]),...Object.keys(after)])];
 return <div className="comparison-scroll" tabIndex={0} role="region" aria-label="Field comparison; scroll horizontally on small screens"><table className="field-comparison"><thead><tr><th>Field</th><th>{preview?'Current record':'At proposal creation'}</th><th>{preview?'Proposed result':status==='applied'?'Applied result':status==='pending'?'After approval':'Originally proposed'}</th></tr></thead><tbody>{keys.map(key=>{
 const has=Object.prototype.hasOwnProperty.call(after,key), next=has?after[key]:before[key], changed=has&&next!==before[key];
 return <tr key={key} className={changed?'field-changed':''}><th scope="row">{key==='end_date'&&kind.includes('exit')?'Exit date':labels[key]??key.replaceAll('_',' ')}</th><td>{valueText(key,before[key])}</td><td>{valueText(key,next)}<small>{changed?(preview||status==='pending'?'Will change':status==='applied'?'Applied':'Not applied'):'Unchanged'}</small></td></tr>;
 })}</tbody></table></div>;
}
export function ProposalCard({proposal:p,issue,working,reviewer,onDecide,onResolve}:{proposal:Proposal;issue?:Issue;working:boolean;reviewer:boolean;onDecide:(p:Proposal,d:'approve'|'reject')=>void;onResolve:(i:Issue,p:Proposal)=>void}){
 const followup=p.proposal_type==='follow_up'||Object.keys(p.after).every(k=>k==='review_required');
 const kind=(p.base_issue_key??p.issue_key).split(':')[0];
 return <section className="card padded proposal-card"><div className="section-title"><div><span className={'pill '+(p.status==='applied'?'success':'')}>{p.status}</span><h3>{followup?'Needs information / follow-up':'Proposed correction'}</h3></div></div>
 <ContextLine context={p.context} recordId={p.record_id}/><p className="proposal-reason">{p.reason}</p>
 {followup&&<p className="followup-explanation">This action only marks the record for follow-up. It does not supply a missing date, change enrollment status, or resolve the underlying finding.</p>}
 {p.snapshot_complete?<Comparison before={p.before} after={p.after} kind={kind} status={p.status}/>:<><p className="legacy-note">This older proposal saved only its changed fields. The comparison below shows those saved values.</p><Comparison before={p.before} after={p.after} kind="legacy" status={p.status}/>{p.status==='pending'&&p.current_record&&<details className="current-details" open><summary>Current source record (read now, not the historical snapshot)</summary><Comparison before={p.current_record} after={{}} kind={kind} preview/></details>}</>}
 {p.status==='pending'?<div className="decision-actions correction-actions"><span>{!reviewer?'Add your reviewer token to approve or reject.':followup?'Approval adds a follow-up flag only.':'Only fields marked “Will change” are applied.'}</span>{issue&&<button className="secondary" disabled={working} onClick={()=>onResolve(issue,p)}>{kind==='duplicate'?'Compare profiles':followup?'Choose correction':'Replace proposal'}</button>}<button className="secondary" disabled={working||!reviewer} onClick={()=>onDecide(p,'reject')}>Reject</button><button className="primary" disabled={working||!reviewer||p.revision_requested} onClick={()=>onDecide(p,'approve')}>{followup?'Mark for follow-up':'Approve & apply'}</button></div>:<small>{p.status==='superseded'?'Replaced by a newer proposal; original evidence retained.':`Decision recorded for ${p.decided_by}.`}</small>}
 </section>;
}
const options:Record<string,[string,string][]> = {
 missing_exit:[['set_exit_date','Enter confirmed exit date'],['reactivate_enrollment','Reactivate this enrollment']],
 invalid_dates:[['set_exit_date','Enter corrected exit date']],
 wage_outlier:[['correct_wage','Enter confirmed hourly wage'],['clear_wage','Clear unverified wage and flag for follow-up']],
 negative_units:[['correct_units','Enter confirmed service units']],duplicate:[]
};
export function CorrectionForm({issue,previous,onClose,onSave}:{issue:Issue;previous?:Proposal;onClose:()=>void;onSave:(data:CorrectionRequest)=>Promise<void>}){
 const dialog=useRef<HTMLDialogElement>(null);
 const [resolution,setResolution]=useState(options[issue.kind]?.[0]?.[0]??'follow_up');
 const [value,setValue]=useState(''),[evidence,setEvidence]=useState(''),[saving,setSaving]=useState(false),[error,setError]=useState('');
 useEffect(()=>{const d=dialog.current;d?.showModal();return()=>d?.close();},[]);
 const dateInput=resolution==='set_exit_date',numberInput=['correct_wage','correct_units'].includes(resolution);
 const confirmRequired=!['follow_up','clear_wage'].includes(resolution);
 const after:Record<string,unknown>=resolution==='follow_up'?{review_required:true}:resolution==='reactivate_enrollment'?{status:'active',end_date:null}:resolution==='set_exit_date'?{status:'exited',end_date:value||null}:resolution==='clear_wage'?{hourly_wage:null,review_required:true}:resolution==='correct_wage'?{hourly_wage:value===''?null:Number(value)}:{units:value===''?null:Number(value)};
 async function submit(e:FormEvent){e.preventDefault();setSaving(true);setError('');try{await onSave({issue_key:issue.key,resolution,value:dateInput||numberInput?value:'',evidence,replaces_id:previous?.id});}catch(e){setError((e as Error).message);}finally{setSaving(false);}}
 return <dialog ref={dialog} className="correction-dialog" onCancel={e=>{e.preventDefault();if(!saving)onClose();}} aria-labelledby="correction-title"><form onSubmit={submit}>
 <div className="section-title"><h2 id="correction-title">{previous?'Replace pending proposal':'Choose a resolution'}</h2><button type="button" className="secondary" onClick={onClose} disabled={saving} aria-label="Close correction form">Close</button></div>
 <h3>{issue.title}</h3><ContextLine context={issue.context} recordId={issue.record_id}/><p>{issue.reason}</p>
 {previous&&<p className="followup-explanation">Saving creates a new pending proposal and marks the previous one as superseded. Both remain in decision history. No source data changes until approval.</p>}
 {error&&<p className="alert error" role="alert">{error}</p>}
 <label>Resolution<select aria-label="Resolution" value={resolution} onChange={e=>{setResolution(e.target.value);setValue('');setError('');}}>{(options[issue.kind]??[]).map(([v,label])=><option key={v} value={v}>{label}</option>)}<option value="follow_up" disabled={issue.review_required}>Needs information / follow-up{issue.review_required?' (already flagged)':''}</option></select></label>
 {dateInput&&<label>Confirmed exit date<input type="date" required value={value} min={String(issue.record.start_date??'')} max={new Date().toISOString().slice(0,10)} onChange={e=>setValue(e.target.value)}/></label>}
 {numberInput&&<label>{resolution==='correct_wage'?'Confirmed hourly wage':'Confirmed service units'}<input type="number" required min={resolution==='correct_wage'?1:0} max={resolution==='correct_wage'?200:undefined} step="any" value={value} onChange={e=>setValue(e.target.value)}/></label>}
 <label>{confirmRequired?'Evidence / confirmation (required)':'Follow-up note (optional)'}<textarea required={confirmRequired} minLength={confirmRequired?10:undefined} maxLength={2000} rows={3} value={evidence} onChange={e=>setEvidence(e.target.value)} placeholder="Describe the source or program confirmation supporting this action."/></label>
 <p className="footnote">Dates and status changes need confirmation. A missing date does not establish active status, and a last service date is not an exit date. Existing follow-up flags remain until separately reviewed.</p>
 <Comparison before={issue.record} after={after} kind={issue.kind} preview/>
 <div className="decision-actions"><span>Save for review; nothing is applied yet.</span><button type="submit" className="primary" disabled={saving||(resolution==='follow_up'&&issue.review_required)}>{saving?'Saving…':previous?'Replace proposal':'Create proposal'}</button></div>
 </form></dialog>;
}
