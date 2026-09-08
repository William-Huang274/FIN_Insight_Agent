import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { sessionsApi, type Source } from "../api/reportSessions";

function safeUrl(value?: string) { try { const url = new URL(value || ""); return ["http:", "https:"].includes(url.protocol) ? url.href : undefined; } catch { return undefined; } }
export function SourceReader({ id, checkpoint, source, context, quote, onClose }: { id: string; checkpoint: string; source: Source; context: string; quote?: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [pages, setPages] = useState([source]);
  const [loading, setLoading] = useState(false), [error, setError] = useState("");
  const [mode, setMode] = useState<"context" | "document">("context");
  const [search, setSearch] = useState(quote?.slice(0, 100) || "");
  const [match, setMatch] = useState(0);
  const ticket = useRef(0);
  useEffect(() => { dialog.current?.showModal(); return () => { ticket.current++; dialog.current?.close(); }; }, []);
  const last = pages[pages.length - 1];
  const text = pages.map(p => p.text || "").join("");
  const original = safeUrl(source.source_url || source.citation_urls?.[0]);
  const highlight = () => (tree: any) => {
    if (!search.trim()) return;
    const visit = (parent: any) => {
      if (!parent.children || ["code", "inlineCode"].includes(parent.type)) return;
      parent.children = parent.children.flatMap((child: any) => {
        if (child.type !== "text") { visit(child); return [child]; }
        const out = []; let start = 0; let at: number;
        while ((at = child.value.toLowerCase().indexOf(search.toLowerCase(), start)) !== -1) {
          out.push({ type: "text", value: child.value.slice(start, at) }, { type: "emphasis", data: { hName: "mark" }, children: [{ type: "text", value: child.value.slice(at, at + search.length) }] });
          start = at + search.length;
        }
        return out.length ? [...out, { type: "text", value: child.value.slice(start) }] : [child];
      });
    }; visit(tree);
  };
  const jump = () => { const marks = dialog.current?.querySelectorAll("mark") || []; if (marks.length) { marks[match % marks.length].scrollIntoView({ block: "center" }); setMatch(n => n + 1); } };
  const more = async () => {
    if (last.next_offset == null) return;
    const epoch = ++ticket.current; setLoading(true); setError("");
    try { const next = await sessionsApi.source(id, source.source_id, last.next_offset, checkpoint);
      if (epoch === ticket.current) { if (next.next_offset != null && next.next_offset <= last.next_offset) throw new Error("来源分页未向后推进，已停止读取。"); setPages(old => [...old, next]); }
    } catch (e) { if (epoch === ticket.current) setError((e as Error).message); }
    finally { if (epoch === ticket.current) setLoading(false); }
  };
  return <dialog ref={dialog} className="rg-reader" aria-label="来源上下文与原文阅读" onCancel={onClose}>
    <header><div><small>固定研究版本 · 已保存的来源</small><h2>{source.title || "来源原文"}</h2></div><button onClick={onClose}>关闭原文，返回研究图</button></header>
    <nav><button aria-pressed={mode === "context"} onClick={() => setMode("context")}>扩展上下文</button><button aria-pressed={mode === "document"} onClick={() => setMode("document")}>已存档原文</button>{original && <a href={original} target="_blank" rel="noopener noreferrer">打开外部原始文献 ↗</a>}</nav>
    <div className="rg-reader-search"><label>在已载入原文中查找<input value={search} onChange={e => { setSearch(e.target.value); setMatch(0); }} /></label><button disabled={!search.trim()} onClick={jump}>定位下一处</button></div>
    <div className={`rg-reader-body ${mode}`}>
      {mode === "context" && <aside><h3>正在核对的研究主张</h3><p>{context}</p>{quote && <><h3>保存的引用摘录</h3><blockquote>{quote}</blockquote></>}<p>对照上下文核对适用期间、限定条件与原文含义。</p></aside>}
      <article><ReactMarkdown skipHtml remarkPlugins={[remarkGfm, highlight]} components={{ img: ({ alt }) => <span>[原文图片：{alt || "请在外部文献中查看"}]</span>, a: ({ href, children }) => safeUrl(href) ? <a href={safeUrl(href)} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span> }}>{text || "该来源记录未保存正文；请使用外部文献入口核对。"}</ReactMarkdown>
        {error && <p role="alert">{error}</p>}{last.next_offset != null && <button disabled={loading} onClick={() => void more()}>{loading ? "正在读取…" : "继续读取后续原文"}</button>}
        <p className="rg-hint">{last.next_offset == null ? "此来源对象的已存档内容已全部载入。存档对象可能只是文献片段，不等同于外部文献全文。" : "当前仅载入部分存档内容，可继续向后读取。"}</p>
      </article>
    </div>
  </dialog>;
}
