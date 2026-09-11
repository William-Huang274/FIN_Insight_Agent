import { useEffect, useState } from "react";
import { sessionsApi, type ExecutionOptions, type ResearchConfiguration } from "../api/reportSessions";

export const executionModeName = { standard: "完整研究", auto: "自由调度", selected: "指定专家", single: "单 Agent" };
export const executionReady = (v: ExecutionOptions) => v.mode === "single" ? v.branch_ids.length === 1 : v.mode !== "selected" || v.branch_ids.length > 0;
export function ExecutionPicker({ value, onChange, disabled, assistantId, action = "research" }: { value: ExecutionOptions; onChange: (v: ExecutionOptions) => void; disabled?: boolean; assistantId?:string; action?: "research" | "ask" | "revise" }) {
  const [directions,setDirections]=useState<Record<string,{name:string;objective:string}>>({});
  useEffect(()=>{let live=true;setDirections({});if(assistantId)fetch(`/api/v1/research-studio/configurations/${assistantId}`).then(async r=>{if(!r.ok)throw Error('任务研究方向配置读取失败');return r.json();}).then(v=>live&&setDirections(v.configuration.directions||{})).catch(e=>live&&setError(e.message));return()=>{live=false;};},[assistantId]);
  const [catalog, setCatalog] = useState<ResearchConfiguration | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { let live = true; sessionsApi.config().then(v => live && setCatalog(v)).catch(e => live && setError(e.message)); return () => { live = false; }; }, []);
  return <fieldset className="fs-execution-picker" disabled={disabled}><legend>本次运行</legend><div>
    <label>协作模式<select aria-label="协作模式" value={value.mode} onChange={e => onChange({ ...value, mode: e.target.value as ExecutionOptions["mode"], branch_ids: e.target.value === "single" ? (value.branch_ids.slice(0, 1).length ? value.branch_ids.slice(0, 1) : (catalog?.branch_topics || []).slice(0, 1).map(b => b.branch_id)) : [] })}>
      <option value="auto">自由调度</option><option value="selected">指定专家</option><option value="single">单 Agent</option><option value="standard">完整研究</option></select></label>
    <label>研究模型<select aria-label="研究模型" value={value.model} onChange={e => onChange({ ...value, model: e.target.value as ExecutionOptions["model"] })}><option value="default">按角色配置</option><option value="deepseek-v4-flash">DeepSeek V4 Flash</option><option value="deepseek-v4-pro">DeepSeek V4 Pro</option></select></label>
  </div><p>{value.mode === "single" ? "单一研究者执行，不启动独立审查。结果标记为未经独立复核。" : value.mode === "auto" ? "由负责人按问题选择必要研究方向，动态分派；保留独立复核。" : value.mode === "selected" ? "仅在所选方向内安排专家工作；不能处理的范围需要明确反馈。" : "覆盖部署提供的全部研究方向，并完成多方审查。"}</p>
    {action !== "research" && <small>后续操作复用当前报告和底稿。追问不自动重写报告；修订按实际责任处理。</small>}
    {(value.mode === "selected" || value.mode === "single") && <details className="fs-execution-scope" open><summary>研究范围 · 已选 {value.branch_ids.length} 项</summary>{catalog?.branch_topics?.map(b => <label key={b.branch_id}><input type={value.mode === "single" ? "radio" : "checkbox"} name="research-scope" checked={value.branch_ids.includes(b.branch_id)} onChange={e => onChange({ ...value, branch_ids: value.mode === "single" ? [b.branch_id] : e.target.checked ? [...value.branch_ids, b.branch_id] : value.branch_ids.filter(id => id !== b.branch_id) })}/><span>{directions[b.branch_id]?`${directions[b.branch_id].name}：${directions[b.branch_id].objective}`:b.objective}</span></label>)}{!catalog?.branch_topics?.length && <p>研究范围尚未载入；暂不能提交此模式。</p>}</details>}
    {error && <p role="alert">无法载入运行选项：{error}</p>}
  </fieldset>;
}
