import {useRef,useState} from 'react';

import {BoundCitationMarkdown} from './BoundCitationMarkdown';
import type {Citation} from '../api/reportSessions';

export type SelectionTarget={version:string;offset:number;quote:string};
export type ReviewResult={citations?:Record<string,Citation>;reviewer:string;version:string;quote:string;question:string;opinion:string;reason:string;edits:{before:string;after:string}[]};

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

export function AnswerReviewResult({result,onCitation}:{result:ReviewResult;onCitation:(key:string,c:Citation)=>void}){
  return <section aria-label="选段核查与作者修改"><h4>核查与修改</h4><blockquote>{result.quote||'针对这版回答的问题'}</blockquote>{result.question&&<p>{result.question}</p>}
    <details><summary>独立核查意见 · {result.reviewer}</summary><BoundCitationMarkdown text={result.opinion} citations={result.citations} onCitation={onCitation}/></details>
    <p>{result.reason}</p>{result.edits.length?<details open><summary>与所选原稿相比修改了 {result.edits.length} 处</summary>
      {result.edits.map((edit,i)=><div key={i}><del>{edit.before}</del><p><ins>{edit.after}</ins></p></div>)}
      <small>其余原文沿用所选版本。</small></details>:<p>作者保留了原稿。</p>}</section>;
}
