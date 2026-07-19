import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Check,
  Clock3,
  Download,
  FileCheck2,
  Fingerprint,
  Play,
  RefreshCcw,
  ShieldCheck,
  Square,
  UserCheck,
} from "lucide-react";

import {
  AnalystBaselineSubmission,
  HumanBaselineApiClient,
  HumanBaselineApiError,
  HumanBaselineSession,
  SeniorReviewSubmission,
} from "../../api/humanBaseline";
import { useWorkbenchLocale } from "../../i18n/WorkbenchLocale";
import { RemoteStatus } from "../../shared/RemoteStatus";

type HumanBaselineProps = {
  caseId: string;
  online: boolean;
  onOpenEvidence: () => void;
  onOpenNumeric: () => void;
  onOpenWorkpaper: () => void;
  onOpenDeliverable: () => void;
};

type AnalystDraft = Omit<AnalystBaselineSubmission, "idempotency_key">;
type SeniorDraft = Omit<SeniorReviewSubmission, "idempotency_key">;
type TimerKey =
  | "time_to_find_source_seconds"
  | "time_to_verify_numeric_seconds"
  | "time_to_identify_weakest_judgment_seconds"
  | "time_to_review_writer_seconds";
type TimerState = Partial<Record<TimerKey, number>>;

const api = new HumanBaselineApiClient();

const emptyAnalystDraft: AnalystDraft = {
  strongest_source: "",
  material_limitation: "",
  numeric_verification: "",
  weakest_judgment: "",
  required_modification: "",
  writer_usefulness_score: 3,
  writer_usefulness_reason: "",
  time_to_find_source_seconds: 0,
  time_to_verify_numeric_seconds: 0,
  time_to_identify_weakest_judgment_seconds: 0,
  time_to_review_writer_seconds: 0,
  repeated_work_count: 0,
  blocking_ui_issue: "",
};

const emptySeniorDraft: SeniorDraft = {
  reviewer_ref: "",
  reviewer_role: "senior_analyst",
  decision: "conditional_approve",
  research_quality_score: 3,
  evidence_quality_score: 3,
  senior_reviewability_score: 3,
  numeric_reproducibility_confirmed: false,
  gap_boundaries_preserved: false,
  exact_digest_confirmed: false,
  review_comment: "",
  bounded_follow_up: [],
};

