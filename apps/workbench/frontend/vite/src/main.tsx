import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Database,
  FileSearch,
  FlaskConical,
  FolderOpen,
  FolderSearch,
  History,
  ListChecks,
  MessageSquareText,
  Play,
  RefreshCcw,
  Server,
  ShieldCheck,
  Terminal,
  Save,
  CircleStop,
  Trash2,
  Wrench,
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
  manifest_path?: string | null;
  bm25_index_dir?: string | null;
  object_bm25_index_dir?: string | null;
  source_gap_path?: string | null;
  market_evidence_path?: string | null;
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

type SourceBundleArtifacts = {
  manifest_path?: string | null;
  bm25_index_dir?: string | null;
  object_bm25_index_dir?: string | null;
  source_gap_path?: string | null;
  market_evidence_path?: string | null;
};

type SourceBundleBuild = {
  created_at: string;
  scripts?: string[];
  status: string;
};

type SourceBundle = {
  schema_version: string;
  bundle_id: string;
  display_name: string;
  market: string;
  coverage_theme: string;
  ticker_count: number;
  tickers_sample: string[];
  source_families: string[];
  as_of_date?: string | null;
  artifacts: SourceBundleArtifacts;
  build: SourceBundleBuild;
};

type StoredSourceBundle = {
  bundle_id: string;
  display_name: string;
  market: string;
  coverage_theme: string;
  ticker_count: number;
  as_of_date?: string | null;
  status: string;
  updated_at: string;
};

type DataBuildParameter = {
  name: string;
  flag: string;
  label: string;
  required: boolean;
  kind: string;
  default?: string | null;
  multiple: boolean;
  description?: string;
};

type DataBuildStep = {
  step_id: string;
  family: string;
  label: string;
  description: string;
  script: string;
  parameters: DataBuildParameter[];
  output_parameters: string[];
  timeout_hint_s: number;
};

