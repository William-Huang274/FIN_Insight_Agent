from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.humanmade_gold_set_runtime import (
    build_ai_semis_gold_depth_content_pack,
    compile_negative_cases_to_failure_gates,
    compile_rubric_cases_to_vertical_playbook_contracts,
    run_humanmade_gold_set_audit,
)
from sec_agent.langgraph_orchestrator import _render_memo_answer
from sec_agent.memo_llm import verifier_input_projection_for_state
from sec_agent.multi_agent_contracts import verify_multi_agent_memo_draft


P33_PROJECTION_REPLAY_SCHEMA_VERSION = "fin_insight_p33_memo_projection_replay_v0_1"
P33_MULTI_CASE_GOLDSET_READINESS_SCHEMA_VERSION = "fin_insight_p33_multicase_goldset_readiness_v0_1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMO_WRITER_NODE_RESULT = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "p33_gold_case_runs"
    / "p33_stepwise_memo_writer_node_after_dimension_plan_projection_deepseek_20260707_r1"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "memo_writer_node_result.json"
)
DEFAULT_SPEC_PATH = REPO_ROOT / "docs" / "project_os" / "humanmade_gold_set_spec_v0_1.json"
DEFAULT_EXEMPLARS_PATH = REPO_ROOT / "docs" / "project_os" / "humanmade_gold_set_answer_exemplars_v0_2.json"
DEFAULT_MATRIX_AUDIT_PATH = REPO_ROOT / "docs" / "project_os" / "humanmade_gold_set_matrix_audit_v0_1.json"
DEFAULT_PROJECTION_JSON = REPO_ROOT / "docs" / "project_os" / "p33_single_case_projection_replay_v0_1.json"
DEFAULT_PROJECTION_MD = (
    REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "p33_single_case_projection_replay_v0_1.zh-CN.md"
)
DEFAULT_MULTI_CASE_JSON = REPO_ROOT / "docs" / "project_os" / "p33_multicase_goldset_readiness_v0_1.json"
DEFAULT_MULTI_CASE_MD = (
    REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "p33_multicase_goldset_readiness_v0_1.zh-CN.md"
)

RENDER_REQUIRED_HEADINGS = (
    "核心判断",
    "分维度分析",
    "关键问题回应",
    "关键论据",
    "投资含义",
    "什么会改变判断",
    "后续跟踪",
    "可行动的证据缺口",
    "证据索引",
)

INTERNAL_RENDER_MARKERS = (
    "ClaimCard",
    "JudgmentCard",
    "gap_id",
    "driver_id",
    "schema_version",
    "memo_slot",
    "source_families",
    "Parsed bounded issuer_official",
    "Official source identifies issuer",
    "尚未完成中文综合",
    "mechanism:",
    "financial bridge:",
    "机制：",
    "财务桥：",
)


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_single_case_projection_replay(
    memo_writer_node_result: str | Path = DEFAULT_MEMO_WRITER_NODE_RESULT,
) -> dict[str, Any]:
    """Replay renderer, final verifier and Workbench projection from one accepted Memo Writer artifact.

    This is deliberately deterministic. It verifies whether the accepted scoped
    writer draft can become a user/reviewer-facing workpaper without another
    paid LLM call.
    """

    artifact_path = Path(memo_writer_node_result)
    node_result = load_json(artifact_path)
    memo = node_result.get("memo_answer") if isinstance(node_result.get("memo_answer"), Mapping) else {}
    judgment = (
        node_result.get("verified_judgment_plan")
        if isinstance(node_result.get("verified_judgment_plan"), Mapping)
        else node_result.get("judgment_plan")
        if isinstance(node_result.get("judgment_plan"), Mapping)
        else {}
    )
    state = {**node_result, "memo_answer": memo, "verified_judgment_plan": judgment}
    renderer_projection = build_renderer_projection(state, artifact_path=artifact_path)
    final_verifier_projection = build_final_verifier_projection(state)
    workbench_projection = build_workbench_projection(state, artifact_path=artifact_path)
    checks = {
        "renderer_projection_pass": renderer_projection.get("status") == "pass",
        "final_verifier_projection_pass": final_verifier_projection.get("status") == "pass",
        "workbench_projection_pass": workbench_projection.get("status") == "pass",
        "no_paid_llm_called": True,
    }
    errors = [{"type": key, "status": "failed"} for key, passed in checks.items() if not passed]
    return {
        "schema_version": P33_PROJECTION_REPLAY_SCHEMA_VERSION,
        "status": "pass" if not errors else "fail",
        "case_id": _case_id_from_artifact(node_result, artifact_path),
        "source_artifact": _rel(artifact_path),
        "checks": checks,
        "errors": errors,
        "renderer_projection": renderer_projection,
        "final_verifier_projection": final_verifier_projection,
        "workbench_projection": workbench_projection,
        "not_run": ["paid_llm", "full_chain", "model_comparison", "case_expansion"],
        "acceptance_boundary": (
            "A pass here only proves renderer/final-verifier/Workbench projection from the scoped memo artifact. "
            "It is not a fresh specialist pass, full-chain pass, or human-accepted gold workpaper."
        ),
    }


