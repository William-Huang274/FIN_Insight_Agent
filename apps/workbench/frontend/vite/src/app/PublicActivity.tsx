import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/** Fold raw routing explanations, never rewrite financial quarter names or source prose. */
export function PublicActivity({text}:{text:string}) {
  const body=<ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{a:({children})=><span>{children}</span>,img:()=>null}}>{text}</ReactMarkdown>;
  const internal=/\bQ[1-9]_[A-Z_]+\b|\bQ[1-9]\s*[-–—]\s*Q[1-9]\b/.test(text);
  return internal?<div><p>已记录本阶段的研究方案与范围说明。需要调整时，可直接编辑“研究设置与记忆”中的要求。</p><details><summary>查看原始调度说明 · 含内部标识</summary>{body}</details></div>:body;
}