type DataBuildPreview = {
  step_id: string;
  label: string;
  args: string[];
  cwd: string;
  missing_required: string[];
  bundle_artifact_updates: Record<string, string>;
  bundle_field_updates: Record<string, string>;
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
  trace_id?: string;
  profile_id?: string | null;
  prompt?: string | null;
  run_dir?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  elapsed_ms?: number | null;
  updated_at: string;
  error?: string;
  error_message?: string;
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

type RunStatusReport = {
  job_id: string;
  job_type: string;
  status: string;
  trace_id: string;
  profile_id?: string | null;
  run_dir?: string | null;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  elapsed_ms?: number | null;
  error_message?: string;
  is_terminal: boolean;
  event_count: number;
  latest_event?: RunLogEvent | null;
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
  trace_id?: string;
  stream: string;
  message: string;
  created_at: string;
};

type StoreHealthReport = {
  status: string;
  db_path: string;
  db_exists: boolean;
  db_parent_writable: boolean;
  db_size_bytes: number;
  schema_version: number;
  profile_count: number;
  source_bundle_count: number;
  run_job_count: number;
  run_event_count: number;
  error_message?: string;
};

type SystemStatusReport = {
  status: string;
  service: string;
  version: string;
  checks: Record<string, string>;
  store: StoreHealthReport;
  paths: Record<string, Record<string, unknown>>;
  runtime_limits: Record<string, unknown>;
  runtime_preflight: RuntimePreflightReport;
  deployment: WorkbenchDeploymentReport;
};

type RuntimePreflightReport = {
  status: string;
  missing_full_runtime_modules?: string[];
  control_plane_modules?: RuntimeModuleCheck[];
  full_runtime_modules?: RuntimeModuleCheck[];
  scripts?: RuntimeScriptCheck[];
};

type RuntimeModuleCheck = {
  name: string;
  available: boolean;
};

type RuntimeScriptCheck = {
  path: string;
  exists: boolean;
};

type UpdateInterfaceReport = {
  interface_id: string;
  category: string;
  method: string;
  endpoint: string;
  status: string;
  description: string;
  action_id?: string | null;
};

type WorkbenchDeploymentReport = {
  schema_version: string;
  service: string;
  status: string;
  runtime_profile: string;
  requested_runtime_profile: string;
  image_kind: string;
  release_id: string;
  full_runtime_ready: boolean;
  frontend_bundled: boolean;
  code_update_mode: string;
  data_update_mode: string;
  update_interface_version: string;
  immutable_roots: string[];
  mutable_roots: string[];
  path_policy_allowed_roots: string[];
  missing_full_runtime_modules: string[];
  update_interfaces: UpdateInterfaceReport[];
};

type MaintenanceAction = {
  action_id: string;
  category: string;
  label: string;
  description: string;
  enabled: boolean;
  status: string;
  timeout_hint_s: number;
  requires_full_runtime: boolean;
  command_preview: string[];
  output_contract: string;
};

type RunPruneReport = {
  dry_run: boolean;
  terminal_only: boolean;
  keep_latest: number;
  max_age_days?: number | null;
  candidate_job_ids: string[];
  deleted_job_count: number;
  deleted_event_count: number;
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
  const [systemStatus, setSystemStatus] = useState<SystemStatusReport | null>(null);
  const [deployment, setDeployment] = useState<WorkbenchDeploymentReport | null>(null);
  const [maintenanceActions, setMaintenanceActions] = useState<MaintenanceAction[]>([]);
  const [form, setForm] = useState<FormState>(initialForm);
  const [profile, setProfile] = useState<WorkbenchProfile | null>(null);
  const [profiles, setProfiles] = useState<StoredProfile[]>([]);
  const [sourceBundles, setSourceBundles] = useState<StoredSourceBundle[]>([]);
  const [sourceBundle, setSourceBundle] = useState<SourceBundle | null>(null);
  const [sourceBundleReadiness, setSourceBundleReadiness] = useState<ReadinessReport | null>(null);
  const [readiness, setReadiness] = useState<ReadinessReport | null>(null);
  const [runDir, setRunDir] = useState("reports/quality/<saved-run-dir>");
  const [runs, setRuns] = useState<RunJob[]>([]);
  const [runReport, setRunReport] = useState<RunInspectionReport | null>(null);
  const [nativeCheckpoint, setNativeCheckpoint] = useState<NativeCheckpointInspection | null>(null);
  const [sessions, setSessions] = useState<StoredSession[]>([]);
  const [sessionTurns, setSessionTurns] = useState<RunJob[]>([]);
  const [evals, setEvals] = useState<EvalRunner[]>([]);
  const [dataBuildSteps, setDataBuildSteps] = useState<DataBuildStep[]>([]);
  const [dataBuildStepId, setDataBuildStepId] = useState("");
  const [dataBuildValues, setDataBuildValues] = useState<Record<string, string | boolean>>({});
  const [dataBuildDryRun, setDataBuildDryRun] = useState(true);
  const [dataBuildUpdateBundle, setDataBuildUpdateBundle] = useState(false);
  const [dataBuildBundleId, setDataBuildBundleId] = useState("");
  const [dataBuildPreview, setDataBuildPreview] = useState<DataBuildPreview | null>(null);
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
  const [pruneKeepLatest, setPruneKeepLatest] = useState("200");
  const [prunePreview, setPrunePreview] = useState<RunPruneReport | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const artifactJumpJobIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    void loadSystemDashboard({ quiet: true });
    void loadSavedProfiles();
    void loadSourceBundles();
    void loadRuns();
    void loadSessions();
    void loadEvals();
    void loadDataBuildSteps();
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
  const selectedDataBuildStep = dataBuildSteps.find((step) => step.step_id === dataBuildStepId) ?? dataBuildSteps[0] ?? null;
  const latestMaintenanceRun = runs.find((run) => run.job_type === "maintenance") ?? null;

  async function loadSystemDashboard(options: { quiet?: boolean } = {}) {
    try {
      const [statusPayload, deploymentPayload, maintenancePayload] = await Promise.all([
        requestJson<SystemStatusReport>("/api/system/status"),
        requestJson<WorkbenchDeploymentReport>("/api/system/deployment"),
        requestJson<{ actions: MaintenanceAction[] }>("/api/system/maintenance/actions"),
      ]);
      setSystemStatus(statusPayload);
      setDeployment(deploymentPayload);
      setMaintenanceActions(maintenancePayload.actions ?? []);
      setHealth(statusPayload.status === "ok" ? "pass" : "warn");
    } catch (err) {
      setHealth("fail");
      if (!options.quiet) {
        throw err;
      }
    }
  }

  async function refreshSystemDashboard() {
    await runBusy("system_refresh", async () => {
      await loadSystemDashboard();
    });
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

  async function loadSourceBundles() {
    const payload = await requestJson<{ bundles: StoredSourceBundle[] }>("/api/source-bundles");
    setSourceBundles(payload.bundles ?? []);
  }

  async function importSourceBundleFromProfile() {
    await runBusy("source_bundle_import", async () => {
      const current =
        profile ??
        (await requestJson<WorkbenchProfile>("/api/profiles/import-env", {
          method: "POST",
          body: JSON.stringify(importPayload(form)),
        }));
      setProfile(current);
      const payload = await requestJson<{ bundle: SourceBundle; readiness: ReadinessReport }>("/api/source-bundles/import-profile", {
        method: "POST",
        body: JSON.stringify({
          profile: current,
          bundle_id: suggestedBundleId(current),
          repo_root: form.repoRoot || ".",
        }),
      });
      setSourceBundle(payload.bundle);
      setDataBuildBundleId(payload.bundle.bundle_id);
      setSourceBundleReadiness(payload.readiness);
      setReadiness(payload.readiness);
      await loadSourceBundles();
    });
  }

  async function loadSourceBundle(bundleId: string) {
    await runBusy(`source_bundle:${bundleId}`, async () => {
      const loaded = await requestJson<SourceBundle>(`/api/source-bundles/${encodeURIComponent(bundleId)}`);
      setSourceBundle(loaded);
      setDataBuildBundleId(loaded.bundle_id);
      await validateSourceBundle(loaded);
    });
  }

  async function validateSourceBundle(targetBundle = sourceBundle) {
    if (!targetBundle) return;
    await runBusy("source_bundle_validate", async () => {
      const payload = await requestJson<{ bundle: SourceBundle; readiness: ReadinessReport }>("/api/source-bundles/validate", {
        method: "POST",
        body: JSON.stringify({
          bundle: targetBundle,
          repo_root: form.repoRoot || ".",
        }),
      });
      setSourceBundle(payload.bundle);
      setSourceBundleReadiness(payload.readiness);
    });
  }

  async function loadRuns() {
    const payload = await requestJson<{ runs: RunJob[] }>("/api/runs");
    setRuns(payload.runs ?? []);
  }

  async function runMaintenanceAction(actionId: string) {
    await runBusy(`maintenance:${actionId}`, async () => {
      const payload = await requestJson<{ job: RunJob; action: MaintenanceAction }>("/api/system/maintenance/run", {
        method: "POST",
        body: JSON.stringify({ action_id: actionId }),
      });
      setActiveJob(payload.job);
      setJobEvents([]);
      await refreshJob(payload.job.job_id);
      await loadRuns();
      await loadSystemDashboard({ quiet: true });
    });
  }

  async function previewRunPrune() {
    await runBusy("runs_prune_preview", async () => {
      const payload = await requestJson<RunPruneReport>("/api/runs/prune", {
        method: "POST",
        body: JSON.stringify({
          keep_latest: normalizedKeepLatest(pruneKeepLatest),
          terminal_only: true,
          dry_run: true,
        }),
      });
      setPrunePreview(payload);
    });
  }

  async function executeRunPrune() {
    if (!prunePreview?.candidate_job_ids.length) return;
    if (!window.confirm(`确认裁剪 ${prunePreview.candidate_job_ids.length} 个终态任务记录？`)) return;
    await runBusy("runs_prune_execute", async () => {
      const payload = await requestJson<RunPruneReport>("/api/runs/prune", {
        method: "POST",
        body: JSON.stringify({
          keep_latest: normalizedKeepLatest(pruneKeepLatest),
          terminal_only: true,
          dry_run: false,
        }),
      });
      setPrunePreview(payload);
      await loadRuns();
    });
  }

  async function loadSessions() {
    const payload = await requestJson<{ sessions: StoredSession[] }>("/api/sessions");
    setSessions(payload.sessions ?? []);
  }

  async function loadEvals() {
    const payload = await requestJson<{ evals: EvalRunner[] }>("/api/evals");
    setEvals(payload.evals ?? []);
  }

  async function loadDataBuildSteps() {
    const payload = await requestJson<{ steps: DataBuildStep[] }>("/api/data-build/steps");
    const steps = payload.steps ?? [];
    setDataBuildSteps(steps);
    setDataBuildStepId((current) => current || steps[0]?.step_id || "");
  }

  async function previewDataBuild() {
    if (!selectedDataBuildStep) return;
    await runBusy("data_build_preview", async () => {
      const payload = await requestJson<{ preview: DataBuildPreview }>("/api/data-build/preview", {
        method: "POST",
        body: JSON.stringify(dataBuildRequestPayload(selectedDataBuildStep, dataBuildValues, profile, dataBuildDryRun, dataBuildBundleId, sourceBundle, dataBuildUpdateBundle)),
      });
      setDataBuildPreview(payload.preview);
    });
  }

  async function runDataBuild() {
    if (!selectedDataBuildStep) return;
    await runBusy("data_build_run", async () => {
      const payload = await requestJson<{ job: RunJob; preview: DataBuildPreview }>("/api/data-build/run", {
        method: "POST",
        body: JSON.stringify(dataBuildRequestPayload(selectedDataBuildStep, dataBuildValues, profile, dataBuildDryRun, dataBuildBundleId, sourceBundle, dataBuildUpdateBundle)),
      });
      setDataBuildPreview(payload.preview);
      setActiveJob(payload.job);
      setJobEvents([]);
      await refreshJob(payload.job.job_id);
      await loadRuns();
    });
  }

  function applyDataBuildDefaults() {
    if (!selectedDataBuildStep) return;
    setDataBuildValues((current) => suggestDataBuildValues(selectedDataBuildStep, current, profile, sourceBundle, dataBuildBundleId));
    setDataBuildPreview(null);
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
    const status = await requestJson<RunStatusReport>(`/api/runs/${encodeURIComponent(jobId)}/status`);
    setActiveJob((current) => mergeStatusIntoJob(status, current));
    await loadJobEvents(jobId);
    if (status.run_dir) {
      setRunDir(status.run_dir);
    }
    if (status.is_terminal) {
      const payload = await requestJson<RunInspectionReport>(`/api/runs/${encodeURIComponent(jobId)}`);
      setActiveJob(payload.job);
      if (payload.artifact_index) {
        setRunReport(payload as RunInspectionReport);
      }
      if (payload.native_checkpoint !== undefined) {
        setNativeCheckpoint(payload.native_checkpoint ?? null);
      }
      if (payload.job.run_dir) {
        setRunDir(payload.job.run_dir);
      }
      await loadRuns();
      await loadSessions();
      if (payload.artifact_index && !artifactJumpJobIds.current.has(payload.job.job_id)) {
        artifactJumpJobIds.current.add(payload.job.job_id);
        window.setTimeout(() => document.getElementById("artifacts")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
      }
    }
  }

  async function cancelActiveJob() {
    if (!activeJob?.job_id || isTerminal(activeJob.status)) return;
    await runBusy("cancel_job", async () => {
      const payload = await requestJson<{ cancelled: boolean; status: string; message: string; job?: RunJob | null }>(
        `/api/runs/${encodeURIComponent(activeJob.job_id)}/cancel`,
        {
          method: "POST",
          body: JSON.stringify({ reason: "cancelled from workbench" }),
        },
      );
      if (payload.job) {
        setActiveJob(payload.job);
      }
      await loadJobEvents(activeJob.job_id);
      await loadRuns();
    });
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
      { label: "运行态", icon: Activity, href: "#runtime", active: true },
      { label: "数据源配置", icon: FolderOpen, href: "#profile", active: false },
      { label: "数据包", icon: Database, href: "#source-bundles", active: false },
      { label: "数据构建", icon: Terminal, href: "#data-build", active: false },
      { label: "数据源检查", icon: FileSearch, href: "#readiness", active: false },
      { label: "Agent 会话", icon: MessageSquareText, href: "#agent", active: false },
      { label: "任务中心", icon: ListChecks, href: "#jobs", active: false },
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
            <p>配置研究数据源，检查证据产物，并为后续 Agent 会话准备可复用运行配置。</p>
          </div>
          <div className="topbar-actions">
            <button type="button" className="icon-button" onClick={refreshSystemDashboard} disabled={Boolean(busy)} aria-label="刷新系统状态">
              <RefreshCcw size={16} aria-hidden="true" />
            </button>
            <StatusPill status={health} label={health === "pass" ? "已连接" : "未连接"} />
          </div>
        </header>

        <section id="runtime" className="panel">
          <div className="section-heading">
            <div>
              <h2>运行态总览</h2>
              <p>确认当前镜像、依赖、前端 bundle、可写目录和未来更新接口是否处在可上线状态。</p>
            </div>
            <StatusPill status={statusFromString(systemStatus?.status)} label={systemStatus?.status ?? "未知"} />
          </div>
          <SystemOverview
            systemStatus={systemStatus}
            deployment={deployment}
            maintenanceActions={maintenanceActions}
            latestMaintenanceRun={latestMaintenanceRun}
            busy={busy}
            onRefresh={refreshSystemDashboard}
            onRunMaintenance={runMaintenanceAction}
          />
        </section>

        <section id="profile" className="panel">
          <div className="section-heading">
            <div>
              <h2>运行配置导入</h2>
              <p>导入现有 `.env` 运行配置。Workbench 只保存环境变量名，不保存真实 API key。</p>
            </div>
          </div>

          <div className="profile-form">
            <TextInput label="配置文件" value={form.envPath} onChange={(envPath) => setForm({ ...form, envPath })} />
            <TextInput label="配置 ID" value={form.profileId} onChange={(profileId) => setForm({ ...form, profileId })} />
            <TextInput label="显示名称" value={form.displayName} onChange={(displayName) => setForm({ ...form, displayName })} />
            <TextInput label="仓库根目录" value={form.repoRoot} onChange={(repoRoot) => setForm({ ...form, repoRoot })} />
            <div className="form-actions">
              <button type="button" onClick={importProfile} disabled={Boolean(busy)}>
                <FolderOpen size={16} aria-hidden="true" />
                {busy === "import" ? "导入中" : "导入运行配置"}
              </button>
              <button type="button" className="secondary" onClick={saveProfile} disabled={Boolean(busy)}>
                <Save size={16} aria-hidden="true" />
                {busy === "save" ? "保存中" : "保存运行配置"}
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
              <MetricBox label="运行配置" value={profile.display_name} detail={profile.profile_id} />
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

        <section id="source-bundles" className="panel">
          <div className="section-heading">
            <div>
              <h2>数据包</h2>
              <p>把运行配置里的长路径整理成可读的数据包，后续运行时只需要选择数据包，不需要记住每个文件名。</p>
            </div>
            <StatusPill status={sourceBundleReadiness?.status ?? "neutral"} />
          </div>

          <div className="form-actions">
            <button type="button" onClick={importSourceBundleFromProfile} disabled={Boolean(busy)}>
              <Database size={16} aria-hidden="true" />
              {busy === "source_bundle_import" ? "生成中" : "从当前配置生成数据包"}
            </button>
            <button type="button" className="secondary" onClick={() => validateSourceBundle()} disabled={Boolean(busy) || !sourceBundle}>
              <FileSearch size={16} aria-hidden="true" />
              {busy === "source_bundle_validate" ? "校验中" : "校验当前数据包"}
            </button>
          </div>

          <SavedSourceBundles bundles={sourceBundles} onLoad={loadSourceBundle} />
          {sourceBundle ? (
            <SourceBundlePanel bundle={sourceBundle} readiness={sourceBundleReadiness} />
          ) : (
            <div className="summary-grid empty-state">
              <div>
                <h3>还没有选择数据包</h3>
                <p>导入运行配置后，可以一键生成数据包；也可以从已保存数据包中重新加载。</p>
              </div>
            </div>
          )}
        </section>

        <section id="data-build" className="panel">
          <div className="section-heading">
            <div>
              <h2>数据构建</h2>
              <p>通过白名单步骤运行 SEC / 8-K 下载和本地处理脚本。先预览命令，再提交后台任务。</p>
            </div>
          </div>
          <DataBuildPanel
            steps={dataBuildSteps}
            selectedStep={selectedDataBuildStep}
            selectedStepId={dataBuildStepId}
            values={dataBuildValues}
            dryRun={dataBuildDryRun}
            updateBundle={dataBuildUpdateBundle}
            bundleId={dataBuildBundleId}
            bundles={sourceBundles}
            preview={dataBuildPreview}
            busy={busy}
            onSelectStep={(stepId) => {
              setDataBuildStepId(stepId);
              setDataBuildPreview(null);
            }}
            onChangeValue={(name, value) => {
              setDataBuildValues((current) => ({ ...current, [name]: value }));
              setDataBuildPreview(null);
            }}
            onDryRunChange={setDataBuildDryRun}
            onUpdateBundleChange={setDataBuildUpdateBundle}
            onBundleIdChange={setDataBuildBundleId}
            onApplyDefaults={applyDataBuildDefaults}
            onPreview={previewDataBuild}
            onRun={runDataBuild}
          />
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

          <JobConsole job={activeJob} events={jobEvents} onCancel={cancelActiveJob} cancelling={busy === "cancel_job"} />
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

        <section id="jobs" className="panel">
          <div className="section-heading">
            <div>
              <h2>任务中心</h2>
              <p>集中查看后台任务、载入日志、刷新状态，并在 dry-run 后裁剪终态历史。</p>
            </div>
            <StatusPill status={jobStatus(activeJob)} label={activeJob?.status ?? "未启动"} />
          </div>
          <TaskCenter
            runs={runs}
            activeJob={activeJob}
            busy={busy}
            pruneKeepLatest={pruneKeepLatest}
            prunePreview={prunePreview}
            onLoadRun={loadRun}
            onRefresh={loadRuns}
            onPruneKeepLatestChange={setPruneKeepLatest}
            onPreviewPrune={previewRunPrune}
            onExecutePrune={executeRunPrune}
          />
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

function SystemOverview({
  systemStatus,
  deployment,
  maintenanceActions,
  latestMaintenanceRun,
  busy,
  onRefresh,
  onRunMaintenance,
}: {
  systemStatus: SystemStatusReport | null;
  deployment: WorkbenchDeploymentReport | null;
  maintenanceActions: MaintenanceAction[];
  latestMaintenanceRun: RunJob | null;
  busy: string | null;
  onRefresh: () => void;
  onRunMaintenance: (actionId: string) => void;
}) {
  if (!systemStatus || !deployment) {
    return (
      <div className="summary-grid empty-state">
        <div>
          <h3>等待系统状态</h3>
          <p>Workbench 正在读取后端运行态、部署配置和维护动作目录。</p>
        </div>
      </div>
    );
  }
  const runtimePreflight = systemStatus.runtime_preflight;
  const missingModules = deployment.missing_full_runtime_modules ?? runtimePreflight.missing_full_runtime_modules ?? [];
  return (
    <div className="runtime-layout">
      <div className="summary-grid runtime-summary">
        <MetricBox label="服务状态" value={systemStatus.status} detail={`${systemStatus.service} · ${systemStatus.version}`} />
        <MetricBox label="运行 profile" value={deployment.runtime_profile} detail={`requested: ${deployment.requested_runtime_profile}`} />
        <MetricBox label="镜像类型" value={deployment.image_kind} detail={deployment.release_id} />
        <MetricBox label="完整 runtime" value={boolText(deployment.full_runtime_ready)} detail={missingModules.length ? missingModules.join(", ") : "依赖完整"} />
        <MetricBox label="前端 bundle" value={boolText(deployment.frontend_bundled)} detail={deployment.frontend_bundled ? "dist 已打入镜像" : "使用静态 fallback"} />
        <MetricBox label="Store" value={systemStatus.store.status} detail={`${systemStatus.store.run_job_count} jobs · ${systemStatus.store.run_event_count} events`} />
      </div>

      <div className="runtime-columns">
        <div>
          <div className="inline-heading">
            <h3>
              <ShieldCheck size={15} aria-hidden="true" />
              系统检查
            </h3>
            <button type="button" className="icon-button" onClick={onRefresh} disabled={Boolean(busy)} aria-label="刷新系统检查">
              <RefreshCcw size={15} aria-hidden="true" />
            </button>
          </div>
          <div className="check-list">
            {Object.entries(systemStatus.checks).map(([name, value]) => (
              <div className="check-item" key={name}>
                <span className="mono">{name}</span>
                <StatusPill status={statusFromString(value)} label={value} />
              </div>
            ))}
          </div>
        </div>
        <div>
          <h3>
            <Server size={15} aria-hidden="true" />
            更新边界
          </h3>
          <div className="summary-grid compact-summary">
            <MetricBox label="脚本更新" value={deployment.code_update_mode} />
            <MetricBox label="数据更新" value={deployment.data_update_mode} />
            <MetricBox label="接口版本" value={deployment.update_interface_version} />
          </div>
          <div className="root-lists">
            <ListBlock title="可写目录" values={listRecord(deployment.mutable_roots)} />
            <ListBlock title="镜像内只读目录" values={listRecord(deployment.immutable_roots)} />
          </div>
        </div>
      </div>

      <div className="runtime-columns">
        <MaintenanceActions actions={maintenanceActions} latestRun={latestMaintenanceRun} busy={busy} onRun={onRunMaintenance} />
        <UpdateInterfaces interfaces={deployment.update_interfaces} />
      </div>
    </div>
  );
}

function MaintenanceActions({
  actions,
  latestRun,
  busy,
  onRun,
}: {
  actions: MaintenanceAction[];
  latestRun: RunJob | null;
  busy: string | null;
  onRun: (actionId: string) => void;
}) {
  return (
    <div>
      <h3>
        <Wrench size={15} aria-hidden="true" />
        维护动作
      </h3>
      {latestRun ? (
        <div className="maintenance-run-status">
          <span className="maintenance-run-title">
            <span className="mono">{latestRun.job_id}</span>
            <StatusPill status={jobStatus(latestRun)} label={latestRun.status} />
          </span>
          <span className="maintenance-run-meta">
            <span>{latestRun.job_type}</span>
            <span className="mono">{latestRun.trace_id || "no trace"}</span>
            <span>{latestRun.elapsed_ms !== undefined && latestRun.elapsed_ms !== null ? `${latestRun.elapsed_ms} ms` : "running"}</span>
          </span>
        </div>
      ) : null}
      {actions.length ? (
        <div className="maintenance-list">
          {actions.map((action) => {
            const isBusy = busy === `maintenance:${action.action_id}`;
            return (
              <button
                className="maintenance-action"
                type="button"
                onClick={() => onRun(action.action_id)}
                disabled={Boolean(busy) || !action.enabled}
                key={action.action_id}
              >
                <span className="maintenance-title">
                  {isBusy ? "运行中" : action.label}
                  <StatusPill status={statusFromString(action.status)} label={action.status} />
                </span>
                <span>{action.description}</span>
                <span className="mono">
                  {action.enabled ? `timeout ${action.timeout_hint_s}s` : "reserved"}
                  {action.command_preview.length ? ` · ${commandLine(action.command_preview)}` : ""}
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <p className="muted-text">后端没有返回维护动作目录。</p>
      )}
    </div>
  );
}

function UpdateInterfaces({ interfaces }: { interfaces: UpdateInterfaceReport[] }) {
  return (
    <div>
      <h3>
        <ListChecks size={15} aria-hidden="true" />
        更新接口
      </h3>
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>接口</th>
              <th>类别</th>
              <th>状态</th>
              <th>Endpoint</th>
            </tr>
          </thead>
          <tbody>
            {interfaces.map((item) => (
              <tr key={item.interface_id}>
                <td>
                  <div className="mono">{item.interface_id}</div>
                  <div>{item.description}</div>
                </td>
                <td>{item.category}</td>
                <td>
                  <StatusPill status={statusFromString(item.status)} label={item.status} />
                </td>
                <td className="mono">
                  {item.method} {item.endpoint}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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

function TaskCenter({
  runs,
  activeJob,
  busy,
  pruneKeepLatest,
  prunePreview,
  onLoadRun,
  onRefresh,
  onPruneKeepLatestChange,
  onPreviewPrune,
  onExecutePrune,
}: {
  runs: RunJob[];
  activeJob: RunJob | null;
  busy: string | null;
  pruneKeepLatest: string;
  prunePreview: RunPruneReport | null;
  onLoadRun: (jobId: string) => void;
  onRefresh: () => void;
  onPruneKeepLatestChange: (value: string) => void;
  onPreviewPrune: () => void;
  onExecutePrune: () => void;
}) {
  const activeRuns = runs.filter((run) => !isTerminal(run.status));
  const failedRuns = runs.filter((run) => ["failed", "timed_out", "interrupted"].includes(run.status));
  const latestRuns = runs.slice(0, 14);
  return (
    <div className="task-center">
      <div className="summary-grid">
        <MetricBox label="任务总数" value={String(runs.length)} detail={`${activeRuns.length} active`} />
        <MetricBox label="失败/中断" value={String(failedRuns.length)} detail="failed · timed_out · interrupted" />
        <MetricBox label="当前任务" value={activeJob?.job_id ?? "未选择"} detail={activeJob ? `${activeJob.job_type} · ${activeJob.status}` : ""} />
      </div>

      <div className="task-toolbar">
        <button type="button" className="secondary" onClick={onRefresh} disabled={Boolean(busy)}>
          <RefreshCcw size={16} aria-hidden="true" />
          刷新任务
        </button>
        <label className="inline-input">
          <span>保留最近</span>
          <input value={pruneKeepLatest} onChange={(event) => onPruneKeepLatestChange(event.target.value)} inputMode="numeric" />
        </label>
        <button type="button" className="secondary" onClick={onPreviewPrune} disabled={Boolean(busy)}>
          <Trash2 size={16} aria-hidden="true" />
          {busy === "runs_prune_preview" ? "预览中" : "裁剪 dry-run"}
        </button>
        <button
          type="button"
          onClick={onExecutePrune}
          disabled={Boolean(busy) || !prunePreview?.candidate_job_ids.length || prunePreview.dry_run === false}
        >
          <Trash2 size={16} aria-hidden="true" />
          {busy === "runs_prune_execute" ? "裁剪中" : "执行裁剪"}
        </button>
        {prunePreview ? (
          <span className="mono task-prune-status">
            {prunePreview.dry_run ? "dry-run" : "done"} · candidates {prunePreview.candidate_job_ids.length} · deleted jobs {prunePreview.deleted_job_count}
          </span>
        ) : null}
      </div>

      {latestRuns.length ? (
        <div className="table-wrap task-table">
          <table>
            <thead>
              <tr>
                <th>任务</th>
                <th>状态</th>
                <th>Trace</th>
                <th>耗时</th>
                <th>Run dir</th>
              </tr>
            </thead>
            <tbody>
              {latestRuns.map((job) => (
                <tr key={job.job_id}>
                  <td>
                    <button className="table-link" type="button" onClick={() => onLoadRun(job.job_id)}>
                      {job.job_id}
                    </button>
                    <div>{job.job_type}</div>
                  </td>
                  <td>
                    <StatusPill status={jobStatus(job)} label={job.status} />
                  </td>
                  <td className="mono">{job.trace_id || "none"}</td>
                  <td>{job.elapsed_ms !== undefined && job.elapsed_ms !== null ? `${job.elapsed_ms} ms` : "running"}</td>
                  <td className="mono">{job.run_dir ?? "未记录"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="summary-grid empty-state">
          <div>
            <h3>还没有任务历史</h3>
            <p>运行 smoke、维护动作、数据构建或 Agent 后，任务会出现在这里。</p>
          </div>
        </div>
      )}
    </div>
  );
}

function SavedProfiles({ profiles, onLoad }: { profiles: StoredProfile[]; onLoad: (profileId: string) => void }) {
  if (!profiles.length) {
    return (
      <div className="saved-profiles empty-state">
        <h3>已保存运行配置</h3>
        <p>还没有保存过运行配置。</p>
      </div>
    );
  }
  return (
    <div className="saved-profiles">
      <h3>已保存运行配置</h3>
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

function SavedSourceBundles({
  bundles,
  onLoad,
}: {
  bundles: StoredSourceBundle[];
  onLoad: (bundleId: string) => void;
}) {
  if (!bundles.length) {
    return (
      <div className="saved-profiles empty-state">
        <h3>已保存数据包</h3>
        <p>还没有保存过数据包。</p>
      </div>
    );
  }
  return (
    <div className="saved-profiles">
      <h3>已保存数据包</h3>
      <div className="saved-profile-list">
        {bundles.map((bundle) => (
          <button className="saved-profile-button" type="button" onClick={() => onLoad(bundle.bundle_id)} key={bundle.bundle_id}>
            {bundle.display_name || bundle.bundle_id}
            <span>
              {bundle.market} · {bundle.ticker_count}家公司 · {bundle.as_of_date ?? "日期未记录"} · {bundle.status}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function SourceBundlePanel({ bundle, readiness }: { bundle: SourceBundle; readiness: ReadinessReport | null }) {
  return (
    <div className="readiness-layout">
      <div className="summary-grid">
        <MetricBox label="数据包" value={bundle.display_name} detail={bundle.bundle_id} />
        <MetricBox label="覆盖范围" value={`${bundle.market} · ${bundle.ticker_count} 家公司`} detail={bundle.coverage_theme} />
        <MetricBox label="截至日期" value={bundle.as_of_date ?? "未记录"} detail={bundle.build.status} />
      </div>
      <div className="readiness-columns">
        <div>
          <h3>来源组合</h3>
          <ListBlock title="数据来源" values={listRecord(bundle.source_families)} />
          <ListBlock title="股票样例" values={listRecord(bundle.tickers_sample)} />
          <ListBlock title="构建脚本" values={listRecord(bundle.build.scripts ?? [])} />
        </div>
        <div>
          <h3>产物路径</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>产物</th>
                  <th>路径</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(bundle.artifacts).map(([name, path]) => (
                  <tr key={name}>
                    <td className="mono">{name}</td>
                    <td className="mono">{path || "未配置"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      {readiness ? (
        <div className="readiness-columns">
          <MessageBlock title="数据包警告" rows={readiness.warnings ?? []} status="warn" />
          <MessageBlock title="数据包错误" rows={readiness.errors ?? []} status="fail" />
        </div>
      ) : null}
    </div>
  );
}

function DataBuildPanel({
  steps,
  selectedStep,
  selectedStepId,
  values,
  dryRun,
  updateBundle,
  bundleId,
  bundles,
  preview,
  busy,
  onSelectStep,
  onChangeValue,
  onDryRunChange,
  onUpdateBundleChange,
  onBundleIdChange,
  onApplyDefaults,
  onPreview,
  onRun,
}: {
  steps: DataBuildStep[];
  selectedStep: DataBuildStep | null;
  selectedStepId: string;
  values: Record<string, string | boolean>;
  dryRun: boolean;
  updateBundle: boolean;
  bundleId: string;
  bundles: StoredSourceBundle[];
  preview: DataBuildPreview | null;
  busy: string | null;
  onSelectStep: (stepId: string) => void;
  onChangeValue: (name: string, value: string | boolean) => void;
  onDryRunChange: (value: boolean) => void;
  onUpdateBundleChange: (value: boolean) => void;
  onBundleIdChange: (value: string) => void;
  onApplyDefaults: () => void;
  onPreview: () => void;
  onRun: () => void;
}) {
  if (!steps.length || !selectedStep) {
    return (
      <div className="summary-grid empty-state">
        <div>
          <h3>没有可用构建步骤</h3>
          <p>后端没有返回数据构建白名单。</p>
        </div>
      </div>
    );
  }
  const supportsDryRun = selectedStep.step_id === "sec_download_filings" || selectedStep.step_id === "sec_download_8k_earnings";
  return (
    <div className="readiness-layout">
      <div className="data-build-grid">
        <label>
          <span>构建步骤</span>
          <select value={selectedStepId} onChange={(event) => onSelectStep(event.target.value)}>
            {steps.map((step) => (
              <option value={step.step_id} key={step.step_id}>
                {step.family} · {step.label}
              </option>
            ))}
          </select>
        </label>
        <MetricBox label="脚本" value={selectedStep.script} detail={`预计 ${selectedStep.timeout_hint_s}s 内`} />
      </div>
      <p className="muted-text">{selectedStep.description}</p>
      <div className="form-actions compact-actions">
        <button type="button" className="secondary" onClick={onApplyDefaults} disabled={Boolean(busy)}>
          <FolderOpen size={16} aria-hidden="true" />
          填入建议路径
        </button>
      </div>
      <div className="data-build-params">
        {selectedStep.parameters.map((parameter) =>
          parameter.kind === "bool" ? (
            <label className="check-row" key={parameter.name}>
              <input
                type="checkbox"
                checked={Boolean(values[parameter.name] ?? false)}
                onChange={(event) => onChangeValue(parameter.name, event.target.checked)}
              />
              <span>
                {parameter.label}
                {parameter.required ? " *" : ""}
              </span>
            </label>
          ) : (
            <label key={parameter.name}>
              <span>
                {parameter.label}
                {parameter.required ? " *" : ""}
              </span>
              <input
                value={String(values[parameter.name] ?? parameter.default ?? "")}
                onChange={(event) => onChangeValue(parameter.name, event.target.value)}
                placeholder={parameter.flag}
                autoComplete="off"
              />
            </label>
          ),
        )}
      </div>
      <label className="check-row">
        <input type="checkbox" checked={dryRun} disabled={!supportsDryRun} onChange={(event) => onDryRunChange(event.target.checked)} />
        <span>{supportsDryRun ? "下载步骤先 dry-run 预演" : "当前步骤不支持 dry-run"}</span>
      </label>
      <div className="data-build-grid">
        <label className="check-row">
          <input type="checkbox" checked={updateBundle} disabled={dryRun} onChange={(event) => onUpdateBundleChange(event.target.checked)} />
          <span>{dryRun ? "dry-run 不回填数据包" : "任务成功后回填数据包"}</span>
        </label>
        <label>
          <span>回填目标数据包</span>
          <select value={bundleId} onChange={(event) => onBundleIdChange(event.target.value)} disabled={!updateBundle || dryRun}>
            <option value="">不绑定数据包</option>
            {bundles.map((bundle) => (
              <option value={bundle.bundle_id} key={bundle.bundle_id}>
                {bundle.display_name || bundle.bundle_id}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="form-actions">
        <button type="button" className="secondary" onClick={onPreview} disabled={Boolean(busy)}>
          <Terminal size={16} aria-hidden="true" />
          {busy === "data_build_preview" ? "预览中" : "预览命令"}
        </button>
        <button type="button" onClick={onRun} disabled={Boolean(busy)}>
          <Play size={16} aria-hidden="true" />
          {busy === "data_build_run" ? "提交中" : "提交后台任务"}
        </button>
      </div>
      {preview ? (
        <div className="job-console data-build-preview">
          <div className="job-console-header">
            <h3>命令预览</h3>
            <span className="mono">{preview.label}</span>
          </div>
          <pre>{commandLine(preview.args)}</pre>
          {Object.keys(preview.bundle_artifact_updates ?? {}).length || Object.keys(preview.bundle_field_updates ?? {}).length ? (
            <p className="job-summary">
              可回填数据包：{compactObject({ ...preview.bundle_artifact_updates, ...preview.bundle_field_updates })}
            </p>
          ) : null}
          {preview.missing_required.length ? (
            <p className="job-error">缺少必填参数：{preview.missing_required.join(", ")}</p>
          ) : null}
        </div>
      ) : null}
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

function JobConsole({
  job,
  events,
  onCancel,
  cancelling,
}: {
  job: RunJob | null;
  events: RunLogEvent[];
  onCancel: () => void;
  cancelling: boolean;
}) {
  const evalSummary = job?.metadata?.eval_summary as Record<string, unknown> | undefined;
  const canCancel = Boolean(job?.job_id && !isTerminal(job.status));
  return (
    <div className="job-console">
      <div className="job-console-header">
        <div>
          <h3>运行日志</h3>
          {job ? (
            <span className="mono">
              {job.job_id} · {job.job_type} · {job.status}
            </span>
          ) : (
            <span className="mono">尚未启动</span>
          )}
        </div>
        <button type="button" className="secondary" onClick={onCancel} disabled={!canCancel || cancelling}>
          <CircleStop size={16} aria-hidden="true" />
          {cancelling ? "取消中" : "取消运行"}
        </button>
      </div>
      {job ? (
        <div className="job-meta-grid">
          <MetricBox label="Trace" value={job.trace_id || "none"} />
          <MetricBox label="Elapsed" value={job.elapsed_ms !== undefined && job.elapsed_ms !== null ? `${job.elapsed_ms} ms` : "running"} />
          <MetricBox label="Events" value={String(events.length)} />
        </div>
      ) : null}
      <pre>
        {events.length
          ? events.map((event) => `[${event.sequence}] ${event.trace_id ? `${event.trace_id} ` : ""}${event.stream}: ${event.message}`).join("\n")
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
      {job?.error_message || job?.error ? <p className="job-error">{job.error_message || job.error}</p> : null}
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

function statusFromString(value?: string | null): Status {
  const normalized = String(value ?? "").toLowerCase();
  if (["ok", "pass", "passed", "available", "completed", "healthy", "true"].includes(normalized)) return "pass";
  if (["warn", "warning", "degraded", "queued", "running", "reserved", "pending"].includes(normalized)) return "warn";
  if (["fail", "failed", "missing", "not_writable", "interrupted", "timed_out", "false", "unhealthy"].includes(normalized)) return "fail";
  return "neutral";
}

function jobStatus(job: RunJob | null): Status {
  if (!job) return "neutral";
  if (job.status === "completed") return "pass";
  if (["failed", "cancelled", "interrupted", "timed_out"].includes(job.status)) return "fail";
  if (job.status === "running" || job.status === "queued") return "warn";
  return "neutral";
}

function isTerminal(status: string) {
  return ["completed", "failed", "cancelled", "interrupted", "timed_out"].includes(status);
}

function boolText(value: boolean) {
  return value ? "yes" : "no";
}

function normalizedKeepLatest(value: string) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return 200;
  return Math.max(0, Math.min(10000, parsed));
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

function commandLine(args: string[]) {
  return args.map((arg) => (/[\s"'$]/.test(arg) ? JSON.stringify(arg) : arg)).join(" ");
}

function dataBuildRequestPayload(
  step: DataBuildStep,
  values: Record<string, string | boolean>,
  profile: WorkbenchProfile | null,
  dryRun: boolean,
  bundleId: string,
  sourceBundle: SourceBundle | null,
  updateBundle: boolean,
) {
  return {
    step_id: step.step_id,
    values,
    profile: profile ?? null,
    dry_run: dryRun,
    bundle_id: bundleId || sourceBundle?.bundle_id || null,
    update_bundle: updateBundle,
  };
}

function suggestDataBuildValues(
  step: DataBuildStep,
  current: Record<string, string | boolean>,
  profile: WorkbenchProfile | null,
  sourceBundle: SourceBundle | null,
  bundleId: string,
) {
  const next = { ...current };
  const artifacts: SourceBundleArtifacts & Partial<SourceProfile> = sourceBundle?.artifacts ?? profile?.sources ?? {};
  const baseId = pathSlug(bundleId || sourceBundle?.bundle_id || profile?.sources?.market_snapshot_id || profile?.profile_id || "workbench");
  const snapshotId = profile?.sources?.market_snapshot_id || sourceBundle?.bundle_id || baseId;
  const asOfDate = sourceBundle?.as_of_date || profile?.sources?.market_as_of_date || "";
  const inputDefaults: Record<string, string | undefined | null> = {
    manifest: artifacts.manifest_path,
    manifest_paths: artifacts.manifest_path,
    snapshot_id: snapshotId,
    as_of_date: asOfDate,
  };

  for (const parameter of step.parameters) {
    if (!isBlankValue(next[parameter.name])) continue;
    const inputDefault = inputDefaults[parameter.name];
    if (!isBlankValue(inputDefault)) {
      next[parameter.name] = String(inputDefault);
      continue;
    }
    if (step.output_parameters.includes(parameter.name)) {
      next[parameter.name] = suggestedOutputPath(step.step_id, parameter.name, baseId);
    }
  }
  return next;
}

function suggestedOutputPath(stepId: string, parameterName: string, baseId: string) {
  const base = `data/workbench_private/builds/${baseId}/${stepId}`;
  if (parameterName === "output_dir" || parameterName === "output_root") return base;
  const fileNames: Record<string, Record<string, string>> = {
    sec_build_manifest: { output: "sec_manifest.jsonl" },
    sec_build_chunks: { output: "sec_chunks.jsonl" },
    sec_build_evidence_store: { output: "sec_evidence_store.jsonl" },
    sec_download_8k_earnings: { missing_output: "sec_8k_missing.jsonl" },
    sec_build_8k_manifest: { output: "sec_8k_manifest.jsonl", gap_output: "sec_8k_gaps.jsonl" },
    sec_merge_source_gaps: { output: "source_gaps.jsonl" },
    market_build_events: { output: "market_events.jsonl" },
    market_enrich_valuation_fmp: { output: "market_valuation.csv" },
    market_build_catalog: { catalog_path: "market_snapshot_catalog.duckdb" },
    market_compute_analytics: { output: "market_analytics.jsonl" },
    market_build_evidence_pack: { output: "market_evidence_pack.jsonl" },
    market_validate_snapshot: { report: "market_validation_report.json" },
  };
  const fileName = fileNames[stepId]?.[parameterName] ?? `${parameterName}.json`;
  return `${base}/${fileName}`;
}

function pathSlug(value: string) {
  return (
    value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_.-]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^[_\-.]+|[_\-.]+$/g, "") || "workbench"
  );
}

function isBlankValue(value: unknown) {
  return value === undefined || value === null || (typeof value === "string" && value.trim() === "");
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

function suggestedBundleId(profile: WorkbenchProfile) {
  const source = profile.sources?.market_snapshot_id || profile.profile_id || "source_bundle";
  return source
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^[_\-.]+|[_\-.]+$/g, "") || "source_bundle";
}

function newSessionId() {
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
  return `workbench_session_${stamp}`;
}

function mergeStatusIntoJob(status: RunStatusReport, current: RunJob | null): RunJob {
  return {
    ...(current ?? {}),
    job_id: status.job_id,
    job_type: status.job_type,
    status: status.status,
    trace_id: status.trace_id,
    profile_id: status.profile_id ?? current?.profile_id ?? null,
    run_dir: status.run_dir ?? current?.run_dir ?? null,
    started_at: status.started_at ?? current?.started_at ?? null,
    finished_at: status.finished_at ?? current?.finished_at ?? null,
    elapsed_ms: status.elapsed_ms ?? current?.elapsed_ms ?? null,
    updated_at: status.updated_at,
    error_message: status.error_message ?? current?.error_message ?? "",
    error: status.error_message ?? current?.error ?? "",
    metadata: current?.metadata ?? {},
  };
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
    const error = payload.error ?? {};
    const suffix = [error.error_code, error.trace_id].filter(Boolean).join(" · ");
    const message = typeof detail === "string" ? detail : JSON.stringify(detail);
    throw new Error(suffix ? `${message} · ${suffix}` : message);
  }
  return payload as T;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
