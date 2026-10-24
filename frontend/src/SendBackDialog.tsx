import { useEffect, useRef, useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import type { Proposal } from './CorrectionReview';

export function SendBackDialog({proposal,title,onClose,onSubmit}:{proposal:Proposal;title:string;onClose:()=>void;onSubmit:(note:string)=>Promise<void>}){
 // When the AI reviewer raised problems, start the note from them; the person can edit or replace it.
 const ai=proposal.ai_review,draft=ai&&ai.verdict!=='agree'?[`AI reviewer: ${ai.summary}`,...ai.concerns].join(' ').slice(0,2000):'';
 const dialog=useRef<HTMLDialogElement>(null),[note,setNote]=useState(draft),[saving,setSaving]=useState(false),[error,setError]=useState('');
 useEffect(()=>{dialog.current?.showModal();},[]);
 async function submit(e:FormEvent){e.preventDefault();setSaving(true);setError('');try{await onSubmit(note.trim());}catch(err){setError((err as Error).message);}finally{setSaving(false);}}
 const author=proposal.created_by_kind==='agent'?'the AI agent that proposed it':'its author';
 return <dialog ref={dialog} className="correction-dialog send-back-dialog" onCancel={e=>{e.preventDefault();if(!saving)onClose();}} aria-labelledby="send-back-title"><form onSubmit={submit}>
  <div className="section-title"><h2 id="send-back-title">Send back for reevaluation</h2><button type="button" className="secondary" onClick={onClose} disabled={saving} aria-label="Close"><X size={16}/></button></div>
  <p><b>{title}</b> · {proposal.context?.client_name??`Record #${proposal.record_id}`}</p>
  <p>Nothing changes in the source record. The proposal returns to {author} with your note, and a revised proposal comes back to the review queue.</p>
  {draft&&<p className="muted">Started from the AI reviewer's concerns. Edit it to say what you want reevaluated.</p>}
  {error&&<div role="alert" className="alert error">{error}</div>}
  <label>What should be reevaluated?<textarea required minLength={10} maxLength={2000} rows={4} value={note} onChange={e=>setNote(e.target.value)} placeholder="For example: this looks like an annual salary, not an hourly wage. Check the payroll export."/></label>
  <div className="decision-actions"><button type="button" className="secondary" onClick={onClose} disabled={saving}>Cancel</button><button className="primary" disabled={saving||note.trim().length<10}>{saving?'Sending…':'Send back'}</button></div>
 </form></dialog>;
}
