import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Database,
  FileSearch,
  FlaskConical,
  FolderOpen,
  FolderSearch,
  History,
  MessageSquareText,
  Play,
  RefreshCcw,
  Terminal,
  Save,
} from "lucide-react";
import "../../static/styles.css";
import "./workbench.css";

type Status = "pass" | "warn" | "fail" | "neutral";

type ModelRoute = {
  backend?: string;
  base_url?: string | null;
  model_name?: string | null;
  api_key_env?: string | null;
};

type SourceProfile = {
  source_policy?: string;
  market_snapshot_id?: string | null;
  market_as_of_date?: string | null;
};

type RuntimeProfile = {
  python?: string;
  bge_model?: string | null;
  bge_device?: string;
  execution_shell?: string;
  wsl_distro?: string | null;
  wsl_repo_root?: string | null;
};

type WorkbenchProfile = {
  profile_id: string;
  display_name: string;
  env_file?: string | null;
  model_route?: ModelRoute;
  sources?: SourceProfile;
  runtime?: RuntimeProfile;
};

type StoredProfile = {
  profile_id: string;
  display_name: string;
  source_policy: string;
  model_name?: string | null;
  updated_at: string;
};

type PathStatus = {
  name: string;
  path: string | null;
  exists: boolean;
  required: boolean;
  kind: string;
  status: Status;
  reason: string;
};

type Summary = {
  row_count?: number;
  ticker_count?: number;
  years?: number[];
  form_counts?: Record<string, number>;
  source_tier_counts?: Record<string, number>;
  field_counts?: Record<string, number>;
};

type ReadinessReport = {
  status: Status;
  paths: PathStatus[];
  manifest?: Summary;
  market_evidence?: Summary;
  warnings?: string[];
  errors?: string[];
};

type ArtifactSummary = {
  artifact_id: string;
  label: string;
  rel_path: string;
  path: string;
  kind: string;
  exists: boolean;
  required: boolean;
  status: Status | "missing";
  size_bytes: number;
  modified_at?: string | null;
  summary: Record<string, unknown>;
  preview: string;
  error: string;
};

type RunArtifactIndex = {
  run_dir: string;
  status: Status;
  artifacts: ArtifactSummary[];
  missing_required: string[];
  warnings: string[];
  errors: string[];
  answer_preview: string;
  state_summary: Record<string, unknown>;
  gate_summary: Record<string, unknown>;
  performance_summary: Record<string, unknown>;
};

type RunJob = {
  job_id: string;
  job_type: string;
  status: string;
  profile_id?: string | null;
  prompt?: string | null;
  run_dir?: string | null;
  updated_at: string;
  error?: string;
  metadata?: Record<string, unknown>;
};

type StoredSession = {
  session_id: string;
  tenant_id?: string | null;
  user_id?: string | null;
  profile_id?: string | null;
  turn_count: number;
  latest_job_id: string;
  latest_status: string;
  updated_at: string;
};

type EvalRunner = {
  eval_id: string;
  label: string;
  description: string;
  timeout_hint_s?: number;
};

type RunInspectionReport = {
  job: RunJob;
  artifact_index?: RunArtifactIndex | null;
  native_checkpoint?: NativeCheckpointInspection | null;
};

type NativeCheckpointInspection = {
  schema_version: string;
  checkpoint_path: string;
  run_id: string;
  status: string;
  checkpoint_count: number;
  latest_checkpoint_id: string;
  latest_completed_node: string;
  next_recoverable_node: string;
  required_artifacts_for_next_node: string[];
  resume_supported: boolean;
  blocked_reasons: string[];
  missing_required_artifacts: string[];
  digest_mismatch_artifacts: string[];
  recoverable_state_summary: Record<string, unknown>;
};

type RunLogEvent = {
  job_id: string;
  sequence: number;
  stream: string;
  message: string;
  created_at: string;
};

type FormState = {
  envPath: string;
  profileId: string;
  displayName: string;
  repoRoot: string;
};

const initialForm: FormState = {
  envPath: "configs/sec_agent_full_source_demo.env.example",
  profileId: "full_source_demo",
  displayName: "Full-source demo",
  repoRoot: ".",
};