def build_renderer_projection(state: Mapping[str, Any], *, artifact_path: Path) -> dict[str, Any]:
    memo = state.get("memo_answer") if isinstance(state.get("memo_answer"), Mapping) else {}
    rendered = _render_memo_answer(memo, bounded=False, state=state)
    headings_present = {heading: heading in rendered for heading in RENDER_REQUIRED_HEADINGS}
    internal_markers = [marker for marker in INTERNAL_RENDER_MARKERS if marker in rendered]
    heading_failures = [heading for heading, present in headings_present.items() if not present]
    citation_labels = sorted(set(re.findall(r"\[C\d+\]", rendered)))
    errors: list[dict[str, Any]] = []
    if len(rendered.strip()) < 3500:
        errors.append({"type": "rendered_workpaper_too_thin", "chars": len(rendered)})
    if heading_failures:
        errors.append({"type": "missing_required_rendered_headings", "headings": heading_failures})
    if internal_markers:
        errors.append({"type": "internal_field_or_trace_leak", "markers": internal_markers})
    if len(citation_labels) < 6:
        errors.append({"type": "citation_projection_too_sparse", "citation_count": len(citation_labels)})
    return {
        "schema_version": "fin_insight_p33_renderer_projection_v0_1",
        "status": "pass" if not errors else "fail",
        "source_artifact": _rel(artifact_path),
        "rendered_answer_chars": len(rendered),
        "heading_presence": headings_present,
        "citation_label_count": len(citation_labels),
        "citation_labels": citation_labels[:40],
        "internal_marker_hits": internal_markers,
        "errors": errors,
        "rendered_answer": rendered,
        "rendering_policy": "memo_logic_plan_to_user_workpaper_markdown_no_internal_fields_v0_1",
    }


def build_final_verifier_projection(state: Mapping[str, Any]) -> dict[str, Any]:
    memo = state.get("memo_answer") if isinstance(state.get("memo_answer"), Mapping) else {}
    judgment = state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else {}
    deterministic = verify_multi_agent_memo_draft(memo, judgment)
    projection = verifier_input_projection_for_state(
        state,
        deterministic=deterministic,
        capture_source="p33_projection_replay_from_scoped_memo_writer_artifact",
    )
    stats = projection.get("projection_stats") if isinstance(projection.get("projection_stats"), Mapping) else {}
    fingerprint = (
        projection.get("input_pack_fingerprint") if isinstance(projection.get("input_pack_fingerprint"), Mapping) else {}
    )
    errors: list[dict[str, Any]] = []
    if deterministic.get("status") != "pass":
        errors.append({"type": "deterministic_memo_verification_failed", "errors": deterministic.get("errors") or []})
    if int(stats.get("memo_claim_count") or 0) < 6:
        errors.append({"type": "memo_claim_projection_too_sparse", "memo_claim_count": stats.get("memo_claim_count")})
    if int(stats.get("projected_claim_count") or 0) < 6:
        errors.append(
            {"type": "verifier_claim_inventory_too_sparse", "projected_claim_count": stats.get("projected_claim_count")}
        )
    if int(fingerprint.get("known_evidence_ref_count") or 0) < 10:
        errors.append(
            {
                "type": "verifier_known_evidence_refs_too_sparse",
                "known_evidence_ref_count": fingerprint.get("known_evidence_ref_count"),
            }
        )
    if int(fingerprint.get("approx_total_prompt_chars_with_scaffold") or 0) > 25000:
        errors.append(
            {
                "type": "verifier_projection_not_compact_enough",
                "approx_total_prompt_chars_with_scaffold": fingerprint.get("approx_total_prompt_chars_with_scaffold"),
            }
        )
    compact_projection = {
        key: projection.get(key)
        for key in (
            "schema_version",
            "projection_policy",
            "memo_claim_ref_inventory",
            "allowed_evidence_refs",
            "source_boundary_notes",
            "deterministic_verification",
            "projection_stats",
            "input_pack_fingerprint",
        )
    }
    return {
        "schema_version": "fin_insight_p33_final_verifier_projection_v0_1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "deterministic_status": deterministic.get("status"),
        "deterministic_error_count": len(deterministic.get("errors") or []),
        "deterministic_warning_count": len(deterministic.get("warnings") or []),
        "projection_stats": dict(stats),
        "input_pack_fingerprint": dict(fingerprint),
        "projection": compact_projection,
        "projection_policy": "final_memo_claims_and_referenced_evidence_only_no_raw_evidence_dump_v0_1",
    }


