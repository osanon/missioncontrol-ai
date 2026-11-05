import { Fragment, type ReactNode } from 'react';

// A small Markdown renderer for AI answers: headings, bold, inline code, lists and tables.
// It only builds React elements, never raw HTML, so model output cannot inject markup or links.
function inline(text:string):ReactNode[]{
 return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part,i)=>
  part.length>4&&part.startsWith('**')&&part.endsWith('**')?<strong key={i}>{part.slice(2,-2)}</strong>
  :part.length>2&&part.startsWith('`')&&part.endsWith('`')?<code key={i}>{part.slice(1,-1)}</code>
  :<Fragment key={i}>{part}</Fragment>);
}
const cells=(line:string)=>line.trim().replace(/^\||\|$/g,'').split('|').map(c=>c.trim());
const isRule=(line:string|undefined)=>!!line&&/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line);
const HEADING=/^(#{1,4})\s+(.*)$/,BULLET=/^\s*[-*•]\s+/,NUMBERED=/^\s*\d+[.)]\s+/;
const startsTable=(lines:string[],i:number)=>lines[i].trim().startsWith('|')&&isRule(lines[i+1]);

export function Markdown({text}:{text:string}){
 const lines=text.replace(/\r\n/g,'\n').split('\n'),out:ReactNode[]=[];
 let i=0;
 while(i<lines.length){
  const line=lines[i],heading=HEADING.exec(line);
  if(!line.trim()){i++;continue;}
  if(heading){const H=heading[1].length<=2?'h3':'h4';out.push(<H key={i}>{inline(heading[2])}</H>);i++;continue;}
  if(startsTable(lines,i)){
   const head=cells(line),rows:string[][]=[];i+=2;
   while(i<lines.length&&lines[i].trim().startsWith('|')){rows.push(cells(lines[i]));i++;}
   out.push(<div className="md-table" key={i}><table><thead><tr>{head.map((c,j)=><th key={j}>{inline(c)}</th>)}</tr></thead>
    <tbody>{rows.map((r,k)=><tr key={k}>{r.map((c,j)=><td key={j}>{inline(c)}</td>)}</tr>)}</tbody></table></div>);
   continue;
  }
  if(BULLET.test(line)||NUMBERED.test(line)){
   const ordered=!BULLET.test(line),marker=ordered?NUMBERED:BULLET,items:string[]=[];
   while(i<lines.length&&marker.test(lines[i])){items.push(lines[i].replace(marker,''));i++;}
   const List=ordered?'ol':'ul';
   out.push(<List key={i}>{items.map((t,k)=><li key={k}>{inline(t)}</li>)}</List>);
   continue;
  }
  const para=[line];i++;
  while(i<lines.length&&lines[i].trim()&&!HEADING.test(lines[i])&&!BULLET.test(lines[i])&&!NUMBERED.test(lines[i])&&!startsTable(lines,i)){para.push(lines[i]);i++;}
  out.push(<p key={i}>{para.map((t,k)=><Fragment key={k}>{k>0&&<br/>}{inline(t)}</Fragment>)}</p>);
 }
 return <>{out}</>;
}