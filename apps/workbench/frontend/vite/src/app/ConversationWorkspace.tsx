import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUp, Layers, MessageSquare, Paperclip, Plus, Square, X } from "lucide-react";
import { ContextUsage } from "./ContextUsage";
import type { Event, Session } from "../api/reportSessions";
import "./research-session.css";
import "./workspace-design.css";

type Conversation = { thread_id: string; title: string; status: string; messages: {id: string; role: string; content: string}[]; events: Event[]; runs: NonNullable<Session["runs"]>; permissions_notice: string; attachments?: {document_id:string;name:string}[] };
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1/conversations${path}`, { method: body === undefined ? "GET" : "POST", headers: {"Content-Type":"application/json","X-Workbench-Request":"1"}, ...(body === undefined ? {} : {body:JSON.stringify(body)}) });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : `请求未完成 (${response.status})`);
  return result;
}

export default function ConversationWorkspace() {
  const [params, setParams] = useSearchParams(); const id = params.get("thread") || "";
  const [threads, setThreads] = useState<Conversation[]>([]), [session, setSession] = useState<Conversation | null>(null);
  const [text, setText] = useState(""), [error, setError] = useState(""), [sending, setSending] = useState(false);
  const [model, setModel] = useState("deepseek-v4-flash"), [permission, setPermission] = useState("request_standard");
  const [live, setLive] = useState<Event[]>([]); const current = useRef(id); current.current = id;
  const [navOpen, setNavOpen] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const uploadInput = useRef<HTMLInputElement>(null);
  const [draftMessages, setDraftMessages] = useState<Record<string, string>>({});
  const reading = useRef<HTMLDivElement>(null), followBottom = useRef(true);
  useEffect(() => { followBottom.current = true; }, [id]);
  useEffect(() => { if(followBottom.current && reading.current) reading.current.scrollTop = reading.current.scrollHeight; }, [session?.messages, draftMessages]);
  const refresh = async () => { const selected = id; const value = await request<Conversation>(`/${selected}`); if (current.current === selected) setSession(value); };
  useEffect(() => { request<Conversation[]>("").then(setThreads).catch(e => setError(e.message)); }, [id, sending]);
  useEffect(() => { setSession(null); setLive([]); setError(""); if (!id) return; let cancelled = false;
    const load = async () => { try { const value = await request<Conversation>(`/${id}`); if (!cancelled) setSession(value); } catch(e) { if (!cancelled) setError((e as Error).message); } };
    void load(); const timer = window.setInterval(load, 2500); return () => { cancelled = true; clearInterval(timer); };
  }, [id]);
  const active = session?.runs.find(r => ["running","pending"].includes(r.status));
  useEffect(() => { setDraftMessages({}); if (!id || !active) return; const selected = id; const stream = new EventSource(`/api/v1/conversations/${id}/runs/${active.run_id}/stream`); const seen = new Set<string>();
    stream.addEventListener("assistant_delta", event => { const message = event as MessageEvent; if (current.current !== selected || (message.lastEventId && seen.has(message.lastEventId))) return; if(message.lastEventId) seen.add(message.lastEventId); const value = JSON.parse(message.data) as {id:string;text:string}; setDraftMessages(rows => ({...rows, [value.id]:(rows[value.id] || "") + value.text})); });
    stream.addEventListener("custom", event => { const message = event as MessageEvent; if (current.current !== selected || seen.has(message.lastEventId)) return; seen.add(message.lastEventId); const value = JSON.parse(message.data) as Event; setLive(rows => [...rows, value]); });
    return () => stream.close();
  }, [id, active?.run_id]);
  const send = async () => { if (!text.trim() || sending || active) return; setSending(true); setError("");
    try {
      let target = id;
      if(files.length && !target) { target = (await request<{thread_id:string}>("/drafts", {title:text.slice(0,80)})).thread_id; setParams({thread:target}); }
      for(const file of files) {
        const response = await fetch(`/api/v1/conversations/${target}/attachments`, {method:"POST",headers:{"X-Workbench-Request":"1","X-Filename":encodeURIComponent(file.name)},body:file});
        const result = await response.json(); if(!response.ok) throw new Error(typeof result.detail==="string" ? result.detail : "资料上传失败");
        setFiles(pending=>pending.filter(f=>f!==file));
      }
      const result = await request<{thread_id:string}>(target ? `/${target}/messages` : "", {message:text + (files.length ? `\n\n本轮附带资料：${files.map(f=>f.name).join("、")}。请通过对话资料工具读取。` : ""), model, permission_mode:permission}); setText(""); setLive([]); if (!id) setParams({thread:result.thread_id}); else await refresh();
    }
    catch(e) { setError((e as Error).message); } finally { setSending(false); }
  };
  return <div className={`rs-shell fs-workspace fs-assistant-shell ${navOpen ? "nav-open" : ""}`}><aside className="fs-assistant-nav"><a className="fs-brand" href="/workspace"><Layers size={24}/><strong>FinSight</strong></a><button className="fs-primary" disabled={sending} onClick={() => { setParams({}); setText(""); setFiles([]); setNavOpen(false); }}><Plus size={17}/>新对话</button><a href="/workspace">研究工作台 →</a><nav aria-label="已保存对话">{threads.map(t => <button key={t.thread_id} aria-current={id===t.thread_id ? "page":undefined} disabled={sending} onClick={() => {setParams({thread:t.thread_id}); setFiles([]); setNavOpen(false);}}><MessageSquare size={15}/><span>{t.title || "未命名对话"}</span></button>)}</nav></aside>
    <main className="fs-assistant-main"><header><button className="fs-assistant-menu" aria-expanded={navOpen} onClick={()=>setNavOpen(!navOpen)}>对话列表</button><div><small>FINSIGHT · ASSISTANT</small><h1>{session?.title || "从一个问题开始"}</h1></div><a href="/workspace">返回研究</a></header>
      <div className="fs-assistant-messages" aria-live="polite" ref={reading} onScroll={e=>{const el=e.currentTarget;followBottom.current=el.scrollHeight-el.scrollTop-el.clientHeight<120;}}>{!id && <p>日常问答、资料阅读与数据核对，可以在同一对话中继续。复杂投研仍可从研究工作台启动。</p>}
        {session?.messages.map((message, i) => <article className={`fs-assistant-message ${message.role}`} key={message.id || i}><small>{message.role==="user" ? "你" : "FinSight"}</small><ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown></article>)}
        {active && Object.entries(draftMessages).filter(([messageId]) => !session?.messages.some(m=>m.id===messageId)).map(([messageId,content])=><article className="fs-assistant-message assistant" key={messageId}><small>FinSight · 正在输出</small><ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown></article>)}
        {active && <section className="fs-assistant-live" aria-label="实时助理活动"><strong>正在处理这一轮</strong>{live.filter(e => e.kind==="stage" && e.objective).map((e,i) => <ReactMarkdown key={i} remarkPlugins={[remarkGfm]}>{e.objective}</ReactMarkdown>)}<details><summary>模型与工具活动</summary>{live.filter(e=>e.kind!=="stage").map((e,i)=><p key={i}>{e.tool || e.model || "助理"} · {e.event==="started" ? "已发起" : e.status || "已返回"}</p>)}</details></section>}
        {session?.status==="error" && <p role="alert">本轮执行失败，已生成的输出和记录保留。请结合活动信息检查原因，修改后再继续。</p>}
        {!!session?.events.length && !active && <details><summary>本对话已保存活动</summary>{session.events.map((e,i)=><div key={i}>{e.objective ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{e.objective}</ReactMarkdown> : <p>{e.tool || e.model || "助理"} · {e.event==="started" ? "已发起" : e.status || "已返回"}</p>}</div>)}</details>}
      </div>
      <footer className="fs-assistant-compose">{session?.runs[0] && <ContextUsage usage={session.runs[0].context_usage} nodeName={() => "当前助理"}/>}
        {error && <p role="alert">{error}</p>}
        {!!session?.attachments?.length && <details><summary>本对话资料 · {session.attachments.length} 份</summary>{session.attachments.map(f=><p key={f.document_id}>{f.name}</p>)}</details>}
        {!!files.length && <div>{files.map((file,i)=><button key={i} disabled={sending} onClick={()=>setFiles(rows=>rows.filter(f=>f!==file))}>{file.name} <X size={12}/></button>)}</div>}
        <input ref={uploadInput} type="file" multiple hidden aria-label="添加对话资料" disabled={sending || !!active} accept=".pdf,.docx,.md,.txt,.html,.htm,.png,.jpg,.jpeg,.webp" onChange={e=>{setFiles(rows=>[...rows,...Array.from(e.target.files || [])]);e.target.value="";}}/>
        <button disabled={sending || !!active} onClick={()=>uploadInput.current?.click()}><Paperclip size={16}/>添加资料 · 仅用于本对话</button>
        <label className="fs-sr-only" htmlFor="assistant-message">发送消息</label><textarea id="assistant-message" value={text} onChange={e=>setText(e.target.value)} rows={3} maxLength={15500} placeholder="输入问题，或继续修改刚才的回答…"/>
        <div className="fs-assistant-controls"><label>模型 <select value={model} onChange={e=>setModel(e.target.value)} disabled={sending || !!active}><option value="deepseek-v4-flash">DeepSeek V4 Flash</option><option value="deepseek-v4-pro">DeepSeek V4 Pro</option></select></label><label>权限 <select value={permission} onChange={e=>setPermission(e.target.value)} disabled={sending || !!active}><option value="request_standard">请求标准</option><option value="approve_for_me">代我批准</option><option value="full_access">完全访问权限</option></select></label>{active ? <button onClick={async()=>{try {await request(`/${id}/stop`,{}); await refresh();} catch(e){setError((e as Error).message);}}}><Square size={16}/>停止</button> : <button className="fs-primary" disabled={!text.trim() || sending} onClick={send}><ArrowUp size={17}/>{sending ? "发送中" : "发送"}</button>}</div>
        <small>{session?.permissions_notice || "当前工具范围：对话资料读取与精确计算。选择权限模式不会自动开放用户文件、终端或服务器访问。"}</small>
      </footer>
    </main></div>;
}
