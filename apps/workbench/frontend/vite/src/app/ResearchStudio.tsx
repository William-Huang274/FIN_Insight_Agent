import { useEffect, useState } from "react";
import { ArrowRight, BookOpen, CheckCircle2, GitBranch, Save } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Configuration = {schema_version:1;title:string;methods:Record<string,string>;bindings:Record<string,string>;max_parallel_tasks:number;review_order:string};
type Version = {assistant_id:string;title:string;created_at:string;digest:string};
type Catalog = {default:Configuration;roles:Record<string,string>;versions:Version[]};
type Task = {thread_id:string;title:string;status:string;studio_assistant_id?:string};
const methodTitles:Record<string,string>={lead:"研究任务规划",finance:"增长、盈利与现金兑现",industry_product:"行业与产品传导",counter:"反证与替代解释",writer:"综合研究与可读交付",verifier:"研究与报告复核"};
async function api<T>(path:string,body?:unknown):Promise<T>{
  const r=await fetch(`/api/v1/${path}`,body===undefined?undefined:{method:"POST",headers:{"Content-Type":"application/json","X-Workbench-Request":"1"},body:JSON.stringify(body)});
  const value=await r.json(); if(!r.ok) throw new Error(typeof value.detail==="string"?value.detail:"配置未保存：请检查内容完整性及长度。每项 Skill 最多比原方法增加 2000 字符。"); return value;
}

