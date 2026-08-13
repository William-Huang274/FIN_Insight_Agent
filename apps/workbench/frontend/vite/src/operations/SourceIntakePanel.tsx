import { CloudDownload, FileCheck2, LoaderCircle, ShieldCheck, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { SourceIntakeAttempt, SourceIntakeRoute } from "../api/operations";


type Props = {
  routes: SourceIntakeRoute[];
  attempts: SourceIntakeAttempt[];
  action: string | null;
  onUpload: (routeId: string, file: File) => Promise<void>;
  onAutomatic: (routeId: string) => Promise<void>;
};

export function SourceIntakePanel({ routes, attempts, action, onUpload, onAutomatic }: Props) {
  const [routeId, setRouteId] = useState(routes[0]?.route_id ?? "");
  const [file, setFile] = useState<File | null>(null);
  useEffect(() => {
    if (!routes.some((route) => route.route_id === routeId)) {
      setRouteId(routes[0]?.route_id ?? "");
    }
  }, [routeId, routes]);
  const route = useMemo(() => routes.find((row) => row.route_id === routeId), [routeId, routes]);
  const busy = action === "source-upload" || action === "source-automatic";

  return (
    <section className="operations-console__panel operations-console__source-intake">
      <div className="operations-console__panel-title">
        <div><h2>官方资料入库</h2><p>自动获取和人工上传共用一份不可变 capture；入库成功仍不是 Evidence。</p></div>
        <span><ShieldCheck size={13} /> CAPTURE FIRST</span>
      </div>
      <div className="operations-console__source-layout">
        <div className="operations-console__source-form">
          <label htmlFor="source-intake-route">已登记来源</label>
          <select id="source-intake-route" value={routeId} onChange={(event) => { setRouteId(event.target.value); setFile(null); }}>
            {routes.map((row) => <option key={row.route_id} value={row.route_id}>{row.case_key} · {row.title}</option>)}
          </select>
          {route ? (
            <dl>
              <div><dt>发布日期</dt><dd>{route.publication_date}</dd></div>
              <div><dt>官方域名</dt><dd>{new URL(route.source_url).hostname}</dd></div>
              <div><dt>文件上限</dt><dd>{formatBytes(route.byte_ceiling)}</dd></div>
              <div><dt>当前权限</dt><dd>source only · not evidence</dd></div>
            </dl>
          ) : <p className="operations-console__empty">尚未登记来源 route</p>}
          <label className="operations-console__file-picker">
            <input
              type="file"
              accept="application/pdf,.pdf"
              disabled={!route?.operator_upload_enabled || busy}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            <UploadCloud size={18} />
            <span>{file ? `${file.name} · ${formatBytes(file.size)}` : "选择从官方页面下载的 PDF"}</span>
          </label>
          <div className="operations-console__source-actions">
            <button
              type="button"
              className="is-primary"
              disabled={!route || !file || busy || file.size > (route?.byte_ceiling ?? 0)}
              onClick={() => route && file ? onUpload(route.route_id, file) : undefined}
            >
              {action === "source-upload" ? <LoaderCircle className="is-spinning" size={15} /> : <FileCheck2 size={15} />}
              校验并入库
            </button>
            <button
              type="button"
              disabled={!route?.automatic_enabled || busy}
              onClick={() => route ? onAutomatic(route.route_id) : undefined}
            >
              {action === "source-automatic" ? <LoaderCircle className="is-spinning" size={15} /> : <CloudDownload size={15} />}
              自动获取一次
            </button>
          </div>
          <p className="operations-console__source-boundary">系统只接受 route 绑定的 HTTPS 官方 URL。搜索摘要、截图、文本粘贴和任意站点文件不能通过这个入口晋升。</p>
        </div>

        <div className="operations-console__source-attempts">
          <div className="operations-console__panel-title"><h3>最近入库记录</h3><span>{attempts.length} 条</span></div>
          {attempts.length === 0 ? <p className="operations-console__empty">暂无记录；原始字节不会通过 API 返回。</p> : (
            <div className="operations-console__source-attempt-list">
              {attempts.slice(0, 8).map((row) => (
                <article key={row.attempt_id}>
                  <div><strong>{row.case_key} · {methodLabel(row.acquisition_method)}</strong><AttemptStatus attempt={row} /></div>
                  <code>{row.attempt_id}</code>
                  <p>{row.failure_code ?? `${row.pdf_page_count} pages · ${formatBytes(row.raw_object_bytes)}`}</p>
                  {row.network_path?.transparent_tun_likely ? <small>TUN path · {row.network_path.route_interface ?? "transparent route"}</small> : null}
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function AttemptStatus({ attempt }: { attempt: SourceIntakeAttempt }) {
  const ok = attempt.status === "captured_ready_for_parse";
  return <span className={ok ? "is-ok" : "is-warn"}>{ok ? "可解析" : attempt.status === "acquisition_failed" ? "获取失败" : "已拒绝"}</span>;
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function methodLabel(value: SourceIntakeAttempt["acquisition_method"]) {
  return value === "operator_upload" ? "人工上传" : "自动获取";
}
