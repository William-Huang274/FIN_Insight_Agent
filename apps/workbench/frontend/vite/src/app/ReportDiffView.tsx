import { useMemo, useState } from "react";
import { parsePatch } from "diff";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ReportDiff } from "../api/reportSessions";

/** Interpret the server's immutable patch with jsdiff; never regenerate report text. */
export function ReportDiffView({ value }: { value: ReportDiff }) {
  const [context, setContext] = useState(false);
  const parsed = useMemo(() => {
    try { return { hunks: parsePatch(value.diff).flatMap(p => p.hunks), error: "" }; }
    catch { return { hunks: [], error: "无法呈现这份差异，请展开原始记录核对。" }; }
  }, [value.diff]);
  return <section className="fs-diff" aria-label="报告修订前后对照">
    <header><div><strong>v{value.before_version} → v{value.after_version}</strong><span>{parsed.hunks.length} 处变化 · {value.citations_changed ? "引用有变化" : "引用未变"} · {value.charts_changed ? "图表有变化" : "图表未变"}</span></div>
      <label><input type="checkbox" checked={context} onChange={e => setContext(e.target.checked)} />显示邻近上下文</label></header>
    {value.reason && <details className="fs-diff-reason"><summary>修订请求与基线说明</summary><p>{value.reason}</p></details>}
    {parsed.error && <p role="alert">{parsed.error}</p>}
    {!value.diff && <p>报告正文没有变化。</p>}
    {parsed.hunks.map((h, i) => <div className="fs-diff-pair" key={i}>{["before", "after"].map(side => {
      const sign = side === "before" ? "-" : "+";
      const text = h.lines.filter(line => line.startsWith(sign) || line.startsWith(" ")).map(line => context || line.startsWith(sign) ? line.slice(1) : "").join("\n").trim();
      return <section key={side} className={`fs-diff-side ${side}`} aria-label={side === "before" ? "修订前" : "修订后"}>
        <h4>{side === "before" ? "修订前" : "修订后"} <span>v{side === "before" ? value.before_version : value.after_version} · 第 {i + 1} 处</span></h4>
        <div className="fs-diff-prose"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{ img: ({alt}) => <span>{alt}</span>, a: ({children}) => <span>{children}</span> }}>{text || (side === "before" ? "此处为新增内容。" : "此处内容已删除。")}</ReactMarkdown></div>
      </section>;
    })}</div>)}
    <details className="fs-diff-raw"><summary>原始差异记录</summary><pre>{value.diff}</pre></details>
  </section>;
}
