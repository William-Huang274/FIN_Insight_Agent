import {
  AlertTriangle,
  ArrowLeft,
  BookOpenCheck,
  Building2,
  CheckCircle2,
  Database,
  ExternalLink,
  FileSearch,
  Fingerprint,
  LoaderCircle,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  EvidenceItem,
  ResearchCaseDetail,
  ResearchCaseList,
  ResearchCaseSummary,
  ResearchEvidenceView,
  ResearchWorkspaceApiClient,
} from "../api/researchWorkspace";
import "./research-workspace.css";

type WorkspaceRoute =
  | { kind: "cases" }
  | { kind: "case"; caseId: string; surface: "overview" | "evidence" };

type LoadState<T> =
  | { kind: "loading" }
  | { kind: "ready"; value: T }
  | { kind: "error"; message: string };

const api = new ResearchWorkspaceApiClient();

export function isResearchWorkspacePath(pathname: string): boolean {
  return pathname === "/workspace" || pathname.startsWith("/workspace/");
}

export function ResearchWorkspace() {
  const [route, setRoute] = useState<WorkspaceRoute>(() => decodeRoute(window.location.pathname));

  useEffect(() => {
    const onPopState = () => setRoute(decodeRoute(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (next: WorkspaceRoute) => {
    window.history.pushState({}, "", pathForRoute(next));
    setRoute(next);
  };

  return (
    <div className="research-workspace">
      <header className="research-workspace__topbar">
        <button className="research-workspace__brand" type="button" onClick={() => navigate({ kind: "cases" })}>
          <span>F</span>
          <div>
            <strong>FinSight Research</strong>
            <small>FIN 0.1.3 · reviewed evidence workspace</small>
          </div>
        </button>
        <div className="research-workspace__topbar-actions">
          <span className="research-workspace__online is-online">
            <i />只读审证模式
          </span>
          <a href="/operations">运行与运维 <ExternalLink size={14} /></a>
        </div>
      </header>

      {route.kind === "cases" ? (
        <ResearchCaseIndex onOpen={(caseId) => navigate({ kind: "case", caseId, surface: "overview" })} />
      ) : (
        <ResearchCaseWorkspace
          route={route}
          onBack={() => navigate({ kind: "cases" })}
          onSurface={(surface) => navigate({ ...route, surface })}
        />
      )}
    </div>
  );
}

function ResearchCaseIndex({ onOpen }: { onOpen: (caseId: string) => void }) {
  const [state, setState] = useState<LoadState<ResearchCaseList>>({ kind: "loading" });
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    api.listCases(controller.signal)
      .then((value) => setState({ kind: "ready", value }))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setState({ kind: "error", message: error.message });
      });
    return () => controller.abort();
  }, [refreshKey]);

  return (
    <main className="research-workspace__page">
      <section className="research-workspace__hero">
        <div>
          <p className="research-workspace__eyebrow">PRIMARY PRODUCT SURFACE</p>
          <h1>当前研究案例</h1>
          <p>这里仅展示已绑定公司身份、研究截至日和不可变 Evidence Pack 的真实案例。</p>
        </div>
        <button type="button" onClick={() => setRefreshKey((value) => value + 1)}>
          <RefreshCcw size={16} /> 刷新
        </button>
      </section>

      {state.kind === "loading" ? <Loading label="正在核验案例与 Evidence Pack 绑定…" /> : null}
      {state.kind === "error" ? <Failure message={state.message} /> : null}
      {state.kind === "ready" ? (
        <>
          <div className="research-workspace__assurance">
            <ShieldCheck size={19} />
            <span>{state.value.items.length} 个案例已通过身份与摘要绑定；{state.value.evidence_objects_ready ? "证据对象已挂载" : `仍需挂载 ${state.value.unavailable_case_keys.join("、")} 证据对象`}。</span>
            <code>{shortDigest(state.value.evidence_pack_result_digest)}</code>
          </div>
          <section className="research-workspace__case-grid">
            {state.value.items.map((item) => <CaseCard key={item.case_id} item={item} onOpen={onOpen} />)}
          </section>
          <Boundary text={state.value.known_boundary} />
        </>
      ) : null}
    </main>
  );
}

