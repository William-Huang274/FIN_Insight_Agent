import {
  Activity,
  Boxes,
  CheckCircle2,
  CircleStop,
  Database,
  ExternalLink,
  FlaskConical,
  LoaderCircle,
  Play,
  RefreshCcw,
  ServerCog,
  Settings2,
  ShieldAlert,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  EvalCatalogItem,
  OperationsApiClient,
  RunJob,
  StoredProfile,
  StoredSourceBundle,
  SystemStatus,
} from "../api/operations";
import "./operations-console.css";

type Snapshot = {
  status: SystemStatus;
  profiles: StoredProfile[];
  bundles: StoredSourceBundle[];
  runs: RunJob[];
  evals: EvalCatalogItem[];
};

type ViewState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; snapshot: Snapshot };

const api = new OperationsApiClient();

export function OperationsConsole() {
  const [state, setState] = useState<ViewState>({ kind: "loading" });
  const [action, setAction] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setState({ kind: "loading" });
    Promise.all([api.status(), api.profiles(), api.sourceBundles(), api.runs(), api.evals()])
      .then(([status, profiles, bundles, runs, evals]) => {
        setState({ kind: "ready", snapshot: { status, profiles, bundles, runs, evals } });
      })
      .catch((error: Error) => setState({ kind: "error", message: error.message }));
  }, []);

  useEffect(() => refresh(), [refresh]);

  const startSmoke = async () => {
    setAction("smoke");
    setActionError(null);
    try {
      await api.startSmoke();
      refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setAction(null);
    }
  };

  const cancel = async (jobId: string) => {
    setAction(jobId);
    setActionError(null);
    try {
      await api.cancelRun(jobId);
      refresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : String(error));
    } finally {
      setAction(null);
    }
  };

  return (
    <div className="operations-console">
      <header className="operations-console__topbar">
        <a className="operations-console__brand" href="/operations">
          <span><ServerCog size={19} /></span>
          <div><strong>FinSight Operations</strong><small>Runtime · data · jobs · evals</small></div>
        </a>
        <div className="operations-console__actions">
          <a href="/workspace">研究工作区 <ExternalLink size={13} /></a>
          <button className="operations-console__refresh" type="button" onClick={refresh}><RefreshCcw size={15} />刷新</button>
          <button type="button" className="is-primary" disabled={action === "smoke"} onClick={startSmoke}>
            {action === "smoke" ? <LoaderCircle className="is-spinning" size={15} /> : <Play size={15} />}本地 smoke
          </button>
        </div>
      </header>

      <main className="operations-console__page">
        <section className="operations-console__heading">
          <div><p>OPERATOR SURFACE</p><h1>运行与数据控制台</h1><span>这里管理运行时、数据源、作业和评测；不会形成或改写研究事实。</span></div>
        </section>
        {actionError ? <div className="operations-console__error"><ShieldAlert size={17} />{actionError}</div> : null}
        {state.kind === "loading" ? <div className="operations-console__loading"><LoaderCircle className="is-spinning" /><span>正在读取当前运行状态…</span></div> : null}
        {state.kind === "error" ? <div className="operations-console__error"><ShieldAlert size={17} />{state.message}</div> : null}
        {state.kind === "ready" ? <OperationsSnapshot snapshot={state.snapshot} action={action} onCancel={cancel} /> : null}
      </main>
    </div>
  );
}