def build_workbench_projection(state: Mapping[str, Any], *, artifact_path: Path) -> dict[str, Any]:
    memo = state.get("memo_answer") if isinstance(state.get("memo_answer"), Mapping) else {}
    logic_plan = state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {}
    judgment = state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else {}
    route = state.get("memo_route_result") if isinstance(state.get("memo_route_result"), Mapping) else {}
    sections = _workbench_sections(memo, logic_plan)
    claims = _workbench_claims(memo)
    gaps = _workbench_gaps(memo, judgment)
    gates = [
        {
            "gate_id": "memo_writer_node_gate",
            "status": "pass" if str(route.get("status") or "") == "pass" else "fail",
            "detail": {
                "attempt_count": route.get("attempt_count"),
                "repair_attempts": route.get("repair_attempts"),
                "total_tokens": route.get("total_tokens"),
            },
        },
        {
            "gate_id": "memo_deterministic_hard_check",
            "status": verify_multi_agent_memo_draft(memo, judgment).get("status") or "unknown",
            "detail": {"policy": "verify_multi_agent_memo_draft"},
        },
    ]
    artifacts = [
        {"artifact_id": "memo_writer_node_result", "artifact_type": "json", "path": _rel(artifact_path), "exists": artifact_path.exists()},
        {
            "artifact_id": "p33_single_case_projection_replay",
            "artifact_type": "json",
            "path": _rel(DEFAULT_PROJECTION_JSON),
            "exists": DEFAULT_PROJECTION_JSON.exists(),
        },
    ]
    events = [
        {"sequence": 1, "event_type": "memo_writer_node_pass", "source": "scoped_paid_node_artifact"},
        {"sequence": 2, "event_type": "renderer_projection_replay", "source": "deterministic_replay"},
        {"sequence": 3, "event_type": "final_verifier_projection_replay", "source": "deterministic_replay"},
        {"sequence": 4, "event_type": "workbench_projection_replay", "source": "deterministic_replay"},
    ]
    section_claim_links = sum(1 for section in sections if section.get("claim_ids"))
    evidence_linked_claims = sum(1 for claim in claims if claim.get("evidence_refs"))
    errors: list[dict[str, Any]] = []
    if len(sections) < 6:
        errors.append({"type": "workbench_sections_too_sparse", "section_count": len(sections)})
    if len(claims) < 6:
        errors.append({"type": "workbench_claims_too_sparse", "claim_count": len(claims)})
    if evidence_linked_claims < 6:
        errors.append({"type": "workbench_claim_evidence_links_too_sparse", "linked_claim_count": evidence_linked_claims})
    if len(gaps) < 1:
        errors.append({"type": "workbench_typed_gaps_missing"})
    if section_claim_links < 3:
        errors.append({"type": "workbench_section_claim_links_too_sparse", "section_claim_links": section_claim_links})
    if not all(artifact["exists"] for artifact in artifacts[:1]):
        errors.append({"type": "source_artifact_missing"})
    return {
        "schema_version": "fin_insight_p33_workbench_projection_v0_1",
        "status": "pass" if not errors else "fail",
        "task_id": _case_id_from_artifact(state, artifact_path),
        "run_id": str(state.get("run_id") or artifact_path.parents[1].name),
        "surfaces": ["sections", "claims", "gaps", "gates", "artifacts", "events"],
        "sections": sections,
        "claims": claims,
        "gaps": gaps,
        "gates": gates,
        "artifacts": artifacts,
        "events": events,
        "counts": {
            "section_count": len(sections),
            "claim_count": len(claims),
            "gap_count": len(gaps),
            "gate_count": len(gates),
            "artifact_count": len(artifacts),
            "event_count": len(events),
            "evidence_linked_claim_count": evidence_linked_claims,
            "section_claim_link_count": section_claim_links,
        },
        "errors": errors,
        "projection_policy": "artifact_backed_workbench_drilldown_without_sql_write_v0_1",
    }


