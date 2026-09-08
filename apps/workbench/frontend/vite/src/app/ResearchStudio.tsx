import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, Download, GitBranch, RefreshCw, Save } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Method = { method_id: string; title: string; summary: string; content: string; version: number };
type Graph = { graph_id: string; nodes: { id: string }[]; edges: { source: string; target: string; conditional: boolean }[] };
async function read<T>(path: string): Promise<T> { const r = await fetch(`/api/v1/research-studio${path}`); if (!r.ok) throw new Error("研究配置读取失败，请重试。"); return r.json(); }

export function ResearchStudio() {
  const [tab, setTab] = useState("methods"), [methods, setMethods] = useState<Method[]>([]), [selected, setSelected] = useState("");
  const [graph, setGraph] = useState<Graph | null>(null), [kind, setKind] = useState("research"), [node, setNode] = useState("");
  const [error, setError] = useState(""), [retry, setRetry] = useState(0);
  useEffect(() => { let live = true; setError(""); read<{methods:Method[]}>("").then(v => { if(live) { setMethods(v.methods); setSelected(v.methods[0]?.method_id || ""); } }).catch(e => live && setError(e.message)); return () => { live=false; }; }, [retry]);
  useEffect(() => { let live = true; setGraph(null); setNode(""); setError(""); read<Graph>(`/graph/${kind}`).then(v => { if(live) { setGraph(v); setNode(v.nodes[0]?.id || ""); } }).catch(e => live && setError(e.message)); return () => { live=false; }; }, [kind,retry]);
  const method = methods.find(m => m.method_id === selected);
  return <section className="fs-page fs-studio"><div className="fs-page-title"><div><span className="fs-kicker">RESEARCH STUDIO</span><h1>研究配置</h1><p>阅读方法，检查编排，在独立草稿中调整你的研究方式。</p></div><button className="fs-secondary" onClick={() => setRetry(r => r+1)}><RefreshCw size={15} />重新读取</button></div>
    <div className="fs-studio-tabs"><button aria-pressed={tab === "methods"} onClick={() => setTab("methods")}><BookOpen size={17} />投研 Skills</button><button aria-pressed={tab === "graph"} onClick={() => setTab("graph")}><GitBranch size={17} />Agent 图与编排</button></div>
    {error && <p role="alert">{error}</p>}
    {tab === "methods" ? <div className="fs-studio-layout"><nav aria-label="投研方法">{methods.map(m => <button key={m.method_id} aria-current={selected===m.method_id ? "page" : undefined} onClick={() => setSelected(m.method_id)}><strong>{m.title}</strong><span>{m.summary}</span></button>)}</nav><div>{method ? <><div className="fs-studio-origin">工作台方法包 · {method.method_id} · v{method.version} · 不代表所有节点均已消费</div><DraftEditor key={method.method_id} identity={`method-${method.method_id}-v${method.version}`} original={method.content} title={method.title} /></> : !error && <p role="status">正在读取方法目录…</p>}</div></div> : <>
      <div className="fs-studio-selector"><label>任务入口 <select aria-label="任务类型" value={kind} onChange={e => setKind(e.target.value)}><option value="research">完整研究 / 后续追问与修订</option><option value="review">已有报告审阅</option></select></label><span>来自原生运行服务 · 静态拓扑</span></div>
      {graph && <><p className="fs-studio-origin">此图只包含服务端公开的静态连接。动态 Command 分派、内部专家子图和实际执行顺序，请结合任务“运行与费用”查看。</p>
        <div className="fs-studio-nodes" aria-label="原生图节点">{graph.nodes.map(n => <button key={n.id} aria-pressed={n.id===node} onClick={() => setNode(n.id)}><GitBranch size={16} />{n.id}</button>)}</div>
        <div className="fs-studio-edges"><strong>{node} · 已记录连接</strong>{graph.edges.filter(e => e.source===node || e.target===node).map((e,i) => <div key={i}><code>{e.source}</code><ArrowRight size={18} /><code>{e.target}</code>{e.conditional && <small>条件连接</small>}</div>)}{!graph.edges.some(e => e.source===node || e.target===node) && <p>静态接口没有返回此节点的连接，不表示该节点不会执行。</p>}</div>
        <DraftEditor key={kind} identity={`graph-${graph.graph_id}`} original={JSON.stringify(graph,null,2)} title={`${graph.graph_id} 编排草稿`} json />
      </>}{!graph && !error && <p role="status">正在读取原生图…</p>}
    </>}
  </section>;
}

function DraftEditor({identity,original,title,json=false}: {identity:string;original:string;title:string;json?:boolean}) {
  const key=`finsight.studio-draft.${identity}`;
  const [text,setText]=useState(() => { try { return localStorage.getItem(key) ?? original; } catch { return original; } });
  const [message,setMessage]=useState(""), [editing,setEditing]=useState(false);
  const validate=() => { if(json) { try { JSON.parse(text); return true; } catch { setMessage("JSON 语法有误，请修正后保存；未更改运行服务。"); return false; } } return true; };
  return <section className="fs-draft-editor"><header><h2>{title}</h2><button onClick={() => setEditing(v=>!v)}>{editing ? "阅读预览" : "编辑草稿"}</button></header><p className="fs-studio-origin">草稿只保存在此浏览器，可导出供代码审查；不会改变当前或后续运行。{json && "语法检查不等于编排可执行验证。"}</p>
    {editing ? <textarea aria-label="配置草稿" spellCheck={false} value={text} onChange={e=>{setText(e.target.value);setMessage("有未保存修改");}} /> : json ? <pre>{text}</pre> : <div className="fs-method-prose"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{img:({alt})=><span>{alt}</span>}}>{text}</ReactMarkdown></div>}
    <footer><button onClick={()=>{if(!validate())return;try{localStorage.setItem(key,text);setMessage("草稿已保存到此浏览器，未应用到运行服务。");}catch{setMessage("保存失败，请导出草稿以保留修改。");}}}><Save size={15}/>保存草稿</button><button onClick={()=>{if(!validate())return;const url=URL.createObjectURL(new Blob([text],{type:json?"application/json":"text/markdown;charset=utf-8"}));const a=document.createElement("a");a.href=url;a.download=`${identity}.draft.${json?"json":"md"}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}><Download size={15}/>导出草稿</button><button onClick={()=>{setText(original);setMessage("已载入源版本；保存后才覆盖本地草稿。");}}>载入源版本</button></footer><p role="status">{message}</p>
  </section>;
}
