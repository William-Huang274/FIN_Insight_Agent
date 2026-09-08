import { useEffect, useRef, useState } from "react";
import { sessionsApi, type ReportVersion, type ReportSnapshot, type ReportDiff } from "../api/reportSessions";
import { ReportDiffView } from "./ReportDiffView";

export function ReportVersions({ id, currentVersion, onSelect }: {
  id: string; currentVersion: number; onSelect: (report: ReportSnapshot | null) => void;
}) {
  const [versions, setVersions] = useState<ReportVersion[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [diff, setDiff] = useState<ReportDiff | null>(null);
  const epoch = useRef(0);
  useEffect(() => {
    let active = true;
    setSelected(""); setDiff(null); onSelect(null); setLoading(true); setError("");
    sessionsApi.versions(id).then(page => {
      if (active) { setVersions(page.versions); setCursor(page.next_cursor); }
    }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; epoch.current++; };
  }, [id, currentVersion, onSelect]);
  async function choose(checkpoint: string) {
    const request = ++epoch.current;
    setDiff(null); setError("");
    if (!checkpoint) { setSelected(""); onSelect(null); return; }
    setLoading(true);
    try {
      const report = await sessionsApi.version(id, checkpoint);
      if (request === epoch.current) { setSelected(checkpoint); onSelect(report); }
    } catch (e) { if (request === epoch.current) setError((e as Error).message); }
    finally { if (request === epoch.current) setLoading(false); }
  }
  async function more() {
    if (!cursor) return;
    const request = ++epoch.current;
    setLoading(true); setError("");
    try {
      const page = await sessionsApi.versions(id, cursor);
      if (request === epoch.current) {
        setVersions(old => [...new Map([...page.versions, ...old].map(v => [v.version, v])).values()].sort((a, b) => b.version - a.version));
        setCursor(page.next_cursor);
      }
    } catch (e) { if (request === epoch.current) setError((e as Error).message); }
    finally { if (request === epoch.current) setLoading(false); }
  }
  async function compare() {
    const request = ++epoch.current;
    setLoading(true); setError("");
    try { const result = await sessionsApi.diff(id, selected); if (request === epoch.current) setDiff(result); }
    catch (e) { if (request === epoch.current) setError((e as Error).message); }
    finally { if (request === epoch.current) setLoading(false); }
  }
  const version = versions.find(v => v.checkpoint_id === selected);
  return <section className="rs-version-browser" aria-label="报告版本">
    <div className="rs-export-actions">
      <label>阅读版本 <select aria-label="阅读报告版本" value={selected} disabled={loading} onChange={e => void choose(e.target.value)}>
        <option value="">当前 v{currentVersion}</option>
        {versions.filter(v => v.version !== currentVersion).map(v => <option key={v.checkpoint_id} value={v.checkpoint_id}>v{v.version} · {v.title}</option>)}
      </select></label>
      {cursor && <button disabled={loading} onClick={() => void more()}>载入更早记录</button>}
      {selected && <button disabled={loading} onClick={() => void compare()}>与当前版本比较</button>}
      {loading && <span role="status">正在读取版本…</span>}
    </div>
    {version && <p>正在阅读历史 v{version.version}；引用、图表和导出均对应此版。修订原因：{version.reason}</p>}
    {error && <p role="alert">{error}</p>}
    {diff && <details open className="rs-version-diff"><summary>v{diff.before_version} → v{diff.after_version} 的实际变化</summary>
      <ReportDiffView value={diff} />
    </details>}
  </section>;
}