def build_multicase_goldset_readiness(
    *,
    single_case_projection: Mapping[str, Any] | None = None,
    spec_path: str | Path = DEFAULT_SPEC_PATH,
    exemplars_path: str | Path = DEFAULT_EXEMPLARS_PATH,
    matrix_audit_path: str | Path = DEFAULT_MATRIX_AUDIT_PATH,
) -> dict[str, Any]:
    spec = load_json(spec_path)
    exemplars = load_json(exemplars_path)
    matrix_audit = load_json(matrix_audit_path)
    single_case_projection = single_case_projection or {}
    gold_content = build_ai_semis_gold_depth_content_pack()
    rubric_contracts = compile_rubric_cases_to_vertical_playbook_contracts(spec, exemplars)
    negative_gates = compile_negative_cases_to_failure_gates(spec, exemplars)
    cases = [case for case in spec.get("cases") or [] if isinstance(case, Mapping)]
    matrix_by_case = {
        str(row.get("case_id") or ""): row
        for row in matrix_audit.get("case_results") or []
        if isinstance(row, Mapping)
    }
    case_rows = [
        _multicase_readiness_row(
            case,
            matrix_by_case=matrix_by_case,
            single_case_projection=single_case_projection,
            gold_content=gold_content,
        )
        for case in cases
    ]
    artifact_ready_count = sum(1 for row in case_rows if row["artifact_backed_evidence_depth"]["status"] == "pass")
    fresh_specialist_pass_count = sum(1 for row in case_rows if row["fresh_all_specialist_gold_pass"]["status"] == "pass")
    runtime_contract_ready_count = sum(1 for row in case_rows if row["runtime_contract"]["status"] == "pass")
    blocking_cases = [
        row["case_id"]
        for row in case_rows
        if row["artifact_backed_evidence_depth"]["status"] != "pass"
        or row["fresh_all_specialist_gold_pass"]["status"] != "pass"
        or row["runtime_contract"]["status"] != "pass"
    ]
    return {
        "schema_version": P33_MULTI_CASE_GOLDSET_READINESS_SCHEMA_VERSION,
        "status": "blocked_until_multicase_artifact_depth_and_fresh_specialists_pass"
        if blocking_cases
        else "pass",
        "case_count": len(case_rows),
        "artifact_ready_count": artifact_ready_count,
        "fresh_specialist_pass_count": fresh_specialist_pass_count,
        "runtime_contract_ready_count": runtime_contract_ready_count,
        "blocking_case_count": len(blocking_cases),
        "blocking_cases": blocking_cases,
        "case_results": case_rows,
        "compiled_contracts": {
            "rubric_vertical_playbook_contract_count": rubric_contracts.get("contract_count"),
            "negative_failure_gate_count": negative_gates.get("gate_count"),
        },
        "acceptance_policy": {
            "evidence_depth": "Each gold case needs artifact-backed source/depth rows, not only catalog or rubric text.",
            "specialist": "Targeted composite or stale specialist artifacts do not count. A fresh all-specialist gold pass is required per case before promotion.",
            "runtime": "Rubric and negative cases must be contract-translated and runtime-consumable before broader case expansion.",
        },
        "not_run": ["paid_all_specialist_rerun", "paid_memo_writer", "full_chain", "model_comparison"],
    }


