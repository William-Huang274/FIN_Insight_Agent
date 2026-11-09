import { useMemo, useState } from "react";
import { parsePatch } from "diff";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { remarkBoundCitations } from "./remarkBoundCitations";
import type { ReportDiff } from "../api/reportSessions";
import './bound-citations.css';

/** Interpret the server's immutable patch with jsdiff; never regenerate report text. */
export function ReportDiffView({ value, proseOnly=false }: { value: ReportDiff; proseOnly?:boolean }) {
  const [context, setContext] = useState(false);
  const parsed = useMemo(() => {
    try { return { hunks: parsePatch(value.diff).flatMap(p => p.hunks), error: "" }; }
    catch { return { hunks: [], error: "无法呈现这份差异，请展开原始记录核对。" }; }
  }, [value.diff]);
  return <section className="fs-diff" aria-label="报告修订前后对照">
    <header><div><strong>v{value.before_version} → v{value.after_version}</strong><span>{parsed.hunks.length} 处变化{proseOnly ? ' · 正文对照' : ` · ${value.citations_changed ? "引用有变化" : "引用未变"} · ${value.charts_changed ? "图表有变化" : "图表未变"}`}</span></div>
      <label><input type="checkbox" checked={context} onChange={e => setContext(e.target.checked)} />显示邻近上下文</label></header>
    {value.reason && <details className="fs-diff-reason"><summary>修订请求与基线说明</summary><p>{value.reason}</p></details>}
    {parsed.error && <p role="alert">{parsed.error}</p>}
    {!value.diff && <p>报告正文没有变化。</p>}
    {parsed.hunks.map((h, i) => <div className="fs-diff-pair" key={i}>{["before", "after"].map(side => {
      const sign = side === "before" ? "-" : "+";
      const ids=(side==='before'?value.before_citation_ids:value.after_citation_ids)||[];
      const text = h.lines.filter(line => line.startsWith(sign) || line.startsWith(" ")).map(line => context || line.startsWith(sign) ? line.slice(1) : "").join("\n").trim();
      return <section key={side} className={`fs-diff-side ${side}`} aria-label={side === "before" ? "修订前" : "修订后"}>
        <h4>{side === "before" ? "修订前" : "修订后"} <span>v{side === "before" ? value.before_version : value.after_version} · 第 {i + 1} 处</span></h4>
        <div className="fs-diff-prose"><ReactMarkdown remarkPlugins={[remarkGfm, [remarkBoundCitations, { ids }]]} skipHtml components={{ table: ({children}) => <div className="fs-report-table" role="region" aria-label="版本对照数据表，可横向滚动" tabIndex={0}><table>{children}</table></div>, blockquote: ({children}) => <blockquote className="fs-report-note">{children}</blockquote>, img: ({alt}) => <span>{alt}</span>, a: ({children,href}) => href?.startsWith('#claim:')?<sup title="编号对应此版本；切换到该版本可查看引用依据。">[{children}]</sup>:<span>{children}</span> }}>{text || (side === "before" ? "此处为新增内容。" : "此处内容已删除。")}</ReactMarkdown></div>
      </section>;
    })}</div>)}
    <details className="fs-diff-raw"><summary>原始差异记录</summary><pre>{value.diff}</pre></details>
  </section>;
}
