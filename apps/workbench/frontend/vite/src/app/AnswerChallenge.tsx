import {useRef,useState} from 'react';

import {BoundCitationMarkdown} from './BoundCitationMarkdown';
import './answer-review.css';
import type {Citation} from '../api/reportSessions';

export type SelectionTarget={version:string;offset:number;quote:string};
export type ReviewResult={citations?:Record<string,Citation>;reviewer:string;version:string;quote:string;question:string;opinion:string;reason?:string;edits?:{before:string;after:string}[];artifact?:string;reviewed_report_version?:number;revised_report_version?:number;author_response?:string};

export function SelectAnswerPassage({text,version,onChoose}:{text:string;version:string;onChoose:(s:SelectionTarget)=>void}){
  const [open,setOpen]=useState(false),[error,setError]=useState('');
  const field=useRef<HTMLTextAreaElement>(null);
  function choose(start:number,end:number){
    const quote=text.slice(start,end);
    if(!quote.trim()||Array.from(quote).length>4000){setError('请选中 1 至 4000 字的原文。');return;}
    onChoose({version,offset:Array.from(text.slice(0,start)).length,quote});setOpen(false);setError('');
  }
  return <section><button onMouseDown={e=>e.preventDefault()} onClick={e=>{
    const sel=window.getSelection(),quote=sel?.toString()||'';
    if(quote&&e.currentTarget.closest('.org-finding')?.contains(sel?.anchorNode||null)&&text.indexOf(quote)>=0&&text.indexOf(quote)===text.lastIndexOf(quote))
      choose(text.indexOf(quote),text.indexOf(quote)+quote.length);
    else setOpen(!open);
  }}>核查这份回答中的选段</button>{open&&<div>
    <label>在当前版本中选中原句<textarea aria-label="选择待核查原文" ref={field} readOnly value={text} rows={8}/></label>
    <button onClick={()=>{const t=field.current;if(t)choose(t.selectionStart,t.selectionEnd);}}>使用选中原文</button>
    <button onClick={()=>{onChoose({version,quote:'',offset:0});setOpen(false);setError('');}}>直接就这版回答提出核查问题</button>
    {error&&<p role="alert">{error}</p>}</div>}</section>;
}

export function AnswerReviewResult({result,onCitation,before,after}:{result:ReviewResult;before?:Record<string,Citation>;after?:Record<string,Citation>;onCitation:(key:string,c:Citation)=>void}){
  const report=result.artifact==='report';
  const edits=Array.isArray(result.edits)?result.edits:undefined;
  const response=report?result.author_response:result.reason;
  return <section className="answer-review" aria-label={report?'报告复核与作者修改':'选段核查与作者修改'}><h4>核查与修改</h4><blockquote>{result.quote||(report?'针对整份报告的复核':'针对这版回答的问题')}</blockquote>{result.question&&<p>{result.question}</p>}
    {report&&result.reviewed_report_version!=null&&<p>复核稿：第 {result.reviewed_report_version} 版{result.revised_report_version!=null&&<>；修订稿：第 {result.revised_report_version} 版</>}。</p>}
    <details><summary>独立核查意见 · {result.reviewer}</summary><BoundCitationMarkdown text={result.opinion} citations={result.citations} onCitation={onCitation}/></details>
    {response&&<><h5>原作者的处理说明</h5><BoundCitationMarkdown text={response} citations={after} onCitation={onCitation}/></>}{edits?.length?<details open><summary>与所选原稿相比修改了 {edits.length} 处</summary>
      {edits.map((edit,i)=><section className="answer-edit" key={i}><h5>第 {i+1} 处修改</h5><div className="answer-edit-before"><small>原文</small><BoundCitationMarkdown text={edit.before} citations={before} onCitation={onCitation}/></div><div className="answer-edit-after"><small>修订后</small><BoundCitationMarkdown text={edit.after} citations={after} onCitation={onCitation}/></div></section>)}
      <small>其余原文沿用所选版本。</small></details>:<p>{report||!edits?'本次记录未附逐句修改对照，请结合复核意见、作者说明与报告版本阅读。':'作者保留了原稿。'}</p>}</section>;
}