def render_single_case_projection_markdown(replay: Mapping[str, Any]) -> str:
    renderer = replay.get("renderer_projection") if isinstance(replay.get("renderer_projection"), Mapping) else {}
    verifier = replay.get("final_verifier_projection") if isinstance(replay.get("final_verifier_projection"), Mapping) else {}
    workbench = replay.get("workbench_projection") if isinstance(replay.get("workbench_projection"), Mapping) else {}
    lines = [
        "# P33 Single Case Projection Replay v0.1",
        "",
        "## 结论",
        "",
        f"- status: `{replay.get('status')}`",
        f"- source artifact: `{replay.get('source_artifact')}`",
        "- 未运行：paid LLM、full-chain、模型对比、case expansion。",
        "",
        "## Renderer Projection",
        "",
        f"- status: `{renderer.get('status')}`",
        f"- rendered chars: `{renderer.get('rendered_answer_chars')}`",
        f"- citation labels: `{renderer.get('citation_label_count')}`",
        f"- internal marker hits: `{renderer.get('internal_marker_hits') or []}`",
        "",
        "## Final Verifier Projection",
        "",
        f"- status: `{verifier.get('status')}`",
        f"- deterministic status: `{verifier.get('deterministic_status')}`",
        f"- projected claims: `{_nested(verifier, 'projection_stats', 'projected_claim_count')}`",
        f"- known evidence refs: `{_nested(verifier, 'input_pack_fingerprint', 'known_evidence_ref_count')}`",
        f"- approx verifier prompt chars: `{_nested(verifier, 'input_pack_fingerprint', 'approx_total_prompt_chars_with_scaffold')}`",
        "",
        "## Workbench Projection",
        "",
        f"- status: `{workbench.get('status')}`",
        f"- counts: `{workbench.get('counts')}`",
        "",
        "## Rendered Workpaper Preview",
        "",
        str(renderer.get("rendered_answer") or "")[:6000],
        "",
    ]
    return "\n".join(lines)


