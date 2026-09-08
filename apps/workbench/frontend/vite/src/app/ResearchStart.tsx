import { ArrowRight, ChartNoAxesCombined, Compass, FileSearch, Layers, Paperclip, ShieldCheck } from "lucide-react";
import type { Session, ExecutionOptions } from "../api/reportSessions";
import { ExecutionPicker } from "./ExecutionPicker";

export function ResearchStart({ question, onQuestion, navigate, sessions, execution, onExecution }: { question: string; onQuestion: (text: string) => void; navigate: (page: string, id?: string) => void; sessions: Session[]; execution: ExecutionOptions; onExecution: (v: ExecutionOptions) => void }) {
  const ideas = [
    { title: "研究一家公司", hint: "业务、增长与竞争位置", icon: Compass, prompt: "我想研究【公司】在【期间】的增长质量，重点核对需求、竞争位置与利润兑现。" },
    { title: "解读最新财报", hint: "数字变化背后的经营原因", icon: ChartNoAxesCombined, prompt: "请分析【公司】【季度】财报，对比收入、利润与现金流，区分已披露事实和待验证解释。" },
    { title: "核查一个判断", hint: "沿来源找依据与反证", icon: ShieldCheck, prompt: "请核查这一判断：【判断内容】。找到原始来源，检查适用期间，并列出反证与限制。" },
    { title: "从资料开始", hint: "研读公告、纪要或底稿", icon: FileSearch, prompt: "请基于我提供的资料研究【问题】，先整理关键事实、矛盾和需要补充的证据。" },
  ];
  return <section className="fs-start"><div className="fs-start-inner"><span className="fs-start-emblem"><Layers size={31} strokeWidth={1.5} /></span><span className="fs-kicker">FINSIGHT · RESEARCH DESK</span><h1>这次，你想弄清楚什么？</h1><p>从一个问题出发，走到有依据、可追问的判断。</p>
    <form className="fs-start-composer" onSubmit={e => { e.preventDefault(); navigate("new"); }}><label className="fs-sr-only" htmlFor="start-question">输入研究问题</label><textarea id="start-question" rows={4} maxLength={16000} value={question} onChange={e => onQuestion(e.target.value)} placeholder="研究哪家公司、哪个期间，或哪一个值得核实的判断…" /><footer><button type="button" className="fs-start-attach" onClick={() => navigate("new")}><Paperclip size={17} />添加资料</button><span>先完善问题与资料，再启动研究</span><button className="fs-primary" disabled={!question.trim()} type="submit">准备研究 <ArrowRight size={17} /></button></footer></form>
    <ExecutionPicker value={execution} onChange={onExecution}/>
    <div className="fs-start-ideas">{ideas.map(idea => <button key={idea.title} onClick={() => { onQuestion(idea.prompt); document.getElementById("start-question")?.focus(); }}><idea.icon size={21} strokeWidth={1.6} /><strong>{idea.title}</strong><span>{idea.hint}</span></button>)}</div>
    {!!sessions.length && <div className="fs-resume-strip"><span>继续最近研究</span>{sessions.slice(0, 2).map(s => <button key={s.thread_id} onClick={() => navigate("graph", s.thread_id)}>{s.title || "未命名研究"}<ArrowRight size={14} /></button>)}<button onClick={() => navigate("all")}>查看全部</button></div>}
  </div></section>;
}
