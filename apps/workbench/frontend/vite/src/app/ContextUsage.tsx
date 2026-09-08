import { type Session } from "../api/reportSessions";

type Usage = NonNullable<Session["runs"]>[number]["context_usage"];

export function ContextUsage({ usage, nodeName }: { usage: Usage; nodeName: (s: string) => string }) {
  const measured = (usage?.nodes || []).filter(n => n.input_tokens != null);
  const largest = measured.reduce<typeof measured[number] | undefined>((a, b) => !a || b.input_tokens! > a.input_tokens! ? b : a, undefined);
  return <section className="fs-context-usage" aria-label="模型上下文用量">
    <h3>上下文用量</h3>
    <p>{largest ? `最近一次输入最高 ${largest.input_tokens!.toLocaleString()} tokens · 该模型上限 ${largest.capacity_tokens?.toLocaleString() ?? "未确认"}` : "等待本次请求用量"}</p>
    {!usage?.nodes.length && <small>等待模型用量记录；暂不估算 tokens。</small>}
    {usage?.nodes.some(n=>n.near_character_limit) && <p role="status">接近本任务的输入保护上限。可使用“保留进度并开新对话”，按需回读原始依据；此上限按字符计量，与模型 token 窗口不同。</p>}
    <details><summary>查看 {usage?.nodes.length || 0} 个节点及计量说明</summary><div className="fs-context-grid">
    {usage?.nodes.map(n => <div className="fs-context-node" key={n.actor}>
      <strong>{nodeName(n.actor)}</strong>
      <span>{n.input_tokens == null ? "等待实际用量" : `${n.input_tokens.toLocaleString()} tokens`}</span>
      <small>{n.model || "模型未记录"} · 上限 {n.capacity_tokens?.toLocaleString() ?? "未确认"}</small>
      {n.input_tokens != null && n.capacity_tokens != null && <progress
        aria-label={`${nodeName(n.actor)} 最近请求上下文占用`} max={n.capacity_tokens} value={n.input_tokens} />}
      {n.input_tokens == null && n.input_characters != null && <small>已准备 {n.input_characters.toLocaleString()} 字符；字符数不等于 tokens。</small>}
      {n.max_input_characters != null && <small>本任务输入保护：{n.input_characters?.toLocaleString() ?? "未知"} / {n.max_input_characters.toLocaleString()} 字符，包含工具描述。</small>}
      {n.near_capacity && <p role="status">接近模型窗口上限。继续前应保留当前产物、来源及未完成事项，避免丢失精确依据。</p>}
    </div>)}
    </div><p>{usage?.notice || "这里只显示单次请求输入，完整历史仍由会话保存。"}</p><p>节点之间分别计算；累计费用对应的 tokens 不是窗口占用。数值不表示摘要或跨会话交接已经通过保真验证。</p></details>
  </section>;
}