def render_multicase_readiness_markdown(readiness: Mapping[str, Any]) -> str:
    lines = [
        "# P33 Multi-case Gold Set Readiness v0.1",
        "",
        "## 结论",
        "",
        f"- status: `{readiness.get('status')}`",
        f"- cases: `{readiness.get('case_count')}`",
        f"- artifact-ready: `{readiness.get('artifact_ready_count')}`",
        f"- fresh all-specialist pass: `{readiness.get('fresh_specialist_pass_count')}`",
        f"- runtime-contract-ready: `{readiness.get('runtime_contract_ready_count')}`",
        "",
        "这份 readiness 明确采用硬口径：multi-case gold-set 不能因为 catalog / rubric 已存在就通过；每个 case 都需要 artifact-backed evidence depth 和 fresh all-specialist gold pass。",
        "",
        "## Case Matrix",
        "",
        "| Case | Type | Evidence depth | Fresh all-specialist | Runtime contract | Blocking reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in readiness.get("case_results") or []:
        if not isinstance(row, Mapping):
            continue
        blocking = "; ".join(row.get("blocking_reasons") or [])
        lines.append(
            f"| `{row.get('case_id')}` | `{row.get('case_type')}` | `{_nested(row, 'artifact_backed_evidence_depth', 'status')}` | "
            f"`{_nested(row, 'fresh_all_specialist_gold_pass', 'status')}` | `{_nested(row, 'runtime_contract', 'status')}` | {blocking} |"
        )
    lines.append("")
    lines.append("## 下一步")
    lines.append("")
    lines.append("- 单 case projection 通过后，只能作为 AI/Semis scoped memo draft 的投影证据。")
    lines.append("- multi-case 下一步必须为每个 rubric case 准备 evidence-depth pack，再跑 fresh all-specialist gold pass。")
    lines.append("- 当前不得把 targeted specialist composite 当作 fresh all-specialist pass。")
    lines.append("")
    return "\n".join(lines)


def write_projection_replay_artifacts(
    *,
    memo_writer_node_result: str | Path = DEFAULT_MEMO_WRITER_NODE_RESULT,
    projection_json: str | Path = DEFAULT_PROJECTION_JSON,
    projection_md: str | Path = DEFAULT_PROJECTION_MD,
    multi_case_json: str | Path = DEFAULT_MULTI_CASE_JSON,
    multi_case_md: str | Path = DEFAULT_MULTI_CASE_MD,
) -> dict[str, Any]:
    replay = build_single_case_projection_replay(memo_writer_node_result)
    readiness = build_multicase_goldset_readiness(single_case_projection=replay)
    projection_json = Path(projection_json)
    projection_md = Path(projection_md)
    multi_case_json = Path(multi_case_json)
    multi_case_md = Path(multi_case_md)
    for path in (projection_json, projection_md, multi_case_json, multi_case_md):
        path.parent.mkdir(parents=True, exist_ok=True)
    projection_json.write_text(json.dumps(replay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    projection_md.write_text(render_single_case_projection_markdown(replay), encoding="utf-8")
    multi_case_json.write_text(json.dumps(readiness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    multi_case_md.write_text(render_multicase_readiness_markdown(readiness), encoding="utf-8")
    return {
        "single_case_projection": replay,
        "multi_case_readiness": readiness,
        "artifact_refs": {
            "projection_json": _rel(projection_json),
            "projection_md": _rel(projection_md),
            "multi_case_json": _rel(multi_case_json),
            "multi_case_md": _rel(multi_case_md),
        },
    }


def _multicase_readiness_row(
    case: Mapping[str, Any],
    *,
    matrix_by_case: Mapping[str, Mapping[str, Any]],
    single_case_projection: Mapping[str, Any],
    gold_content: Mapping[str, Any],
) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "")
    case_type = str(case.get("case_type") or "")
    matrix_row = matrix_by_case.get(case_id) if isinstance(matrix_by_case.get(case_id), Mapping) else {}
    is_ai_semis_deep = case_id == "ai_semis_dell_nvda_anchor_v0_1"
    evidence_depth = _case_evidence_depth_status(case_id, case_type, single_case_projection, gold_content)
    specialist_status = _case_fresh_specialist_status(case_id, case_type, single_case_projection)
    runtime_contract = _case_runtime_contract_status(case_id, case_type, matrix_row)
    blocking_reasons = []
    for key, status in (
        ("artifact_backed_evidence_depth", evidence_depth),
        ("fresh_all_specialist_gold_pass", specialist_status),
        ("runtime_contract", runtime_contract),
    ):
        if status["status"] != "pass":
            blocking_reasons.append(f"{key}:{status['status']}")
    return {
        "case_id": case_id,
        "case_type": case_type,
        "vertical": case.get("vertical") or "",
        "artifact_backed_evidence_depth": evidence_depth,
        "fresh_all_specialist_gold_pass": specialist_status,
        "runtime_contract": runtime_contract,
        "matrix_audit_status": matrix_row.get("status") or "",
        "is_current_single_case": is_ai_semis_deep,
        "blocking_reasons": blocking_reasons,
        "next_repair": matrix_row.get("next_repair") or [],
    }


def _case_evidence_depth_status(
    case_id: str,
    case_type: str,
    single_case_projection: Mapping[str, Any],
    gold_content: Mapping[str, Any],
) -> dict[str, Any]:
    if case_id == "ai_semis_dell_nvda_anchor_v0_1":
        markers = gold_content.get("gold_depth_markers") if isinstance(gold_content.get("gold_depth_markers"), Mapping) else {}
        lane_count = len(
            [
                key
                for key, value in (markers or {}).items()
                if key.endswith("_count") and isinstance(value, int) and value > 0
            ]
        )
        projection_pass = single_case_projection.get("status") == "pass"
        return {
            "status": "pass" if projection_pass and lane_count >= 5 else "fail",
            "basis": "ai_semis_gold_depth_content_pack_plus_single_case_projection",
            "lane_marker_count": lane_count,
            "single_case_projection_status": single_case_projection.get("status") or "",
        }
    return {
        "status": "missing_artifact_backed_evidence_pack",
        "basis": f"{case_type}_catalog_or_exemplar_only",
        "required_next_artifact": f"p33_goldset_{case_id}_evidence_depth_pack",
    }


def _case_fresh_specialist_status(
    case_id: str,
    case_type: str,
    single_case_projection: Mapping[str, Any],
) -> dict[str, Any]:
    if case_id == "ai_semis_dell_nvda_anchor_v0_1":
        return {
            "status": "blocked_targeted_composite_not_fresh_all_specialist",
            "basis": "accepted P33 specialist checkpoint was a targeted repaired composite, not a fresh all-specialist gold pass",
            "required_next_artifact": "fresh optional_specialist_subgraph all-specialist gold pass after evidence-depth projection",
        }
    return {
        "status": "missing_fresh_all_specialist_artifact",
        "basis": f"{case_type}_has_no_specialist_runtime_artifact",
        "required_next_artifact": f"p33_goldset_{case_id}_fresh_all_specialist_pass",
    }


def _case_runtime_contract_status(case_id: str, case_type: str, matrix_row: Mapping[str, Any]) -> dict[str, Any]:
    if case_type == "rubric_gold_case":
        return {
            "status": "pass" if matrix_row else "missing_matrix_contract",
            "basis": "rubric vertical playbook contract compiled from HumanmadeGoldSetSpec and answer exemplars",
        }
    if case_type == "negative_gold_case":
        return {
            "status": "pass" if matrix_row else "missing_negative_gate_contract",
            "basis": "negative case failure gate compiled from HumanmadeGoldSetSpec and answer exemplars",
        }
    if case_id == "ai_semis_dell_nvda_anchor_v0_1":
        return {"status": "pass", "basis": "deep gold case has source doc, audit spec, and P33 runtime artifacts"}
    return {"status": "missing_runtime_contract", "basis": "unknown_case_type"}


def _workbench_sections(memo: Mapping[str, Any], logic_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    claim_ids_by_dimension: dict[str, list[str]] = {}
    evidence_refs_by_dimension: dict[str, list[str]] = {}
    all_claim_ids: list[str] = []
    all_evidence_refs: list[str] = []
    for row in memo.get("memo_claims") or []:
        if not isinstance(row, Mapping):
            continue
        claim_id = str(row.get("claim_id") or "")
        if claim_id:
            all_claim_ids.append(claim_id)
        all_evidence_refs.extend(_string_list(row.get("evidence_refs") or row.get("refs")))
    for row in memo.get("dimension_analyses") or []:
        if not isinstance(row, Mapping):
            continue
        dimension_id = str(row.get("dimension_id") or "")
        claim_ids_by_dimension[dimension_id] = _string_list(row.get("claim_ids"))[:8]
        evidence_refs_by_dimension[dimension_id] = _string_list(row.get("evidence_refs") or row.get("refs"))[:8]
    sections = []
    for index, row in enumerate(logic_plan.get("sections") or [], start=1):
        if not isinstance(row, Mapping):
            continue
        section_id = str(row.get("section_id") or f"section_{index}")
        sections.append(
            {
                "section_id": section_id,
                "title": str(row.get("title") or section_id),
                "display_order": int(row.get("order") or index),
                "logic_role": str(row.get("logic_role") or ""),
                "claim_ids": _dedupe([*claim_ids_by_dimension.get(section_id, []), *_string_list(row.get("required_claim_ids"))]),
                "evidence_refs": _dedupe(evidence_refs_by_dimension.get(section_id, [])),
                "required_item_ids": _string_list(row.get("required_item_ids")),
                "source": "memo_logic_plan.sections",
            }
        )
    if sections:
        _append_workbench_review_sections(
            sections,
            memo=memo,
            logic_plan=logic_plan,
            all_claim_ids=_dedupe(all_claim_ids),
            all_evidence_refs=_dedupe(all_evidence_refs),
        )
        return sections
    for index, row in enumerate(memo.get("dimension_analyses") or [], start=1):
        if not isinstance(row, Mapping):
            continue
        section_id = str(row.get("dimension_id") or f"dimension_{index}")
        sections.append(
            {
                "section_id": section_id,
                "title": str(row.get("title") or section_id),
                "display_order": index,
                "logic_role": "dimension_analysis",
                "claim_ids": _string_list(row.get("claim_ids")),
                "evidence_refs": _string_list(row.get("evidence_refs") or row.get("refs")),
                "required_item_ids": [],
                "source": "memo_answer.dimension_analyses",
            }
        )
    _append_workbench_review_sections(
        sections,
        memo=memo,
        logic_plan=logic_plan,
        all_claim_ids=_dedupe(all_claim_ids),
        all_evidence_refs=_dedupe(all_evidence_refs),
    )
    return sections


def _append_workbench_review_sections(
    sections: list[dict[str, Any]],
    *,
    memo: Mapping[str, Any],
    logic_plan: Mapping[str, Any],
    all_claim_ids: list[str],
    all_evidence_refs: list[str],
) -> None:
    existing_ids = {str(section.get("section_id") or "") for section in sections}
    next_order = max([int(section.get("display_order") or 0) for section in sections] or [0]) + 1

    required_items = [row for row in logic_plan.get("required_item_answer_plan") or [] if isinstance(row, Mapping)]
    if required_items and "required_item_answers" not in existing_ids:
        sections.append(
            {
                "section_id": "required_item_answers",
                "title": "关键问题回应",
                "display_order": next_order,
                "logic_role": "required_item_answer_review",
                "claim_ids": all_claim_ids[:8],
                "evidence_refs": _dedupe(
                    [
                        ref
                        for item in required_items
                        for ref in _string_list(item.get("required_evidence_roles") or item.get("evidence_refs"))
                    ]
                )[:12],
                "required_item_ids": _dedupe(
                    [str(item.get("question_item_id") or "") for item in required_items if item.get("question_item_id")]
                ),
                "source": "memo_logic_plan.required_item_answer_plan",
            }
        )
        next_order += 1

    supplemental_specs = [
        ("investment_implications", "投资含义", memo.get("investment_implications")),
        ("what_would_change_view", "什么会改变判断", memo.get("what_would_change_view")),
        ("evidence_gaps_but_actionable", "可行动的证据缺口", memo.get("evidence_gaps_but_actionable")),
    ]
    for section_id, title, rows in supplemental_specs:
        if section_id in existing_ids or not rows:
            continue
        sections.append(
            {
                "section_id": section_id,
                "title": title,
                "display_order": next_order,
                "logic_role": "review_surface",
                "claim_ids": all_claim_ids[:8],
                "evidence_refs": all_evidence_refs[:12],
                "required_item_ids": [],
                "source": f"memo_answer.{section_id}",
            }
        )
        next_order += 1


def _workbench_claims(memo: Mapping[str, Any]) -> list[dict[str, Any]]:
    claims = []
    for index, row in enumerate(memo.get("memo_claims") or [], start=1):
        if not isinstance(row, Mapping):
            continue
        claims.append(
            {
                "claim_card_id": str(row.get("claim_id") or f"memo_claim_{index}"),
                "claim_text": str(row.get("claim") or row.get("text") or ""),
                "dimension_id": str(row.get("memo_slot") or row.get("dimension_id") or ""),
                "confidence": str(row.get("confidence") or ""),
                "materiality": str(row.get("materiality") or ""),
                "evidence_refs": _string_list(row.get("evidence_refs") or row.get("refs")),
                "cannot_infer": _string_list(row.get("caveats") or row.get("cannot_infer")),
                "source": "memo_answer.memo_claims",
            }
        )
    return claims


def _workbench_gaps(memo: Mapping[str, Any], judgment: Mapping[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    for index, row in enumerate(memo.get("evidence_gaps_but_actionable") or [], start=1):
        if isinstance(row, Mapping):
            gaps.append(
                {
                    "gap_id": str(row.get("gap_id") or f"memo_gap_{index}"),
                    "gap_type": str(row.get("gap_type") or row.get("type") or "actionable_evidence_gap"),
                    "description": str(row.get("text") or row.get("description") or ""),
                    "evidence_refs": _string_list(row.get("evidence_refs") or row.get("refs")),
                    "source": "memo_answer.evidence_gaps_but_actionable",
                }
            )
        elif str(row or "").strip():
            gaps.append(
                {
                    "gap_id": f"memo_gap_{index}",
                    "gap_type": "actionable_evidence_gap",
                    "description": str(row),
                    "evidence_refs": [],
                    "source": "memo_answer.evidence_gaps_but_actionable",
                }
            )
    for index, row in enumerate(judgment.get("unsupported_claims") or [], start=1):
        if not isinstance(row, Mapping):
            continue
        if len(gaps) >= 8:
            break
        gaps.append(
            {
                "gap_id": str(row.get("claim_id") or f"unsupported_claim_{index}"),
                "gap_type": "unsupported_or_bounded_claim",
                "description": str(row.get("claim") or row.get("reason") or ""),
                "evidence_refs": _string_list(row.get("evidence_refs") or row.get("refs")),
                "source": "verified_judgment_plan.unsupported_claims",
            }
        )
    return gaps


def _case_id_from_artifact(node_result: Mapping[str, Any], path: Path) -> str:
    contract = node_result.get("case_contract") if isinstance(node_result.get("case_contract"), Mapping) else {}
    return str(node_result.get("case_id") or contract.get("case_id") or path.parent.name)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item) for item in value if str(item or "").strip()]
    return []


def _dedupe(values: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _nested(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _rel(path: str | Path) -> str:
    candidate = Path(path).resolve()
    try:
        return candidate.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(candidate)