function CaseCard({ item, onOpen }: { item: ResearchCaseSummary; onOpen: (caseId: string) => void }) {
  return (
    <button className="research-workspace__case-card" type="button" disabled={!item.evidence_object_ready} onClick={() => onOpen(item.case_id)}>
      <div className="research-workspace__case-heading">
        <span className="research-workspace__ticker">{item.case_key}</span>
        <CheckCircle2 size={18} />
      </div>
      <h2>{item.subject.legal_name}</h2>
      <p>{item.subject.exchange} · CIK {item.subject.issuer_id} · 截至 {item.research_as_of}</p>
      <div className="research-workspace__metrics">
        <Metric value={item.evidence_summary.accepted_evidence_items} label="已审证据" />
        <Metric value={item.evidence_summary.source_materials} label="来源材料" />
        <Metric value={item.evidence_summary.residual_gaps} label="剩余缺口" warn />
      </div>
      <footer>
        <span><Fingerprint size={14} /> {shortDigest(item.pack_binding.binding_digest)}</span>
        <b>{item.evidence_object_ready ? "打开研究案例 →" : "证据对象未挂载"}</b>
      </footer>
    </button>
  );
}

function ResearchCaseWorkspace({
  route,
  onBack,
  onSurface,
}: {
  route: Extract<WorkspaceRoute, { kind: "case" }>;
  onBack: () => void;
  onSurface: (surface: "overview" | "evidence") => void;
}) {
  const [state, setState] = useState<LoadState<{ detail: ResearchCaseDetail; evidence: ResearchEvidenceView }>>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    Promise.all([
      api.getCase(route.caseId, controller.signal),
      api.getEvidence(route.caseId, controller.signal),
    ])
      .then(([detail, evidence]) => setState({ kind: "ready", value: { detail, evidence } }))
      .catch((error: Error) => {
        if (error.name !== "AbortError") setState({ kind: "error", message: error.message });
      });
    return () => controller.abort();
  }, [route.caseId]);

  if (state.kind === "loading") return <main className="research-workspace__page"><Loading label="正在核验案例身份、内容摘要与来源…" /></main>;
  if (state.kind === "error") return <main className="research-workspace__page"><Failure message={state.message} /></main>;

  const { detail, evidence } = state.value;
  return (
    <main className="research-workspace__page">
      <button className="research-workspace__back" type="button" onClick={onBack}><ArrowLeft size={16} /> 返回案例列表</button>
      <section className="research-workspace__case-title">
        <div>
          <p className="research-workspace__eyebrow">{detail.case_key} · IDENTITY BOUND</p>
          <h1>{detail.subject.legal_name}</h1>
          <p>{detail.research_context.research_question}</p>
        </div>
        <div className="research-workspace__identity-badge">
          <Building2 size={19} />
          <div><strong>{detail.subject.exchange}:{detail.subject.ticker}</strong><small>CIK {detail.subject.issuer_id}</small></div>
        </div>
      </section>

      <nav className="research-workspace__tabs" aria-label="研究案例页面">
        <button className={route.surface === "overview" ? "is-active" : ""} type="button" onClick={() => onSurface("overview")}>
          <BookOpenCheck size={16} /> 研究概览
        </button>
        <button className={route.surface === "evidence" ? "is-active" : ""} type="button" onClick={() => onSurface("evidence")}>
          <FileSearch size={16} /> 证据与缺口
        </button>
      </nav>

      {route.surface === "overview" ? <CaseOverview detail={detail} evidence={evidence} /> : <EvidenceSurface evidence={evidence} />}
      <Boundary text={detail.known_boundary} />
    </main>
  );
}

function CaseOverview({ detail, evidence }: { detail: ResearchCaseDetail; evidence: ResearchEvidenceView }) {
  const slotCoverage = useMemo(() => {
    const slots = new Set<string>();
    evidence.evidence_items.forEach((item) => item.slot_bindings?.forEach((slot) => slots.add(slot.slot_id)));
    return slots.size;
  }, [evidence]);
  return (
    <>
      <section className="research-workspace__overview-grid">
        <article className="research-workspace__panel">
          <h2>当前证据基础</h2>
          <div className="research-workspace__metrics is-large">
            <Metric value={evidence.evidence_items.length} label="已审证据" />
            <Metric value={slotCoverage} label="Evidence Slots" />
            <Metric value={evidence.residual_gaps.length} label="明确缺口" warn />
          </div>
          <p>截至 {detail.research_as_of}。下列内容是可追溯的研究输入，不等同于完整投资结论。</p>
        </article>
        <article className="research-workspace__panel">
          <h2>不可变绑定</h2>
          <DigestRow label="Case subject" value={detail.subject_digest} />
          <DigestRow label="Evidence artifact" value={detail.pack_binding.pack_artifact_digest} />
          <DigestRow label="Pack payload" value={detail.pack_binding.pack_payload_digest} />
          <DigestRow label="Binding" value={detail.pack_binding.binding_digest} />
        </article>
      </section>
      <section className="research-workspace__panel">
        <div className="research-workspace__section-title"><h2>代表性证据</h2><span>前 5 条 · 按已审 Pack 顺序</span></div>
        <div className="research-workspace__evidence-list">
          {evidence.evidence_items.slice(0, 5).map((item) => <EvidenceCard key={item.evidence_item_digest} item={item} compact />)}
        </div>
      </section>
      <section className="research-workspace__panel">
        <div className="research-workspace__section-title"><h2>最先需要补足的缺口</h2><span>{evidence.residual_gaps.length} 条保留在产品面</span></div>
        <GapList gaps={evidence.residual_gaps.slice(0, 6)} />
      </section>
    </>
  );
}