function App() {
  const [health, setHealth] = useState<Status>("neutral");
  const [form, setForm] = useState<FormState>(initialForm);
  const [profile, setProfile] = useState<WorkbenchProfile | null>(null);
  const [profiles, setProfiles] = useState<StoredProfile[]>([]);
  const [readiness, setReadiness] = useState<ReadinessReport | null>(null);
  const [runDir, setRunDir] = useState("reports/quality/<saved-run-dir>");
  const [runs, setRuns] = useState<RunJob[]>([]);
  const [runReport, setRunReport] = useState<RunInspectionReport | null>(null);
  const [nativeCheckpoint, setNativeCheckpoint] = useState<NativeCheckpointInspection | null>(null);
  const [sessions, setSessions] = useState<StoredSession[]>([]);
  const [sessionTurns, setSessionTurns] = useState<RunJob[]>([]);
  const [evals, setEvals] = useState<EvalRunner[]>([]);
  const [prompt, setPrompt] = useState(
    "结合 SEC 10-K、最新 10-Q、8-K 业绩新闻稿和最近三个月市场快照，比较 NVDA、AMD、MSFT、AMZN、GOOGL 的 AI 基本面、管理层解释、市场反应和估值分歧。",
  );
  const [commandMode, setCommandMode] = useState("ask-full-source-api");
  const [sessionMode, setSessionMode] = useState("session-full-source-api");
  const [apiKey, setApiKey] = useState("");
  const [tenantId, setTenantId] = useState("workbench_tenant");
  const [userId, setUserId] = useState("workbench_user");
  const [sessionId, setSessionId] = useState(() => newSessionId());
  const [activeJob, setActiveJob] = useState<RunJob | null>(null);
  const [jobEvents, setJobEvents] = useState<RunLogEvent[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const artifactJumpJobIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    void checkHealth();
    void loadSavedProfiles();
    void loadRuns();
    void loadSessions();
    void loadEvals();
  }, []);

  useEffect(() => {
    if (!activeJob?.job_id || isTerminal(activeJob.status)) return undefined;
    const timer = window.setInterval(() => {
      void refreshJob(activeJob.job_id);
    }, 1200);
    return () => window.clearInterval(timer);
  }, [activeJob?.job_id, activeJob?.status]);

  const readinessStatus = readiness?.status ?? "neutral";
  const route = profile?.model_route ?? {};
  const sources = profile?.sources ?? {};
  const runtime = profile?.runtime ?? {};

  async function checkHealth() {
    try {
      const payload = await requestJson<{ status: string }>("/api/health");
      setHealth(payload.status === "ok" ? "pass" : "warn");
    } catch {
      setHealth("fail");
    }
  }

  async function importProfile() {
    await runBusy("import", async () => {
      const imported = await requestJson<WorkbenchProfile>("/api/profiles/import-env", {
        method: "POST",
        body: JSON.stringify(importPayload(form)),
      });
      setProfile(imported);
      await validateSources(imported);
    });
  }

  async function saveProfile() {
    await runBusy("save", async () => {
      const current =
        profile ??
        (await requestJson<WorkbenchProfile>("/api/profiles/import-env", {
          method: "POST",
          body: JSON.stringify(importPayload(form)),
        }));
      setProfile(current);
      await requestJson("/api/profiles", {
        method: "POST",
        body: JSON.stringify(current),
      });
      await loadSavedProfiles();
    });
  }

  async function validateSources(targetProfile = profile) {
    await runBusy("validate", async () => {
      const body = targetProfile
        ? { profile: targetProfile, repo_root: form.repoRoot || "." }
        : { ...importPayload(form), repo_root: form.repoRoot || "." };
      const report = await requestJson<ReadinessReport>("/api/profiles/validate", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setReadiness(report);
    });
  }

  async function loadSavedProfiles() {
    const payload = await requestJson<{ profiles: StoredProfile[] }>("/api/profiles");
    setProfiles(payload.profiles ?? []);
  }

  async function loadRuns() {
    const payload = await requestJson<{ runs: RunJob[] }>("/api/runs");
    setRuns(payload.runs ?? []);
  }

  async function loadSessions() {
    const payload = await requestJson<{ sessions: StoredSession[] }>("/api/sessions");
    setSessions(payload.sessions ?? []);
  }

  async function loadEvals() {
    const payload = await requestJson<{ evals: EvalRunner[] }>("/api/evals");
    setEvals(payload.evals ?? []);
  }

  async function loadSessionTurns(targetSessionId = sessionId) {
    const id = targetSessionId.trim();
    if (!id) {
      setSessionTurns([]);
      return;
    }
    const payload = await requestJson<{ session_id: string; turns: RunJob[] }>(`/api/sessions/${encodeURIComponent(id)}/turns`);
    setSessionTurns(payload.turns ?? []);
  }

  async function inspectRun() {
    await runBusy("inspect_run", async () => {
      const payload = await requestJson<RunInspectionReport>("/api/runs/inspect", {
        method: "POST",
        body: JSON.stringify({
          run_dir: runDir.trim(),
          profile_id: profile?.profile_id ?? null,
        }),
      });
      setRunReport(payload);
      setNativeCheckpoint(payload.native_checkpoint ?? null);
      await loadRuns();
    });
  }

  async function loadRun(jobId: string) {
    await runBusy(`run:${jobId}`, async () => {
      const payload = await requestJson<RunInspectionReport>(`/api/runs/${encodeURIComponent(jobId)}`);
      if (payload.artifact_index) {
        setRunReport(payload as RunInspectionReport);
      } else {
        setRunReport(null);
      }
      setNativeCheckpoint(payload.native_checkpoint ?? null);
      setActiveJob(payload.job);
      await loadJobEvents(jobId);
      setRunDir(payload.job.run_dir ?? "");
    });
  }

  async function loadSession(targetSession: StoredSession) {
    setTenantId(targetSession.tenant_id ?? "workbench_tenant");
    setUserId(targetSession.user_id ?? "workbench_user");
    setSessionId(targetSession.session_id);
    await loadSessionTurns(targetSession.session_id);
    await loadRun(targetSession.latest_job_id);
  }

  async function startSmokeJob() {
    await runBusy("smoke_run", async () => {
      const payload = await requestJson<{ job: RunJob }>("/api/runs/smoke", {
        method: "POST",
        body: JSON.stringify({ profile_id: profile?.profile_id ?? null }),
      });
      setActiveJob(payload.job);
      setJobEvents([]);
      await refreshJob(payload.job.job_id);
      await loadRuns();
    });
  }

  async function startAgentAsk() {
    await runBusy("agent_ask", async () => {
      if (!profile) {
        throw new Error("请先导入或加载 Profile。");
      }
      const payload = await requestJson<{ job: RunJob }>("/api/runs/ask", {
        method: "POST",
          body: JSON.stringify({
            profile,
            prompt,
            command_mode: commandMode,
            api_key_value: apiKey.trim() || null,
          }),
      });
      setActiveJob(payload.job);
      setJobEvents([]);
      await refreshJob(payload.job.job_id);
      await loadRuns();
    });
  }

  async function startSessionTurn() {
    await runBusy("session_turn", async () => {
      if (!profile) {
        throw new Error("请先导入或加载 Profile。");
      }
      const payload = await requestJson<{ job: RunJob }>("/api/sessions/turns", {
        method: "POST",
        body: JSON.stringify({
          profile,
          prompt,
          command_mode: sessionMode,
          session_id: sessionId.trim(),
          tenant_id: tenantId.trim() || "workbench_tenant",
          user_id: userId.trim() || "workbench_user",
          api_key_value: apiKey.trim() || null,
        }),
      });
      setActiveJob(payload.job);
      setJobEvents([]);
      await refreshJob(payload.job.job_id);
      await loadRuns();
      await loadSessions();
      await loadSessionTurns(sessionId);
    });
  }

  async function startEvalRun(evalId: string) {
    await runBusy(`eval:${evalId}`, async () => {
      const payload = await requestJson<{ job: RunJob }>("/api/evals/run", {
        method: "POST",
        body: JSON.stringify({
          eval_id: evalId,
          profile_id: profile?.profile_id ?? null,
        }),
      });
      setActiveJob(payload.job);
      setJobEvents([]);
      await refreshJob(payload.job.job_id);
      await loadRuns();
    });
  }

  async function inspectNativeCheckpoint() {
    await runBusy("native_checkpoint_inspect", async () => {
      const payload = await requestJson<NativeCheckpointInspection>("/api/native-checkpoints/inspect", {
        method: "POST",
        body: JSON.stringify({ run_dir: runDir.trim() }),
      });
      setNativeCheckpoint(payload);
    });
  }

  async function resumeNativeCheckpoint() {
    await runBusy("native_checkpoint_resume", async () => {
      if (!profile) {
        throw new Error("请先导入或加载 Profile。");
      }
      const payload = await requestJson<{ job: RunJob; inspection: NativeCheckpointInspection }>("/api/native-checkpoints/resume", {
        method: "POST",
        body: JSON.stringify({
          run_dir: runDir.trim(),
          profile,
          api_key_value: apiKey.trim() || null,
          include_synthesis: true,
          checkpoint_mode: "sqlite",
        }),
      });
      setNativeCheckpoint(payload.inspection);
      setActiveJob(payload.job);
      setJobEvents([]);
      await refreshJob(payload.job.job_id);
      await loadRuns();
    });
  }

  async function refreshJob(jobId: string) {
    const payload = await requestJson<RunInspectionReport>(`/api/runs/${encodeURIComponent(jobId)}`);
    setActiveJob(payload.job);
    await loadJobEvents(jobId);
    if (payload.artifact_index) {
      setRunReport(payload as RunInspectionReport);
    }
    if (payload.native_checkpoint !== undefined) {
      setNativeCheckpoint(payload.native_checkpoint ?? null);
    }
    if (payload.job.run_dir) {
      setRunDir(payload.job.run_dir);
    }
    if (isTerminal(payload.job.status)) {
      await loadRuns();
      await loadSessions();
      if (payload.artifact_index && !artifactJumpJobIds.current.has(payload.job.job_id)) {
        artifactJumpJobIds.current.add(payload.job.job_id);
        window.setTimeout(() => document.getElementById("artifacts")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
      }
    }
  }

  async function loadJobEvents(jobId: string) {
    const payload = await requestJson<{ events: RunLogEvent[] }>(`/api/runs/${encodeURIComponent(jobId)}/events`);
    setJobEvents(payload.events ?? []);
  }

  async function loadProfile(profileId: string) {
    await runBusy(`profile:${profileId}`, async () => {
      const loaded = await requestJson<WorkbenchProfile>(`/api/profiles/${encodeURIComponent(profileId)}`);
      setProfile(loaded);
      setForm((prev) => ({
        ...prev,
        envPath: loaded.env_file ?? prev.envPath,
        profileId: loaded.profile_id,
        displayName: loaded.display_name,
      }));
      await validateSources(loaded);
    });
  }

  async function runBusy(name: string, action: () => Promise<void>) {
    setBusy(name);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  const navItems = useMemo(
    () => [
      { label: "数据源配置", icon: FolderOpen, href: "#profile", active: true },
      { label: "数据源检查", icon: FileSearch, href: "#readiness", active: false },
      { label: "Agent 会话", icon: MessageSquareText, href: "#agent", active: false },
      { label: "评测入口", icon: FlaskConical, href: "#evals", active: false },
      { label: "运行产物", icon: Database, href: "#artifacts", active: false },
    ],
    [],
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">F</div>
          <div>
            <div className="brand-title">FinSight</div>
            <div className="brand-subtitle">Workbench</div>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <a
              className={`nav-item ${item.active ? "active" : ""}`}
              href={item.href}
              key={item.label}
            >
              <item.icon size={16} aria-hidden="true" />
              {item.label}
            </a>
          ))}
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>FinSight Workbench</h1>
            <p>配置研究数据源，检查证据产物，并为后续 Agent 会话准备可复用 profile。</p>
          </div>
          <StatusPill status={health} label={health === "pass" ? "已连接" : "未连接"} />
        </header>

        <section id="profile" className="panel">
          <div className="section-heading">
            <div>
              <h2>Profile 导入</h2>
              <p>导入现有 `.env` profile。Workbench 只保存环境变量名，不保存真实 API key。</p>
            </div>
          </div>

          <div className="profile-form">
            <TextInput label="Profile 文件" value={form.envPath} onChange={(envPath) => setForm({ ...form, envPath })} />
            <TextInput label="Profile ID" value={form.profileId} onChange={(profileId) => setForm({ ...form, profileId })} />
            <TextInput label="显示名称" value={form.displayName} onChange={(displayName) => setForm({ ...form, displayName })} />
            <TextInput label="仓库根目录" value={form.repoRoot} onChange={(repoRoot) => setForm({ ...form, repoRoot })} />
            <div className="form-actions">
              <button type="button" onClick={importProfile} disabled={Boolean(busy)}>
                <FolderOpen size={16} aria-hidden="true" />
                {busy === "import" ? "导入中" : "导入 Profile"}
              </button>
              <button type="button" className="secondary" onClick={saveProfile} disabled={Boolean(busy)}>
                <Save size={16} aria-hidden="true" />
                {busy === "save" ? "保存中" : "保存 Profile"}
              </button>
              <button type="button" className="secondary" onClick={() => validateSources()} disabled={Boolean(busy)}>
                <FileSearch size={16} aria-hidden="true" />
                {busy === "validate" ? "检查中" : "检查数据源"}
              </button>
            </div>
          </div>

          <SavedProfiles profiles={profiles} onLoad={loadProfile} />

          {profile ? (
            <div className="summary-grid">
              <MetricBox label="Profile" value={profile.display_name} detail={profile.profile_id} />
              <MetricBox label="模型路由" value={route.model_name ?? route.backend ?? "未配置"} detail={route.base_url ?? ""} />
              <MetricBox label="密钥环境变量" value={route.api_key_env ?? "未配置"} detail="不保存真实 key" />
              <MetricBox label="Source policy" value={sources.source_policy ?? "未配置"} />
              <MetricBox label="Market snapshot" value={sources.market_snapshot_id ?? "未配置"} detail={sources.market_as_of_date ?? ""} />
              <MetricBox
                label="运行设置"
                value={`${runtime.execution_shell ?? "auto"} · ${runtime.bge_device ?? "cpu"}`}
                detail={runtime.bge_model || runtime.wsl_repo_root || runtime.python || "python"}
              />
            </div>
          ) : (
            <div className="summary-grid empty-state">
              <div>
                <h3>等待导入</h3>
                <p>导入后这里会展示模型路由、source policy、数据路径和密钥环境变量名。</p>
              </div>
            </div>
          )}
        </section>

        <section id="readiness" className="panel">
          <div className="section-heading">
            <div>
              <h2>Source Readiness</h2>
              <p>检查 manifest、BM25 / ObjectBM25、8-K source gap 和 market evidence 是否足以支撑当前 profile。</p>
            </div>
            <StatusPill status={readinessStatus} />
          </div>

          {error ? <MessageBlock title="Request error" rows={[error]} status="fail" /> : null}
          {readiness ? <Readiness report={readiness} /> : <EmptyReadiness />}
        </section>

        <section id="agent" className="panel">
          <div className="section-heading">
            <div>
              <h2>Agent 会话</h2>
              <p>先用受控后台任务跑轻量 smoke；完整单轮任务会复用当前 Profile，并通过日志面板显示执行进度。</p>
            </div>
            <StatusPill status={jobStatus(activeJob)} label={activeJob?.status ?? "未启动"} />
          </div>

          <div className="agent-grid">
            <label>
              <span>本次运行 API key</span>
              <input
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                type="password"
                autoComplete="off"
                placeholder={route.api_key_env ? `填入 ${route.api_key_env}` : "只在本次请求中使用，不保存"}
              />
            </label>
            <label>
              <span>单轮运行模式</span>
              <select value={commandMode} onChange={(event) => setCommandMode(event.target.value)}>
                <option value="ask-full-source-api">完整数据源 API 模式</option>
                <option value="ask-mixed-8k-api">SEC + 8-K API 模式</option>
                <option value="ask-mixed-api">SEC 10-K/10-Q API 模式</option>
                <option value="ask-api">基础 API 模式</option>
                <option value="plan">仅规划查询合约</option>
              </select>
            </label>
            <label className="prompt-field">
              <span>单轮问题</span>
              <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            </label>
            <div className="form-actions">
              <button type="button" className="secondary" onClick={startSmokeJob} disabled={Boolean(busy)}>
                <Terminal size={16} aria-hidden="true" />
                {busy === "smoke_run" ? "启动中" : "运行本地 Smoke"}
              </button>
              <button type="button" onClick={startAgentAsk} disabled={Boolean(busy)}>
                <Play size={16} aria-hidden="true" />
                {busy === "agent_ask" ? "启动中" : "启动单轮 Agent"}
              </button>
            </div>
          </div>

          <div className="session-grid">
            <TextInput label="Tenant" value={tenantId} onChange={setTenantId} />
            <TextInput label="User" value={userId} onChange={setUserId} />
            <TextInput label="Session / Thread" value={sessionId} onChange={setSessionId} />
            <label>
              <span>多轮运行模式</span>
              <select value={sessionMode} onChange={(event) => setSessionMode(event.target.value)}>
                <option value="session-full-source-api">完整数据源会话</option>
                <option value="session-mixed-8k-api">SEC + 8-K 会话</option>
                <option value="session-mixed-api">SEC 10-K/10-Q 会话</option>
                <option value="session-api">基础会话</option>
              </select>
            </label>
            <div className="form-actions">
              <button type="button" className="secondary" onClick={() => setSessionId(newSessionId())} disabled={Boolean(busy)}>
                新建 Session
              </button>
              <button type="button" onClick={startSessionTurn} disabled={Boolean(busy)}>
                <MessageSquareText size={16} aria-hidden="true" />
                {busy === "session_turn" ? "发送中" : "发送到当前 Session"}
              </button>
            </div>
          </div>

          <div className="session-history-grid">
            <SavedSessions sessions={sessions} onLoad={loadSession} />
            <SessionTurns turns={sessionTurns} onLoadRun={loadRun} onRefresh={() => loadSessionTurns(sessionId)} />
          </div>

          <JobConsole job={activeJob} events={jobEvents} />
        </section>

        <section id="evals" className="panel">
          <div className="section-heading">
            <div>
              <h2>评测入口</h2>
              <p>运行固定 smoke / eval 任务，检查会话状态、上下文接口和小压测，不开放任意 shell 命令。</p>
            </div>
          </div>

          <EvalRunners evals={evals} busy={busy} onRun={startEvalRun} />
        </section>

        <section id="artifacts" className="panel">
          <div className="section-heading">
            <div>
              <h2>运行产物</h2>
              <p>检查已有 run 目录中的图状态、覆盖矩阵、数值台账、判断计划、后置校验和渲染答案。</p>
            </div>
            <StatusPill status={runReport?.artifact_index?.status ?? "neutral"} />
          </div>

          <div className="profile-form run-form">
            <TextInput label="Run 目录" value={runDir} onChange={setRunDir} />
            <div className="form-actions">
              <button type="button" onClick={inspectRun} disabled={Boolean(busy)}>
                <FolderSearch size={16} aria-hidden="true" />
                {busy === "inspect_run" ? "检查中" : "检查运行目录"}
              </button>
              <button type="button" className="secondary" onClick={inspectNativeCheckpoint} disabled={Boolean(busy)}>
                <History size={16} aria-hidden="true" />
                {busy === "native_checkpoint_inspect" ? "检查中" : "检查 Native Checkpoint"}
              </button>
              <button type="button" className="secondary" onClick={resumeNativeCheckpoint} disabled={Boolean(busy) || !nativeCheckpoint?.resume_supported}>
                <Play size={16} aria-hidden="true" />
                {busy === "native_checkpoint_resume" ? "恢复中" : "从 Checkpoint 恢复"}
              </button>
            </div>
          </div>

          {nativeCheckpoint ? <NativeCheckpointPanel inspection={nativeCheckpoint} /> : null}
          <SavedRuns runs={runs} onLoad={loadRun} />
          {runReport ? <RunArtifacts report={runReport} /> : <EmptyArtifacts />}
        </section>
      </main>
    </div>
  );
}