function OperationsSnapshot({ snapshot, action, onCancel }: { snapshot: Snapshot; action: string | null; onCancel: (jobId: string) => void }) {
  const activeRuns = useMemo(() => snapshot.runs.filter((run) => ["queued", "running", "cancelling"].includes(run.status)), [snapshot.runs]);
  return (
    <>
      <section className="operations-console__status-grid">
        <StatusCard icon={Activity} label="服务状态" value={snapshot.status.status} ok={snapshot.status.status === "ok"} />
        <StatusCard icon={Settings2} label="Profiles" value={String(snapshot.profiles.length)} ok />
        <StatusCard icon={Database} label="Source Bundles" value={String(snapshot.bundles.length)} ok />
        <StatusCard icon={Boxes} label="活动作业" value={String(activeRuns.length)} ok={activeRuns.length === 0} />
        <StatusCard icon={FlaskConical} label="Eval runners" value={String(snapshot.evals.length)} ok />
      </section>

      <section className="operations-console__columns">
        <article className="operations-console__panel is-wide">
          <div className="operations-console__panel-title"><h2>已保存作业</h2><span>{snapshot.runs.length} 条 · 仅供审计，不代表当前能力</span></div>
          <div className="operations-console__table-wrap"><table><thead><tr><th>Job</th><th>类型</th><th>状态</th><th>Profile</th><th /></tr></thead><tbody>
            {snapshot.runs.length === 0 ? <tr><td colSpan={5} className="is-empty">暂无作业</td></tr> : snapshot.runs.slice(0, 20).map((run) => (
              <tr key={run.job_id}><td><code>{run.job_id}</code></td><td>{run.job_type}</td><td><RunStatus status={run.status} /></td><td>{run.profile_id ?? "—"}</td><td>{["queued", "running", "cancelling"].includes(run.status) ? <button type="button" disabled={action === run.job_id} onClick={() => onCancel(run.job_id)}><CircleStop size={14} />停止</button> : null}</td></tr>
            ))}
          </tbody></table></div>
        </article>

        <article className="operations-console__panel">
          <div className="operations-console__panel-title"><h2>路径与依赖</h2><span>{snapshot.status.status}</span></div>
          <dl className="operations-console__checks">
            {Object.entries(snapshot.status.checks).map(([key, value]) => <div key={key}><dt>{key}</dt><dd className={value === "ok" || value === "available" ? "is-ok" : ""}>{value}</dd></div>)}
          </dl>
        </article>
      </section>

      <section className="operations-console__columns">
        <article className="operations-console__panel">
          <div className="operations-console__panel-title"><h2>运行 Profiles</h2><span>{snapshot.profiles.length}</span></div>
          <SimpleList rows={snapshot.profiles.map((row) => ({ title: row.display_name, primary: row.profile_id, secondary: `${row.source_policy}${row.model_name ? ` · ${row.model_name}` : ""}` }))} empty="尚未保存 Profile" />
        </article>
        <article className="operations-console__panel">
          <div className="operations-console__panel-title"><h2>Source Bundles</h2><span>{snapshot.bundles.length}</span></div>
          <SimpleList rows={snapshot.bundles.map((row) => ({ title: row.display_name, primary: row.bundle_id, secondary: `${row.market} · ${row.coverage_theme} · ${row.ticker_count} tickers` }))} empty="尚未导入 Source Bundle" />
        </article>
        <article className="operations-console__panel">
          <div className="operations-console__panel-title"><h2>评测目录</h2><span>{snapshot.evals.length}</span></div>
          <SimpleList rows={snapshot.evals.map((row) => ({ title: row.label ?? row.eval_id, primary: row.eval_id, secondary: row.description ?? row.runner ?? "registered eval" }))} empty="未注册评测 Runner" />
        </article>
      </section>
    </>
  );
}

function StatusCard({ icon: Icon, label, value, ok }: { icon: typeof Activity; label: string; value: string; ok: boolean }) {
  return <article className="operations-console__status-card"><div className={ok ? "is-ok" : "is-warn"}><Icon size={18} /></div><span>{label}</span><strong>{value}</strong></article>;
}

function RunStatus({ status }: { status: string }) {
  const ok = ["succeeded", "completed"].includes(status);
  return <span className={`operations-console__run-status ${ok ? "is-ok" : ""}`}>{ok ? <CheckCircle2 size={12} /> : <Activity size={12} />}{status}</span>;
}

function SimpleList({ rows, empty }: { rows: Array<{ title: string; primary: string; secondary: string }>; empty: string }) {
  if (!rows.length) return <p className="operations-console__empty">{empty}</p>;
  return <div className="operations-console__list">{rows.slice(0, 12).map((row) => <div key={row.primary}><strong>{row.title}</strong><code>{row.primary}</code><small>{row.secondary}</small></div>)}</div>;
}