function EvidenceSurface({ evidence }: { evidence: ResearchEvidenceView }) {
  return (
    <section className="research-workspace__evidence-columns">
      <div className="research-workspace__panel">
        <div className="research-workspace__section-title"><h2>已审 Evidence</h2><span>{evidence.evidence_items.length} 条</span></div>
        <div className="research-workspace__evidence-list">
          {evidence.evidence_items.map((item) => <EvidenceCard key={item.evidence_item_digest} item={item} />)}
        </div>
      </div>
      <aside className="research-workspace__panel research-workspace__gap-panel">
        <div className="research-workspace__section-title"><h2>Residual Gaps</h2><span>{evidence.residual_gaps.length} 条</span></div>
        <GapList gaps={evidence.residual_gaps} />
      </aside>
    </section>
  );
}

function EvidenceCard({ item, compact = false }: { item: EvidenceItem; compact?: boolean }) {
  const primarySlot = item.slot_bindings?.[0];
  return (
    <article className="research-workspace__evidence-card">
      <header>
        <span>{item.evidence_role ?? item.disposition}</span>
        <time>{item.publication_date ?? "日期未披露"}</time>
      </header>
      <h3>{primarySlot?.business_meaning_zh ?? primarySlot?.slot_id ?? item.target_id}</h3>
      <p className={compact ? "is-clamped" : ""}>{item.source.reviewed_source_excerpt}</p>
      {primarySlot?.claim_boundary_zh ? <div className="research-workspace__claim-boundary">边界：{primarySlot.claim_boundary_zh}</div> : null}
      <footer>
        <span>{item.source.source_tier} · {item.source.source_type}</span>
        <a href={item.source.source_url} target="_blank" rel="noreferrer">查看来源 <ExternalLink size={12} /></a>
      </footer>
    </article>
  );
}

function GapList({ gaps }: { gaps: ResearchEvidenceView["residual_gaps"] }) {
  return (
    <div className="research-workspace__gap-list">
      {gaps.map((gap) => (
        <article key={gap.gap_id}>
          <AlertTriangle size={15} />
          <div>
            <strong>{gap.business_reason_zh ?? gap.gap_code}</strong>
            {gap.supplement_direction_zh ? <p>{gap.supplement_direction_zh}</p> : null}
            <small>{[gap.slot_id, gap.facet_id].filter(Boolean).join(" / ")}</small>
          </div>
        </article>
      ))}
    </div>
  );
}

function Metric({ value, label, warn = false }: { value: number; label: string; warn?: boolean }) {
  return <div className={warn ? "research-workspace__metric is-warn" : "research-workspace__metric"}><strong>{value}</strong><span>{label}</span></div>;
}

function DigestRow({ label, value }: { label: string; value: string }) {
  return <div className="research-workspace__digest-row"><span>{label}</span><code title={value}>{shortDigest(value)}</code></div>;
}

function Boundary({ text }: { text: string }) {
  return <div className="research-workspace__boundary"><Database size={17} /><div><strong>当前产品边界</strong><p>{text}</p></div></div>;
}

function Loading({ label }: { label: string }) {
  return <div className="research-workspace__state"><LoaderCircle className="is-spinning" size={24} /><p>{label}</p></div>;
}

function Failure({ message }: { message: string }) {
  return <div className="research-workspace__state is-error"><AlertTriangle size={24} /><strong>研究工作区未能通过绑定校验</strong><p>{message}</p></div>;
}

function shortDigest(value: string): string {
  return value.length > 18 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value;
}

function decodeRoute(pathname: string): WorkspaceRoute {
  const match = /^\/workspace\/cases\/([^/]+)(?:\/(overview|evidence))?\/?$/.exec(pathname);
  if (!match) return { kind: "cases" };
  return {
    kind: "case",
    caseId: decodeURIComponent(match[1]),
    surface: match[2] === "evidence" ? "evidence" : "overview",
  };
}

function pathForRoute(route: WorkspaceRoute): string {
  if (route.kind === "cases") return "/workspace";
  return `/workspace/cases/${encodeURIComponent(route.caseId)}/${route.surface}`;
}