function NativeCheckpointPanel({ inspection }: { inspection: NativeCheckpointInspection }) {
  return (
    <div className="checkpoint-panel">
      <div className="summary-grid">
        <MetricBox label="Checkpoint" value={inspection.resume_supported ? "可恢复" : "不可恢复"} detail={inspection.status || inspection.run_id} />
        <MetricBox label="Latest node" value={inspection.latest_completed_node || "unknown"} detail={inspection.latest_checkpoint_id} />
        <MetricBox label="Next node" value={inspection.next_recoverable_node || "none"} detail={`${inspection.checkpoint_count} checkpoints`} />
      </div>
      <div className="readiness-columns">
        <ListBlock title="Required artifacts" values={listRecord(inspection.required_artifacts_for_next_node)} />
        <ListBlock
          title="Blocked reasons"
          values={listRecord([...(inspection.blocked_reasons ?? []), ...(inspection.missing_required_artifacts ?? []), ...(inspection.digest_mismatch_artifacts ?? [])])}
        />
      </div>
    </div>
  );
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label>
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} autoComplete="off" />
    </label>
  );
}

function SavedProfiles({ profiles, onLoad }: { profiles: StoredProfile[]; onLoad: (profileId: string) => void }) {
  if (!profiles.length) {
    return (
      <div className="saved-profiles empty-state">
        <h3>已保存 Profile</h3>
        <p>还没有保存过 profile。</p>
      </div>
    );
  }
  return (
    <div className="saved-profiles">
      <h3>已保存 Profile</h3>
      <div className="saved-profile-list">
        {profiles.map((profile) => (
          <button className="saved-profile-button" type="button" onClick={() => onLoad(profile.profile_id)} key={profile.profile_id}>
            {profile.display_name || profile.profile_id}
            <span>{profile.source_policy || "source policy 未配置"}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function SavedRuns({ runs, onLoad }: { runs: RunJob[]; onLoad: (jobId: string) => void }) {
  if (!runs.length) {
    return (
      <div className="saved-profiles empty-state">
        <h3>已保存 Run</h3>
        <p>检查过的运行目录会保存在这里，便于后续查看产物。</p>
      </div>
    );
  }
  return (
    <div className="saved-profiles">
      <h3>已保存 Run</h3>
      <div className="saved-profile-list">
        {runs.map((job) => (
          <button className="saved-profile-button" type="button" onClick={() => onLoad(job.job_id)} key={job.job_id}>
            {job.job_id}
            <span>{job.status} · {job.run_dir ?? "run_dir 未记录"}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function SavedSessions({ sessions, onLoad }: { sessions: StoredSession[]; onLoad: (session: StoredSession) => void }) {
  if (!sessions.length) {
    return (
      <div className="saved-profiles empty-state">
        <h3>Session 列表</h3>
        <p>发送多轮问题后，这里会按 session 聚合历史 turn。</p>
      </div>
    );
  }
  return (
    <div className="saved-profiles compact-panel">
      <h3>
        <History size={15} aria-hidden="true" />
        Session 列表
      </h3>
      <div className="saved-profile-list vertical-list">
        {sessions.map((session) => (
          <button className="saved-profile-button" type="button" onClick={() => onLoad(session)} key={session.session_id}>
            {session.session_id}
            <span>
              {session.turn_count} turn · {session.latest_status} · {session.user_id ?? "user 未记录"}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function SessionTurns({
  turns,
  onLoadRun,
  onRefresh,
}: {
  turns: RunJob[];
  onLoadRun: (jobId: string) => void;
  onRefresh: () => void;
}) {
  return (
    <div className="saved-profiles compact-panel">
      <div className="inline-heading">
        <h3>
          <MessageSquareText size={15} aria-hidden="true" />
          当前 Session 历史
        </h3>
        <button type="button" className="icon-button" onClick={onRefresh} aria-label="刷新 session 历史">
          <RefreshCcw size={15} aria-hidden="true" />
        </button>
      </div>
      {turns.length ? (
        <div className="session-turn-list">
          {turns.map((turn) => (
            <button className="session-turn" type="button" onClick={() => onLoadRun(turn.job_id)} key={turn.job_id}>
              <span className="mono">{turn.job_id}</span>
              <strong>{turn.status}</strong>
              <span>{turn.prompt || "prompt 未记录"}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="muted-text">当前 session 还没有记录 turn。</p>
      )}
    </div>
  );
}

function EvalRunners({
  evals,
  busy,
  onRun,
}: {
  evals: EvalRunner[];
  busy: string | null;
  onRun: (evalId: string) => void;
}) {
  if (!evals.length) {
    return (
      <div className="saved-profiles empty-state">
        <h3>没有可用评测</h3>
        <p>后端没有返回受控评测任务目录。</p>
      </div>
    );
  }
  return (
    <div className="saved-profiles">
      <h3>受控评测任务</h3>
      <div className="saved-profile-list eval-list">
        {evals.map((item) => {
          const isBusy = busy === `eval:${item.eval_id}`;
          return (
            <button className="saved-profile-button" type="button" onClick={() => onRun(item.eval_id)} disabled={Boolean(busy)} key={item.eval_id}>
              {isBusy ? "运行中" : item.label}
              <span>
                {item.eval_id}
                {item.timeout_hint_s ? ` · 约 ${item.timeout_hint_s}s 内` : ""}
              </span>
              <span>{item.description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function RunArtifacts({ report }: { report: RunInspectionReport }) {
  if (!report.artifact_index) {
    return <EmptyArtifacts />;
  }
  const index = report.artifact_index;
  return (
    <div className="readiness-layout">
      <div className="summary-grid">
        <MetricBox label="Job" value={report.job.job_id} detail={report.job.status} />
        <MetricBox label="Run status" value={statusLabel(index.status)} detail={report.job.job_type} />
        <MetricBox label="Run directory" value={index.run_dir} />
      </div>

      <div className="readiness-columns">
        <div>
          <h3>产物清单</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>产物</th>
                  <th>状态</th>
                  <th>类型</th>
                  <th>摘要</th>
                </tr>
              </thead>
              <tbody>
                {index.artifacts.map((artifact) => (
                  <tr key={artifact.artifact_id}>
                    <td>
                      <div>{artifact.label}</div>
                      <div className="mono">{artifact.rel_path}</div>
                    </td>
                    <td>
                      <StatusPill status={artifact.status === "missing" ? "neutral" : artifact.status} label={artifact.status === "missing" ? "缺失" : undefined} />
                    </td>
                    <td>{artifact.kind}</td>
                    <td className="mono">{artifact.exists ? compactObject(artifact.summary) : artifact.error || "missing"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <h3>关键摘要</h3>
          <ListBlock title="Graph state" values={flatSummary(index.state_summary)} />
          <ListBlock title="Post gates" values={flatSummary(index.gate_summary)} />
          <ListBlock title="Performance" values={flatSummary(index.performance_summary)} />
        </div>
      </div>

      <div className="readiness-columns">
        <MessageBlock title="Warnings" rows={index.warnings ?? []} status="warn" />
        <MessageBlock title="Errors" rows={index.errors ?? []} status="fail" />
      </div>

      <div className="list-block">
        <h3>Rendered answer preview</h3>
        <pre className="answer-preview">{index.answer_preview || "无 rendered answer"}</pre>
      </div>
    </div>
  );
}

function JobConsole({ job, events }: { job: RunJob | null; events: RunLogEvent[] }) {
  const evalSummary = job?.metadata?.eval_summary as Record<string, unknown> | undefined;
  return (
    <div className="job-console">
      <div className="job-console-header">
        <h3>运行日志</h3>
        {job ? (
          <span className="mono">
            {job.job_id} · {job.job_type} · {job.status}
          </span>
        ) : (
          <span className="mono">尚未启动</span>
        )}
      </div>
      <pre>
        {events.length
          ? events.map((event) => `[${event.sequence}] ${event.stream}: ${event.message}`).join("\n")
          : "运行本地 smoke 或单轮 Agent 后，这里会显示 stdout/system 事件。"}
      </pre>
      {evalSummary ? (
        <p className="job-summary">
          Eval summary: {String(evalSummary.status ?? "unknown")}
          {evalSummary.pass_count !== undefined ? ` · pass ${String(evalSummary.pass_count)}` : ""}
          {evalSummary.failure_count !== undefined ? ` · fail ${String(evalSummary.failure_count)}` : ""}
          {evalSummary.skipped_count !== undefined ? ` · skipped ${String(evalSummary.skipped_count)}` : ""}
        </p>
      ) : null}
      {job?.error ? <p className="job-error">{job.error}</p> : null}
    </div>
  );
}

function EmptyArtifacts() {
  return (
    <div className="readiness-layout empty-state">
      <div>
        <h3>没有运行产物报告</h3>
        <p>输入已有 run 目录后，Workbench 会检查核心中间产物和最终渲染答案。</p>
      </div>
    </div>
  );
}

function Readiness({ report }: { report: ReadinessReport }) {
  return (
    <div className="readiness-layout">
      <div className="summary-grid">
        <MetricBox label="Manifest 行数" value={numberText(report.manifest?.row_count)} detail={`${numberText(report.manifest?.ticker_count)} tickers`} />
        <MetricBox label="财年范围" value={listText(report.manifest?.years)} detail="来自 manifest" />
        <MetricBox
          label="市场快照行数"
          value={numberText(report.market_evidence?.row_count)}
          detail={`${numberText(report.market_evidence?.ticker_count)} tickers`}
        />
      </div>
      <div className="readiness-columns">
        <div>
          <h3>产物路径</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>产物</th>
                  <th>状态</th>
                  <th>类型</th>
                  <th>路径</th>
                  <th>原因</th>
                </tr>
              </thead>
              <tbody>
                {report.paths.map((item) => (
                  <tr key={item.name}>
                    <td className="mono">{item.name}</td>
                    <td>
                      <StatusPill status={item.status} />
                    </td>
                    <td>{item.kind}</td>
                    <td className="mono">{item.path ?? "未配置"}</td>
                    <td>{item.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h3>覆盖摘要</h3>
          <ListBlock title="披露文件类型" values={report.manifest?.form_counts} />
          <ListBlock title="证据层级" values={report.manifest?.source_tier_counts} />
          <ListBlock title="市场快照字段" values={report.market_evidence?.field_counts} />
        </div>
      </div>
      <div className="readiness-columns">
        <MessageBlock title="Warnings" rows={report.warnings ?? []} status="warn" />
        <MessageBlock title="Errors" rows={report.errors ?? []} status="fail" />
      </div>
    </div>
  );
}

function EmptyReadiness() {
  return (
    <div className="readiness-layout empty-state">
      <div>
        <h3>没有 readiness 报告</h3>
        <p>点击“检查数据源”后，Workbench 会把缺失项、覆盖范围和市场快照字段列出来。</p>
      </div>
    </div>
  );
}

function ListBlock({ title, values }: { title: string; values?: Record<string, number | string> }) {
  const entries = Object.entries(values ?? {});
  return (
    <div className="list-block">
      <h3>{title}</h3>
      {entries.length ? (
        <ul>
          {entries.map(([key, value]) => (
            <li key={key}>
              <span className="mono">{key}</span>: {value}
            </li>
          ))}
        </ul>
      ) : (
        <p>无数据</p>
      )}
    </div>
  );
}

function MessageBlock({ title, rows, status }: { title: string; rows: string[]; status: Status }) {
  return (
    <div className="list-block">
      <h3>
        {title} <StatusPill status={rows.length ? status : "pass"} />
      </h3>
      {rows.length ? (
        <ul>
          {rows.map((row) => (
            <li key={row}>{row}</li>
          ))}
        </ul>
      ) : (
        <p>无</p>
      )}
    </div>
  );
}

function MetricBox({ label, value, detail }: { label: string; value?: string; detail?: string }) {
  return (
    <div className="metric-box">
      <div className="label">{label}</div>
      <div className="value">{value || "未配置"}</div>
      {detail ? <div className="mono">{detail}</div> : null}
    </div>
  );
}

function StatusPill({ status, label }: { status: Status; label?: string }) {
  return <span className={`status-pill ${status}`}>{label ?? statusLabel(status)}</span>;
}

function statusLabel(status: Status) {
  if (status === "pass") return "通过";
  if (status === "warn") return "警告";
  if (status === "fail") return "失败";
  return "未检查";
}

function jobStatus(job: RunJob | null): Status {
  if (!job) return "neutral";
  if (job.status === "completed") return "pass";
  if (job.status === "failed" || job.status === "cancelled") return "fail";
  if (job.status === "running" || job.status === "queued") return "warn";
  return "neutral";
}

function isTerminal(status: string) {
  return ["completed", "failed", "cancelled"].includes(status);
}

function listText(values?: number[]) {
  return values?.length ? values.join(", ") : "无";
}

function numberText(value?: number) {
  return Number(value ?? 0).toLocaleString("en-US");
}

function compactObject(value: Record<string, unknown>) {
  const entries = Object.entries(value ?? {});
  if (!entries.length) return "无";
  return entries
    .slice(0, 5)
    .map(([key, item]) => `${key}: ${Array.isArray(item) ? item.join(",") : String(item)}`)
    .join(" · ");
}

function flatSummary(value: Record<string, unknown>) {
  const result: Record<string, number> = {};
  for (const [key, item] of Object.entries(value ?? {})) {
    if (typeof item === "number") {
      result[key] = item;
    } else if (typeof item === "boolean") {
      result[key] = item ? 1 : 0;
    } else if (Array.isArray(item)) {
      result[key] = item.length;
    } else if (typeof item === "string" && item) {
      result[key] = 1;
    }
  }
  return result;
}

function listRecord(values?: string[]) {
  return Object.fromEntries((values ?? []).filter(Boolean).map((value) => [value, "yes"]));
}

function importPayload(form: FormState) {
  return {
    env_path: form.envPath.trim(),
    profile_id: form.profileId.trim() || null,
    display_name: form.displayName.trim() || null,
  };
}

function newSessionId() {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
  return `workbench_session_${stamp}`;
}

async function requestJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const detail = payload.detail ?? response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload as T;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