export function HumanBaseline({
  caseId,
  online,
  onOpenEvidence,
  onOpenNumeric,
  onOpenWorkpaper,
  onOpenDeliverable,
}: HumanBaselineProps) {
  const { copy, formatDateTime } = useWorkbenchLocale();
  const [session, setSession] = useState<HumanBaselineSession | null>(null);
  const [participantRef, setParticipantRef] = useState("internal_analyst");
  const [analystDraft, setAnalystDraft] = useState<AnalystDraft>(emptyAnalystDraft);
  const [seniorDraft, setSeniorDraft] = useState<SeniorDraft>(emptySeniorDraft);
  const [timerState, setTimerState] = useState<TimerState>({});
  const [clockNow, setClockNow] = useState(() => Date.now());
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!online || !navigator.onLine) return;
    setError(null);
    try {
      const sessions = await api.list(caseId);
      setSession(sessions.sessions[0] ?? null);
    } catch (reason) {
      setError(failureMessage(reason, copy));
    }
  }, [caseId, copy, online]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!session) return;
    const stored = localStorage.getItem(draftKey(session.session_id));
    if (!stored) return;
    try {
      const payload = JSON.parse(stored) as { analyst?: AnalystDraft; senior?: SeniorDraft; timers?: TimerState };
      if (payload.analyst) setAnalystDraft(payload.analyst);
      if (payload.senior) setSeniorDraft(payload.senior);
      if (payload.timers) setTimerState(payload.timers);
    } catch {
      localStorage.removeItem(draftKey(session.session_id));
    }
  }, [session?.session_id]);

  useEffect(() => {
    if (!session) return;
    localStorage.setItem(draftKey(session.session_id), JSON.stringify({ analyst: analystDraft, senior: seniorDraft, timers: timerState }));
  }, [analystDraft, seniorDraft, session, timerState]);

  useEffect(() => {
    if (!session || session.status === "exact_human_senior_review_recorded") return;
    const interval = window.setInterval(() => setClockNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [session?.session_id, session?.status]);

  const elapsed = useMemo(() => {
    if (!session) return 0;
    return Math.max(0, Math.round((clockNow - Date.parse(session.started_at)) / 1000));
  }, [clockNow, session]);

  function displayedTimerSeconds(key: TimerKey): number {
    const started = timerState[key];
    return analystDraft[key] + (started ? Math.max(0, Math.round((clockNow - started) / 1000)) : 0);
  }

  async function startSession() {
    await runBusy("start", async () => {
      const created = await api.start(caseId, participantRef, `baseline-start-${crypto.randomUUID()}`);
      setSession(created);
      setAnalystDraft(emptyAnalystDraft);
      setSeniorDraft(emptySeniorDraft);
      setTimerState({});
    });
  }

  async function submitAnalyst(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    await runBusy("analyst", async () => {
      const updated = await api.submitAnalyst(caseId, session.session_id, {
        ...analystDraft,
        idempotency_key: `baseline-analyst-${crypto.randomUUID()}`,
      });
      setSession(updated);
    });
  }

  async function submitSenior(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    await runBusy("senior", async () => {
      const updated = await api.submitSenior(caseId, session.session_id, {
        ...seniorDraft,
        bounded_follow_up: seniorDraft.bounded_follow_up.filter(Boolean),
        idempotency_key: `baseline-senior-${crypto.randomUUID()}`,
      });
      localStorage.removeItem(draftKey(session.session_id));
      setSession(updated);
    });
  }

  async function runBusy(label: string, action: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await action();
    } catch (reason) {
      setError(failureMessage(reason, copy));
    } finally {
      setBusy(null);
    }
  }

  function toggleTimer(key: TimerKey) {
    const started = timerState[key];
    if (started) {
      const seconds = Math.max(1, Math.round((Date.now() - started) / 1000));
      setAnalystDraft((current) => ({ ...current, [key]: current[key] + seconds }));
      setTimerState((current) => ({ ...current, [key]: undefined }));
    } else {
      setTimerState((current) => ({ ...current, [key]: Date.now() }));
    }
  }

  function exportSession() {
    if (!session) return;
    const blob = new Blob([JSON.stringify(session, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${session.session_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="p02-workspace baseline-workspace" aria-label={copy("实际产品任务基线", "Actual product task baseline")}>
      <div className="baseline-heading">
        <div>
          <p className="p02-eyebrow">RG3 / RG4 · {copy("人工证据", "Human evidence")}</p>
          <h1>{copy("实际产品任务基线与 Senior Review", "Actual task baseline and senior review")}</h1>
          <p>{copy("完成四个真实研究任务，再由 senior reviewer 针对同一组精确产物作出判断。", "Complete four real research tasks, then record a senior decision against the exact same artifacts.")}</p>
        </div>
        <div className="p02-page-actions">
          <button type="button" className="p02-icon-button" onClick={() => void load()} title={copy("刷新", "Refresh")}><RefreshCcw size={16} /></button>
          {session ? <button type="button" className="p02-secondary-button" onClick={exportSession}><Download size={16} />{copy("导出记录", "Export")}</button> : null}
        </div>
      </div>

      {error ? <RemoteStatus kind="error" message={error} /> : null}

      {!session ? (
        <section className="baseline-start-panel">
          <div className="baseline-start-copy">
            <UserCheck size={32} aria-hidden="true" />
            <h2>{copy("开始一轮可恢复的内部基线", "Start a resumable internal baseline")}</h2>
            <p>{copy("开始时会冻结当前 Case 与分析产物摘要。该记录只用于产品评测，不修改业务 Case，也不授权 RG1 或发布。", "Starting freezes the current Case and artifact digests. The record is product-evaluation evidence only and does not mutate the business Case or authorize release.")}</p>
          </div>
          <label>{copy("参与者标识", "Participant reference")}<input value={participantRef} onChange={(event) => setParticipantRef(event.target.value)} /></label>
          <button type="button" className="p02-primary-button" disabled={!online || busy === "start" || !participantRef.trim()} onClick={() => void startSession()}>
            <Play size={16} />{busy === "start" ? copy("正在创建", "Starting") : copy("开始基线", "Start baseline")}
          </button>
        </section>
      ) : (
        <>
          <ExactBindingBar session={session} elapsed={elapsed} />
          <div className="baseline-stage-grid">
            <StagePill index="1" label={copy("分析师任务", "Analyst tasks")} active={session.status === "in_progress"} complete={session.status !== "in_progress"} />
            <StagePill index="2" label={copy("Senior Review", "Senior review")} active={session.status === "analyst_submitted"} complete={session.status === "exact_human_senior_review_recorded"} />
            <StagePill index="3" label={copy("Exact 记录", "Exact record")} active={session.status === "exact_human_senior_review_recorded"} complete={session.status === "exact_human_senior_review_recorded"} />
          </div>

          {session.status === "in_progress" ? (
            <form className="baseline-form" onSubmit={(event) => void submitAnalyst(event)}>
              <BaselineTask
                number="01"
                title={copy("找到最强需求证据及其限制", "Find the strongest demand source and its limitation")}
                detail={copy("进入证据矩阵，选择你认为最有说服力的一条需求证据，并说明它不能证明什么。", "Open Evidence, select the strongest demand source, and state what it cannot prove.")}
                timerKey="time_to_find_source_seconds"
                seconds={displayedTimerSeconds("time_to_find_source_seconds")}
                running={Boolean(timerState.time_to_find_source_seconds)}
                onTimer={toggleTimer}
                onOpen={onOpenEvidence}
                openLabel={copy("打开证据", "Open Evidence")}
              >
                <label>{copy("最强来源", "Strongest source")}<textarea required rows={2} value={analystDraft.strongest_source} onChange={(event) => setAnalystDraft({ ...analystDraft, strongest_source: event.target.value })} /></label>
                <label>{copy("实质限制", "Material limitation")}<textarea required rows={2} value={analystDraft.material_limitation} onChange={(event) => setAnalystDraft({ ...analystDraft, material_limitation: event.target.value })} /></label>
              </BaselineTask>

              <BaselineTask number="02" title={copy("复核两项利润率计算", "Verify the two margin calculations")} detail={copy("依据三项精确事实复算毛利率和营业利润率，记录结果是否一致。", "Recalculate gross and operating margin from the three exact facts and record whether they match.")} timerKey="time_to_verify_numeric_seconds" seconds={displayedTimerSeconds("time_to_verify_numeric_seconds")} running={Boolean(timerState.time_to_verify_numeric_seconds)} onTimer={toggleTimer} onOpen={onOpenNumeric} openLabel={copy("打开数字", "Open Numbers")}>
                <label className="baseline-span-2">{copy("复算过程与结果", "Calculation and result")}<textarea required rows={3} value={analystDraft.numeric_verification} onChange={(event) => setAnalystDraft({ ...analystDraft, numeric_verification: event.target.value })} /></label>
              </BaselineTask>

              <BaselineTask number="03" title={copy("识别最弱判断并提出修改", "Identify the weakest judgment and required change")} detail={copy("在十个判断中选择最弱的一项，并给出具体修改或降级方式。", "Choose the weakest of the ten judgments and specify the required edit or downgrade.")} timerKey="time_to_identify_weakest_judgment_seconds" seconds={displayedTimerSeconds("time_to_identify_weakest_judgment_seconds")} running={Boolean(timerState.time_to_identify_weakest_judgment_seconds)} onTimer={toggleTimer} onOpen={onOpenWorkpaper} openLabel={copy("打开底稿", "Open Workpaper")}>
                <label>{copy("最弱判断", "Weakest judgment")}<textarea required rows={2} value={analystDraft.weakest_judgment} onChange={(event) => setAnalystDraft({ ...analystDraft, weakest_judgment: event.target.value })} /></label>
                <label>{copy("需要的修改", "Required modification")}<textarea required rows={2} value={analystDraft.required_modification} onChange={(event) => setAnalystDraft({ ...analystDraft, required_modification: event.target.value })} /></label>
              </BaselineTask>

              <BaselineTask number="04" title={copy("判断 Writer 草稿是否有用", "Judge whether the Writer draft is useful")} detail={copy("评价它是否适合作为研究起点，而不是评价它是否已经可以发布。", "Judge it as a research starting point, not as a release-ready deliverable.")} timerKey="time_to_review_writer_seconds" seconds={displayedTimerSeconds("time_to_review_writer_seconds")} running={Boolean(timerState.time_to_review_writer_seconds)} onTimer={toggleTimer} onOpen={onOpenDeliverable} openLabel={copy("打开结论", "Open Deliverable")}>
                <label>{copy("有用性评分（1-5）", "Usefulness score (1-5)")}<input type="number" min={1} max={5} value={analystDraft.writer_usefulness_score} onChange={(event) => setAnalystDraft({ ...analystDraft, writer_usefulness_score: Number(event.target.value) })} /></label>
                <label>{copy("评分理由", "Reason")}<textarea required rows={2} value={analystDraft.writer_usefulness_reason} onChange={(event) => setAnalystDraft({ ...analystDraft, writer_usefulness_reason: event.target.value })} /></label>
              </BaselineTask>

              <section className="baseline-observation-panel">
                <label>{copy("重复工作次数", "Repeated-work count")}<input type="number" min={0} value={analystDraft.repeated_work_count} onChange={(event) => setAnalystDraft({ ...analystDraft, repeated_work_count: Number(event.target.value) })} /></label>
                <label>{copy("阻断性界面问题（没有则留空）", "Blocking UI issue (leave blank if none)")}<input value={analystDraft.blocking_ui_issue} onChange={(event) => setAnalystDraft({ ...analystDraft, blocking_ui_issue: event.target.value })} /></label>
                <button type="submit" className="p02-primary-button" disabled={busy === "analyst" || Object.values(timerState).some(Boolean)}><FileCheck2 size={16} />{busy === "analyst" ? copy("正在提交", "Submitting") : copy("提交分析师基线", "Submit analyst baseline")}</button>
              </section>
            </form>
          ) : null}

          {session.status === "analyst_submitted" ? (
            <form className="senior-review-form" onSubmit={(event) => void submitSenior(event)}>
              <div className="senior-review-intro"><ShieldCheck size={28} /><div><h2>{copy("针对精确产物进行 Senior Review", "Review the exact bound artifacts")}</h2><p>{copy("Reviewer 必须确认当前 digest，并独立评价研究质量、证据质量和可复核性。", "The reviewer must confirm the digest and independently score research quality, evidence quality, and reviewability.")}</p></div></div>
              <div className="baseline-form-grid">
                <label>{copy("Reviewer 标识", "Reviewer reference")}<input required value={seniorDraft.reviewer_ref} onChange={(event) => setSeniorDraft({ ...seniorDraft, reviewer_ref: event.target.value })} /></label>
                <label>{copy("Reviewer 角色", "Reviewer role")}<select value={seniorDraft.reviewer_role} onChange={(event) => setSeniorDraft({ ...seniorDraft, reviewer_role: event.target.value as SeniorDraft["reviewer_role"] })}><option value="senior_analyst">Senior analyst</option><option value="domain_reviewer">Domain reviewer</option></select></label>
                <label>{copy("复核决定", "Decision")}<select value={seniorDraft.decision} onChange={(event) => setSeniorDraft({ ...seniorDraft, decision: event.target.value as SeniorDraft["decision"] })}><option value="approve">Approve</option><option value="conditional_approve">Conditional approve</option><option value="return_for_follow_up">Return for follow-up</option></select></label>
                <ScoreInput label={copy("研究质量", "Research quality")} value={seniorDraft.research_quality_score} onChange={(value) => setSeniorDraft({ ...seniorDraft, research_quality_score: value })} />
                <ScoreInput label={copy("证据质量", "Evidence quality")} value={seniorDraft.evidence_quality_score} onChange={(value) => setSeniorDraft({ ...seniorDraft, evidence_quality_score: value })} />
                <ScoreInput label={copy("可复核性", "Reviewability")} value={seniorDraft.senior_reviewability_score} onChange={(value) => setSeniorDraft({ ...seniorDraft, senior_reviewability_score: value })} />
                <label className="baseline-span-2">{copy("复核意见", "Review comment")}<textarea required rows={4} value={seniorDraft.review_comment} onChange={(event) => setSeniorDraft({ ...seniorDraft, review_comment: event.target.value })} /></label>
                <label className="baseline-span-2">{copy("受限后续动作（每行一项，最多三项）", "Bounded follow-up (one per line, max three)")}<textarea rows={3} value={seniorDraft.bounded_follow_up.join("\n")} onChange={(event) => setSeniorDraft({ ...seniorDraft, bounded_follow_up: event.target.value.split("\n").slice(0, 3) })} /></label>
              </div>
              <div className="senior-attestations">
                <label><input type="checkbox" checked={seniorDraft.numeric_reproducibility_confirmed} onChange={(event) => setSeniorDraft({ ...seniorDraft, numeric_reproducibility_confirmed: event.target.checked })} />{copy("已复核数字可复算", "Numeric reproducibility confirmed")}</label>
                <label><input type="checkbox" checked={seniorDraft.gap_boundaries_preserved} onChange={(event) => setSeniorDraft({ ...seniorDraft, gap_boundaries_preserved: event.target.checked })} />{copy("缺口与结论边界得到保留", "Gaps and conclusion boundaries are preserved")}</label>
                <label><input type="checkbox" checked={seniorDraft.exact_digest_confirmed} onChange={(event) => setSeniorDraft({ ...seniorDraft, exact_digest_confirmed: event.target.checked })} />{copy("我确认复核对象与页面所示 exact digest 一致", "I confirm the reviewed artifacts match the exact digest shown")}</label>
              </div>
              <button type="submit" className="p02-primary-button" disabled={busy === "senior" || !seniorDraft.exact_digest_confirmed}><UserCheck size={16} />{busy === "senior" ? copy("正在记录", "Recording") : copy("记录 Exact Human Senior Review", "Record exact human senior review")}</button>
            </form>
          ) : null}

          {session.status === "exact_human_senior_review_recorded" ? <BaselineComplete session={session} onExport={exportSession} /> : null}
        </>
      )}
    </section>
  );
}

function ExactBindingBar({ session, elapsed }: { session: HumanBaselineSession; elapsed: number }) {
  const { copy, formatDateTime } = useWorkbenchLocale();
  return (
    <section className="exact-binding-bar">
      <div><Fingerprint size={18} /><span><small>EXACT ARTIFACT BINDING</small><b title={session.artifact_binding_digest}>{shortDigest(session.artifact_binding_digest)}</b></span></div>
      <dl><div><dt>{copy("Case 版本", "Case version")}</dt><dd>v{session.artifact_binding.case_version}</dd></div><div><dt>{copy("开始于", "Started")}</dt><dd>{formatDateTime(session.started_at)}</dd></div><div><dt>{copy("已用时间", "Elapsed")}</dt><dd>{formatDuration(elapsed)}</dd></div><div><dt>{copy("当前状态", "Status")}</dt><dd>{session.status}</dd></div></dl>
    </section>
  );
}

function StagePill({ index, label, active, complete }: { index: string; label: string; active: boolean; complete: boolean }) {
  return <div className={`baseline-stage ${active ? "is-active" : ""} ${complete ? "is-complete" : ""}`}><span>{complete ? <Check size={14} /> : index}</span><b>{label}</b></div>;
}

function BaselineTask({ number, title, detail, timerKey, seconds, running, onTimer, onOpen, openLabel, children }: {
  number: string;
  title: string;
  detail: string;
  timerKey: TimerKey;
  seconds: number;
  running: boolean;
  onTimer: (key: TimerKey) => void;
  onOpen: () => void;
  openLabel: string;
  children: React.ReactNode;
}) {
  const { copy } = useWorkbenchLocale();
  return (
    <section className="baseline-task-card">
      <header><span className="baseline-task-number">{number}</span><div><h2>{title}</h2><p>{detail}</p></div><div className="baseline-task-actions"><span><Clock3 size={14} />{formatDuration(seconds)}</span><button type="button" className={running ? "is-running" : ""} onClick={() => onTimer(timerKey)}>{running ? <Square size={13} /> : <Play size={13} />}{running ? copy("停止计时", "Stop") : copy("开始计时", "Start timer")}</button><button type="button" onClick={onOpen}>{openLabel}<ArrowRight size={13} /></button></div></header>
      <div className="baseline-answer-grid">{children}</div>
    </section>
  );
}

function ScoreInput({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label>{label}<input type="number" min={1} max={5} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function BaselineComplete({ session, onExport }: { session: HumanBaselineSession; onExport: () => void }) {
  const { copy, formatDateTime } = useWorkbenchLocale();
  return (
    <section className="baseline-complete-panel">
      <div className="baseline-complete-mark"><Check size={26} /></div>
      <div><p className="p02-eyebrow">EXACT HUMAN REVIEW RECORDED</p><h2>{copy("本轮产品任务基线已完成", "This product task baseline is complete")}</h2><p>{copy("分析师结果与 senior decision 已绑定同一组研究产物，可作为 RG3/RG4 独立复核输入。它本身不自动改变发布状态。", "The analyst result and senior decision are bound to the same artifacts and can be independently reviewed for RG3/RG4. This record does not automatically change release status.")}</p><dl><div><dt>{copy("复核决定", "Decision")}</dt><dd>{session.senior_review?.decision}</dd></div><div><dt>{copy("Reviewer", "Reviewer")}</dt><dd>{session.senior_review?.reviewer_ref}</dd></div><div><dt>{copy("完成时间", "Completed")}</dt><dd>{session.senior_reviewed_at ? formatDateTime(session.senior_reviewed_at) : "-"}</dd></div><div><dt>Final review digest</dt><dd title={session.final_review_digest ?? ""}>{shortDigest(session.final_review_digest ?? "")}</dd></div></dl></div>
      <button type="button" className="p02-primary-button" onClick={onExport}><Download size={16} />{copy("导出完整 JSON", "Export full JSON")}</button>
    </section>
  );
}

function failureMessage(reason: unknown, copy: (zhCN: string, en: string) => string): string {
  if (reason instanceof HumanBaselineApiError) {
    if (reason.code === "exact_candidate_drift") return copy("当前研究产物已变化，本轮基线不能继续。请保留现有记录并重新开始。", "The research artifacts changed. Preserve this record and start a new baseline.");
    if (reason.code === "exact_candidate_unavailable") return copy("当前 Case 尚未准备好真实研究预览，无法冻结基线。", "This Case is not ready for an exact research baseline.");
    if (reason.code === "permission_denied") return copy("当前身份无权写入人工基线。", "The current identity cannot write a human baseline.");
    return `${copy("基线请求失败", "Baseline request failed")}: ${reason.code}`;
  }
  return copy("基线服务未返回可用结果。", "The baseline service did not return a usable result.");
}

function draftKey(sessionId: string): string { return `finsight:human-baseline:draft:${sessionId}`; }
function shortDigest(value: string): string { return value ? `${value.slice(0, 12)}…${value.slice(-8)}` : "-"; }
function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