export function ResearchStudio(){
  const [catalog,setCatalog]=useState<Catalog|null>(null),[config,setConfig]=useState<Configuration|null>(null);
  const [tab,setTab]=useState("graph"),[node,setNode]=useState("writer"),[method,setMethod]=useState("writer");
  const [version,setVersion]=useState(""),[dirty,setDirty]=useState(false),[editing,setEditing]=useState(true);
  const [tasks,setTasks]=useState<Task[]>([]),[task,setTask]=useState(""),[busy,setBusy]=useState(false),[notice,setNotice]=useState(""),[error,setError]=useState("");
  const reload=async()=>{const c=await api<Catalog>("research-studio/configurations");setCatalog(c);return c;};
  useEffect(()=>{let live=true;Promise.all([api<Catalog>("research-studio/configurations"),api<Task[]>("research-sessions")]).then(([c,t])=>{if(live){setCatalog(c);setConfig(c.default);setTasks(t);}}).catch(e=>live&&setError(e.message));return()=>{live=false;};},[]);
  const change=(next:Partial<Configuration>)=>{setConfig(c=>c?{...c,...next}:c);setDirty(true);setNotice("有未保存修改；保存后再应用到任务。");};
  const perform=async(fn:()=>Promise<void>)=>{setBusy(true);setError("");try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  const load=async(id:string)=>perform(async()=>{const next=id?await api<{configuration:Configuration}>(`research-studio/configurations/${id}`):{configuration:catalog!.default};setConfig(next.configuration);setVersion(id);setDirty(false);setNotice(id?"已载入运行服务中的保存版本。":"已载入标准配置。");});
  if(!config||!catalog)return <section className="fs-page"><h1>研究配置</h1>{error?<p role="alert">{error}<button onClick={()=>location.reload()}>重新加载</button></p>:<p role="status">正在读取运行服务中的配置…</p>}</section>;
  const groups=[["lead","specialist"],config.review_order==="verifier_first"?["verifier","counter"]:["counter","verifier"],["repair","synthesis","research_verifier"],["writer","report_verifier","quick_writer"]];
  return <section className="fs-page fs-studio">
    <div className="fs-page-title"><div><span className="fs-kicker">RESEARCH STUDIO</span><h1>定义你的研究方式</h1><p>编辑方法、选择角色 Skill 与执行顺序，保存到运行服务后应用到任务。</p></div><span className="fs-studio-badge"><CheckCircle2 size={16}/>原生运行配置</span></div>
    <div className="fs-studio-versionbar"><label>配置名称<input aria-label="配置名称" maxLength={80} value={config.title} onChange={e=>change({title:e.target.value})}/></label><label>载入保存版本<select aria-label="保存版本" disabled={busy} value={version} onChange={e=>void load(e.target.value)}><option value="">标准配置</option>{catalog.versions.map(v=><option key={v.assistant_id} value={v.assistant_id}>{v.title} · {new Date(v.created_at).toLocaleString("zh-CN")}</option>)}</select></label><button className="fs-primary" disabled={busy||!config.title.trim()} onClick={()=>void perform(async()=>{const saved=await api<{assistant_id:string}>("research-studio/configurations",config);await reload();setVersion(saved.assistant_id);setDirty(false);setNotice("新版本已保存到运行服务。选择任务并应用即可生效。");})}><Save size={16}/>保存为新版本</button></div>
    <div className="fs-studio-tabs"><button aria-pressed={tab==="graph"} onClick={()=>setTab("graph")}><GitBranch size={17}/>Agent 图与编排</button><button aria-pressed={tab==="methods"} onClick={()=>setTab("methods")}><BookOpen size={17}/>投研 Skills</button></div>
    {tab==="graph"?<><div className="fs-studio-controls"><label>专家与责任修订并行数<select aria-label="专家并行数" value={config.max_parallel_tasks} onChange={e=>change({max_parallel_tasks:Number(e.target.value)})}><option value={1}>1 · 顺序执行</option><option value={2}>2 · 并行执行</option></select></label><label>底稿双审查顺序<select aria-label="审查执行顺序" value={config.review_order} onChange={e=>change({review_order:e.target.value})}><option value="parallel">反证与核验并行</option><option value="counter_first">先反证，后核验</option><option value="verifier_first">先核验，后反证</option></select></label></div>
      <div className="fs-studio-graph-layout"><div className="fs-orchestration" aria-label="可编辑研究编排">{groups.map((roles,i)=><div className="fs-orchestration-column" key={i}><header><span>0{i+1}</span>{["拆题与研究","独立审查","修订与综合","报告与追问"][i]}</header>{roles.map(r=><button key={r} className="fs-orchestration-node" aria-pressed={node===r} onClick={()=>setNode(r)}><GitBranch size={17}/><strong>{catalog.roles[r]}</strong><small>{methodTitles[config.bindings[r]]}</small><ArrowRight size={14}/></button>)}{i<3&&<ArrowRight className="fs-orchestration-arrow" size={24}/>}</div>)}</div>
      <aside className="fs-node-editor"><span className="fs-kicker">NODE SETTINGS</span><h2>{catalog.roles[node]}</h2><label>使用的 Skill<select aria-label="节点 Skill" value={config.bindings[node]} onChange={e=>change({bindings:{...config.bindings,[node]:e.target.value}})}>{Object.entries(methodTitles).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><button onClick={()=>{setMethod(config.bindings[node]);setTab("methods");}}>编辑此 Skill <ArrowRight size={15}/></button><p>此绑定进入该角色的模型上下文；方法工具也读取相同保存版本。</p><small>执行节点：{node}</small></aside></div>
      <p className="fs-studio-origin">图表示实际流程分组；追问、责任修订按运行时条件进入。顺序设置改变原生审查子图连接，两个审查者仍独立读取来源。必需复核、工具权限与已批准模型预算保持服务端约束。</p></>:<div className="fs-studio-layout"><nav aria-label="投研方法">{Object.entries(methodTitles).map(([k,v])=><button key={k} aria-current={method===k?"page":undefined} onClick={()=>setMethod(k)}><strong>{v}</strong><span>{Object.entries(config.bindings).filter(([,m])=>m===k).map(([r])=>catalog.roles[r]).join("、")||"尚未绑定角色；可由方法工具按需读取"}</span></button>)}</nav><section className="fs-draft-editor"><header><h2>{methodTitles[method]}</h2><button onClick={()=>setEditing(v=>!v)}>{editing?"阅读预览":"编辑方法"}</button></header>{editing?<textarea aria-label="Skill 内容" value={config.methods[method]} onChange={e=>change({methods:{...config.methods,[method]:e.target.value}})}/>:<div className="fs-method-prose"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{img:()=>null}}>{config.methods[method]}</ReactMarkdown></div>}<p>方法是研究指导，不是已核实的证据。已保存版本不会被覆盖。</p></section></div>}
    <section className="fs-studio-apply"><div><h2>应用到研究任务</h2><p>从下一次运行生效；不会自动发起模型调用或改写历史报告。</p></div><select aria-label="应用配置的任务" value={task} onChange={e=>setTask(e.target.value)}><option value="">选择研究任务…</option>{tasks.map(t=><option key={t.thread_id} value={t.thread_id} disabled={t.status==="busy"}>{t.title} · {t.thread_id.slice(-6)}{t.studio_assistant_id===version&&version?" · 已应用此版本":""}</option>)}</select><button disabled={busy||dirty||!version||!task} onClick={()=>void perform(async()=>{const result=await api<{notice:string}>(`research-studio/configurations/${version}/apply`,{thread_id:task});setTasks(await api<Task[]>("research-sessions"));setNotice(result.notice);})}>应用保存版本</button></section>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </section>;
}

export function ResearchConfigurationPicker({value,onChange}:{value:string;onChange:(v:string)=>void}){
  const [versions,setVersions]=useState<Version[]>([]),[error,setError]=useState("");
  useEffect(()=>{let live=true;api<Catalog>("research-studio/configurations").then(c=>{if(!Array.isArray(c.versions))throw new Error("invalid catalog");if(live)setVersions(c.versions);}).catch(()=>live&&setError("保存配置暂不可读取；可使用标准配置。"));return()=>{live=false;};},[]);
  return <label className="fs-new-configuration">研究编排<select aria-label="本次研究配置" value={value} onChange={e=>onChange(e.target.value)}><option value="">标准配置</option>{versions.map(v=><option key={v.assistant_id} value={v.assistant_id}>{v.title} · {new Date(v.created_at).toLocaleString("zh-CN")}</option>)}</select>{error&&<small>{error}</small>}</label>;
}
