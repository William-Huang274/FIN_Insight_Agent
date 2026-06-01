"""Audit Fin Agent layer quality from saved artifacts.

This script is intentionally artifact-only. It does not call an LLM, retrieval
tool, database, or external API. It converts existing LangGraph/eval summaries
into the project-wide quality framework defined in docs/eval.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUBRIC = REPO_ROOT / "configs" / "fin_agent_quality_rubric_v0_1.json"
QUALITY_SCHEMA_VERSION = "fin_agent_layer_quality_audit_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit saved Fin Agent artifacts against the layered quality framework.")
    parser.add_argument("--summary", type=Path, required=True, help="Saved activation_diagnostic.json or real_chain_eval_summary.json.")
    parser.add_argument("--artifact-root", type=Path, default=None, help="Optional case artifact root for full-chain audits.")
    parser.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--md-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless the audit gate passes.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = _read_json(args.summary)
    rubric = _read_json(args.rubric)
    audit = audit_summary(summary, rubric=rubric, summary_path=args.summary, artifact_root=args.artifact_root)
    json_out = args.json_out or args.summary.with_name("fin_agent_layer_quality_audit.json")
    md_out = args.md_out or args.summary.with_name("fin_agent_layer_quality_audit.md")
    json_out.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps(_stdout_summary(audit, json_out, md_out), ensure_ascii=False, indent=2))
    if args.strict and audit["gate_status"] != "pass":
        return 1
    return 0


def audit_summary(
    summary: Mapping[str, Any],
    *,
    rubric: Mapping[str, Any],
    summary_path: Path | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    source_schema = str(summary.get("schema_version") or "")
    if source_schema == "sec_agent_research_lead_activation_diagnostic_v0.1":
        return _audit_research_lead_activation(summary, rubric=rubric, summary_path=summary_path)
    if source_schema == "sec_agent_universe_relationship_diagnostic_v0.1":
        return _audit_universe_relationship(summary, rubric=rubric, summary_path=summary_path)
    if source_schema == "sec_agent_evidence_operator_diagnostic_v0.1":
        return _audit_evidence_operator(summary, rubric=rubric, summary_path=summary_path)
    if source_schema == "sec_agent_coverage_reflection_diagnostic_v0.1":
        return _audit_coverage_reflection(summary, rubric=rubric, summary_path=summary_path)
    if "cases" in summary and ("real_chain" in source_schema or "multi_agent" in source_schema or summary.get("output_quality_audit")):
        return _audit_real_chain(summary, rubric=rubric, summary_path=summary_path, artifact_root=artifact_root)
    return _audit_unknown(summary, rubric=rubric, summary_path=summary_path)


def render_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        f"# Fin Agent Layer Quality Audit: {audit.get('run_id') or ''}",
        "",
        f"- Source type: `{audit.get('source_type') or ''}`",
        f"- Gate: `{audit.get('gate_status') or ''}`",
        f"- Weighted score: `{audit.get('weighted_score')}`",
        f"- Diagnostic only: `{str(bool(audit.get('diagnostic_only'))).lower()}`",
        "",
        "## Stage Summary",
        "",
        "| Stage | Gate | Cases | Pass rate | Failed checks |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for stage in audit.get("stages") or []:
        if not isinstance(stage, Mapping):
            continue
        failed = ", ".join(stage.get("failed_checks") or []) or "none"
        lines.append(
            "| {stage} | {gate} | {cases} | {rate} | {failed} |".format(
                stage=stage.get("stage_id") or "",
                gate=stage.get("gate_status") or "",
                cases=stage.get("case_count") or 0,
                rate=_fmt(stage.get("pass_rate")),
                failed=failed,
            )
        )
    lines.extend(["", "## Dimension Scores", "", "| Dimension | Score | Weight | Basis |", "| --- | ---: | ---: | --- |"])
    for dimension in audit.get("dimension_scores") or []:
        if not isinstance(dimension, Mapping):
            continue
        lines.append(
            "| {label} | {score} | {weight} | {basis} |".format(
                label=dimension.get("label") or dimension.get("id") or "",
                score=_fmt(dimension.get("score")),
                weight=_fmt(dimension.get("weight")),
                basis=str(dimension.get("basis") or ""),
            )
        )
    flags = audit.get("quality_flags") or []
    lines.extend(["", "## Quality Flags", ""])
    if flags:
        for flag in flags:
            lines.append(f"- `{flag}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Next Actions", ""])
    for action in audit.get("next_actions") or []:
        lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def _audit_research_lead_activation(
    summary: Mapping[str, Any],
    *,
    rubric: Mapping[str, Any],
    summary_path: Path | None,
) -> dict[str, Any]:
    cases = [case for case in summary.get("cases") or [] if isinstance(case, Mapping)]
    stage = _stage_from_case_checks(
        "research_lead",
        cases,
        required_checks=_required_checks(rubric, "research_lead"),
        case_check_getter=lambda case: case.get("checks") if isinstance(case.get("checks"), Mapping) else {},
        case_pass_getter=lambda case: str(case.get("status") or "") == "pass",
    )
    stage_gate = stage["gate_status"] == "pass" and str(summary.get("gate_status") or "") == "pass"
    dimensions = _dimension_scores_for_research_lead(stage, rubric)
    weighted = _weighted_score(dimensions)
    flags = []
    if not stage_gate:
        flags.append("research_lead_stage_gate_failed")
    audit_gate = "pass" if stage_gate else "fail"
    return _base_audit(
        summary=summary,
        rubric=rubric,
        source_type="research_lead_activation",
        summary_path=summary_path,
        stages=[stage],
        dimensions=dimensions,
        quality_flags=flags,
        gate_status=audit_gate,
        next_actions=_next_actions(stage_gate=audit_gate == "pass", source_type="research_lead_activation"),
    )


def _audit_real_chain(
    summary: Mapping[str, Any],
    *,
    rubric: Mapping[str, Any],
    summary_path: Path | None,
    artifact_root: Path | None,
) -> dict[str, Any]:
    cases = [case for case in summary.get("cases") or [] if isinstance(case, Mapping)]
    stages = [
        _stage_from_layer_checks("research_lead", cases, required_checks=_required_checks(rubric, "research_lead")),
        _stage_from_layer_checks("universe_relationship", cases, required_checks=[]),
        _stage_from_layer_checks("evidence_operators", cases, required_checks=_required_checks(rubric, "evidence_operators")),
        _stage_from_layer_checks("specialists", cases, required_checks=_required_checks(rubric, "specialists")),
        _stage_from_memo_verifier_checks("memo_writer", cases),
        _stage_from_memo_verifier_checks("verifier", cases),
        _stage_from_renderer_checks(cases),
    ]
    output_audit = _load_output_quality_audit(summary, artifact_root)
    flags = _quality_flags_from_real_chain(summary, output_audit)
    dimensions = _dimension_scores_for_real_chain(stages, flags, output_audit, rubric)
    weighted = _weighted_score(dimensions)
    stage_gate = all(stage["gate_status"] in {"pass", "skipped"} for stage in stages)
    summary_gate = str(summary.get("gate_status") or "") == "pass"
    high_risk_cases = _high_risk_case_count(output_audit)
    max_high_risk = int(((rubric.get("stage_gates") or {}).get("full_chain") or {}).get("max_high_risk_quality_cases", 0))
    audit_gate = "pass" if stage_gate and summary_gate and high_risk_cases <= max_high_risk and weighted >= _deliverable_threshold(rubric) else "fail"
    return _base_audit(
        summary=summary,
        rubric=rubric,
        source_type="real_llm_full_chain",
        summary_path=summary_path,
        stages=stages,
        dimensions=dimensions,
        quality_flags=flags,
        gate_status=audit_gate,
        next_actions=_next_actions(stage_gate=audit_gate == "pass", source_type="real_llm_full_chain", flags=flags),
        extra={
            "output_quality_audit_present": bool(output_audit),
            "high_risk_quality_cases": high_risk_cases,
            "max_high_risk_quality_cases": max_high_risk,
        },
    )


def _audit_universe_relationship(
    summary: Mapping[str, Any],
    *,
    rubric: Mapping[str, Any],
    summary_path: Path | None,
) -> dict[str, Any]:
    cases = [case for case in summary.get("cases") or [] if isinstance(case, Mapping)]
    stage = _stage_from_case_checks(
        "universe_relationship",
        cases,
        required_checks=[
            *(_required_checks(rubric, "universe_relationship")),
            "relationship_lookup_has_rows",
            "llm_route_pass",
            "fallback_not_used",
            "validation_pass",
            "plan_relationships_present",
            "relationship_refs_present",
            "relationship_scope_only",
            "financial_fact_policy_preserved",
            "economic_link_map_pass",
            "economic_entities_present",
            "economic_links_present",
            "economic_mechanisms_present",
            "investment_implications_present",
            "relationship_plan_covers_lookup",
            "relationship_inference_levels_present",
            "inferred_relationships_not_confirmed_direct",
            "external_confirmation_gaps_recorded",
        ],
        case_check_getter=lambda case: case.get("checks") if isinstance(case.get("checks"), Mapping) else {},
        case_pass_getter=lambda case: str(case.get("status") or "") == "pass",
    )
    stage_gate = stage["gate_status"] == "pass" and str(summary.get("gate_status") or "") == "pass"
    dimensions = _dimension_scores_for_universe_relationship(stage, rubric)
    flags = []
    if not stage_gate:
        flags.append("universe_relationship_stage_gate_failed")
    audit_gate = "pass" if stage_gate else "fail"
    return _base_audit(
        summary=summary,
        rubric=rubric,
        source_type="universe_relationship",
        summary_path=summary_path,
        stages=[stage],
        dimensions=dimensions,
        quality_flags=flags,
        gate_status=audit_gate,
        next_actions=_next_actions(stage_gate=audit_gate == "pass", source_type="universe_relationship"),
    )


def _audit_evidence_operator(
    summary: Mapping[str, Any],
    *,
    rubric: Mapping[str, Any],
    summary_path: Path | None,
) -> dict[str, Any]:
    cases = [case for case in summary.get("cases") or [] if isinstance(case, Mapping)]
    required = [
        *(_required_checks(rubric, "evidence_operators")),
        "real_retrieval_mode_required",
        "sec_search_not_dry_run",
        "sec_search_errors_absent",
        "sec_search_context_rows_present",
        "sec_search_bm25_candidates_present",
        "sec_search_bge_rerank_present",
        "bge_cuda_when_auto_and_available",
        "exact_value_ledger_rows_present",
        "market_rows_present",
        "industry_rows_present",
        "relationship_rows_available",
        "row_payload_usable",
    ]
    stage = _stage_from_case_checks(
        "evidence_operators",
        cases,
        required_checks=required,
        case_check_getter=lambda case: case.get("checks") if isinstance(case.get("checks"), Mapping) else {},
        case_pass_getter=lambda case: str(case.get("status") or "") == "pass",
    )
    stage_gate = stage["gate_status"] == "pass" and str(summary.get("gate_status") or "") == "pass"
    dimensions = _dimension_scores_for_evidence_operator(stage, rubric)
    flags = []
    if not stage_gate:
        flags.append("evidence_operator_stage_gate_failed")
    audit_gate = "pass" if stage_gate else "fail"
    return _base_audit(
        summary=summary,
        rubric=rubric,
        source_type="evidence_operators",
        summary_path=summary_path,
        stages=[stage],
        dimensions=dimensions,
        quality_flags=flags,
        gate_status=audit_gate,
        next_actions=_next_actions(stage_gate=audit_gate == "pass", source_type="evidence_operators"),
        extra={
            "retrieval_metrics": dict(summary.get("metrics") or {}),
        },
    )


def _audit_coverage_reflection(
    summary: Mapping[str, Any],
    *,
    rubric: Mapping[str, Any],
    summary_path: Path | None,
) -> dict[str, Any]:
    cases = [case for case in summary.get("cases") or [] if isinstance(case, Mapping)]
    required = [
        *(_required_checks(rubric, "coverage_reflection")),
        "coverage_report_present",
        "second_pass_decision_present",
        "source_gap_boundary_valid",
        "no_duplicate_or_budget_loop_break",
        "s3_rows_available_for_reflection",
    ]
    stage = _stage_from_case_checks(
        "coverage_reflection",
        cases,
        required_checks=required,
        case_check_getter=lambda case: case.get("checks") if isinstance(case.get("checks"), Mapping) else {},
        case_pass_getter=lambda case: str(case.get("status") or "") == "pass",
    )
    stage_gate = stage["gate_status"] == "pass" and str(summary.get("gate_status") or "") == "pass"
    dimensions = _dimension_scores_for_coverage_reflection(stage, rubric)
    flags = []
    if not stage_gate:
        flags.append("coverage_reflection_stage_gate_failed")
    audit_gate = "pass" if stage_gate else "fail"
    return _base_audit(
        summary=summary,
        rubric=rubric,
        source_type="coverage_reflection",
        summary_path=summary_path,
        stages=[stage],
        dimensions=dimensions,
        quality_flags=flags,
        gate_status=audit_gate,
        next_actions=_next_actions(stage_gate=audit_gate == "pass", source_type="coverage_reflection"),
        extra={"coverage_metrics": dict(summary.get("metrics") or {})},
    )


def _audit_unknown(
    summary: Mapping[str, Any],
    *,
    rubric: Mapping[str, Any],
    summary_path: Path | None,
) -> dict[str, Any]:
    dimensions = _neutral_dimensions(rubric, score=0, basis="unknown summary schema")
    return _base_audit(
        summary=summary,
        rubric=rubric,
        source_type="unknown",
        summary_path=summary_path,
        stages=[],
        dimensions=dimensions,
        quality_flags=["unknown_summary_schema"],
        gate_status="fail",
        next_actions=["Use activation_diagnostic.json or real_chain_eval_summary.json as input."],
    )


def _stage_from_layer_checks(stage_id: str, cases: list[Mapping[str, Any]], *, required_checks: list[str]) -> dict[str, Any]:
    relevant = []
    failed_checks: set[str] = set()
    for case in cases:
        layer_checks = case.get("layer_checks") if isinstance(case.get("layer_checks"), Mapping) else {}
        layer = layer_checks.get(stage_id) if isinstance(layer_checks.get(stage_id), Mapping) else None
        if layer is None:
            continue
        if _layer_not_required(stage_id, case, layer):
            continue
        relevant.append(case)
        checks = _flatten_bool_mapping(layer)
        names = required_checks or list(checks)
        for name in names:
            if name in checks and not checks[name]:
                failed_checks.add(name)
    if not relevant:
        return _stage_result(stage_id, "skipped", 0, 0, [])
    pass_count = 0
    for case in relevant:
        layer = ((case.get("layer_checks") or {}).get(stage_id) or {})
        checks = _flatten_bool_mapping(layer)
        names = required_checks or list(checks)
        if all(checks.get(name, True) for name in names):
            pass_count += 1
    return _stage_result(stage_id, "pass" if pass_count == len(relevant) else "fail", len(relevant), pass_count, sorted(failed_checks))


def _stage_from_case_checks(
    stage_id: str,
    cases: list[Mapping[str, Any]],
    *,
    required_checks: list[str],
    case_check_getter,
    case_pass_getter,
) -> dict[str, Any]:
    failed_checks: set[str] = set()
    pass_count = 0
    for case in cases:
        checks = _flatten_bool_mapping(case_check_getter(case))
        for name in required_checks:
            if name in checks and not checks[name]:
                failed_checks.add(name)
        if case_pass_getter(case) and all(checks.get(name, True) for name in required_checks):
            pass_count += 1
    gate = "pass" if cases and pass_count == len(cases) else "fail"
    return _stage_result(stage_id, gate, len(cases), pass_count, sorted(failed_checks))


def _stage_from_memo_verifier_checks(stage_id: str, cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    relevant = []
    pass_count = 0
    failed: set[str] = set()
    for case in cases:
        layer_checks = case.get("layer_checks") if isinstance(case.get("layer_checks"), Mapping) else {}
        layer = layer_checks.get("memo_verifier") if isinstance(layer_checks.get("memo_verifier"), Mapping) else {}
        if not layer:
            continue
        relevant.append(case)
        checks = _flatten_bool_mapping(layer)
        if stage_id == "memo_writer":
            names = ["memo_llm_pass", "memo_status_allowed", "rendered_answer_has_memo_claims", "rendered_answer_has_evidence_refs"]
        else:
            names = ["claim_verification_pass", "verifier_llm_pass"]
            agent_audit = case.get("agent_audit") if isinstance(case.get("agent_audit"), Mapping) else {}
            verifier = agent_audit.get("verifier") if isinstance(agent_audit.get("verifier"), Mapping) else {}
            projection = verifier.get("input_projection") if isinstance(verifier.get("input_projection"), Mapping) else {}
            checks["verifier_projection_present"] = bool(projection)
            names.append("verifier_projection_present")
        for name in names:
            if name in checks and not checks[name]:
                failed.add(name)
        if all(checks.get(name, True) for name in names):
            pass_count += 1
    if not relevant:
        return _stage_result(stage_id, "skipped", 0, 0, [])
    return _stage_result(stage_id, "pass" if pass_count == len(relevant) else "fail", len(relevant), pass_count, sorted(failed))


def _stage_from_renderer_checks(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    relevant = []
    pass_count = 0
    failed: set[str] = set()
    for case in cases:
        relevant.append(case)
        checks = {
            "rendered_answer_present": int(case.get("rendered_answer_chars") or len(str(case.get("rendered_answer_preview") or ""))) > 0,
            "rendered_answer_has_evidence_refs": bool(case.get("rendered_answer_has_evidence_refs")),
            "no_internal_trace_leak": _no_internal_trace_leak(str(case.get("rendered_answer_preview") or "")),
        }
        for name, value in checks.items():
            if not value:
                failed.add(name)
        if all(checks.values()):
            pass_count += 1
    if not relevant:
        return _stage_result("renderer", "skipped", 0, 0, [])
    return _stage_result("renderer", "pass" if pass_count == len(relevant) else "fail", len(relevant), pass_count, sorted(failed))


def _stage_result(stage_id: str, gate_status: str, case_count: int, pass_count: int, failed_checks: list[str]) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "gate_status": gate_status,
        "case_count": case_count,
        "pass_count": pass_count,
        "pass_rate": round(pass_count / case_count, 4) if case_count else 0.0,
        "failed_checks": failed_checks,
    }


def _dimension_scores_for_research_lead(stage: Mapping[str, Any], rubric: Mapping[str, Any]) -> list[dict[str, Any]]:
    stage_ok = stage.get("gate_status") == "pass"
    scores = []
    for dim in _dimensions(rubric):
        dim_id = str(dim.get("id") or "")
        if dim_id in {"mandate_fit", "permissions_and_auditability", "cost_quality_efficiency"}:
            score = 3.2 if stage_ok else 1.0
            basis = "Research Lead stage checks"
        elif dim_id == "evidence_boundary":
            score = 3.0 if stage_ok else 1.0
            basis = "EvidenceRequirementPlan validation"
        else:
            score = 2.4 if stage_ok else 0.5
            basis = "not fully evaluated until downstream stages"
        scores.append(_dimension_result(dim, score, basis))
    return scores


def _dimension_scores_for_universe_relationship(stage: Mapping[str, Any], rubric: Mapping[str, Any]) -> list[dict[str, Any]]:
    stage_ok = stage.get("gate_status") == "pass"
    scores = []
    for dim in _dimensions(rubric):
        dim_id = str(dim.get("id") or "")
        if dim_id == "economic_relationship_reasoning":
            score = 3.2 if stage_ok else 1.0
            basis = "Universe relationship plan and refs"
        elif dim_id in {"mandate_fit", "evidence_boundary", "permissions_and_auditability"}:
            score = 3.0 if stage_ok else 1.0
            basis = "bounded relationship lookup and source-boundary checks"
        elif dim_id == "cost_quality_efficiency":
            score = 3.0 if stage_ok else 1.0
            basis = "single-layer relationship route"
        else:
            score = 2.4 if stage_ok else 0.5
            basis = "not fully evaluated until downstream stages"
        scores.append(_dimension_result(dim, score, basis))
    return scores


def _dimension_scores_for_evidence_operator(stage: Mapping[str, Any], rubric: Mapping[str, Any]) -> list[dict[str, Any]]:
    stage_ok = stage.get("gate_status") == "pass"
    scores = []
    for dim in _dimensions(rubric):
        dim_id = str(dim.get("id") or "")
        if dim_id in {"evidence_boundary", "financial_metric_reasoning", "permissions_and_auditability"}:
            score = 3.2 if stage_ok else 1.0
            basis = "real retrieval rows, runtime ledger, and permission checks"
        elif dim_id == "economic_relationship_reasoning":
            score = 3.0 if stage_ok else 1.0
            basis = "relationship rows preserved for sector-depth evidence layer"
        elif dim_id == "cost_quality_efficiency":
            score = 3.0 if stage_ok else 1.0
            basis = "tool budget, duplicate, and rerank execution checks"
        else:
            score = 2.4 if stage_ok else 0.5
            basis = "not fully evaluated until specialist/memo stages"
        scores.append(_dimension_result(dim, score, basis))
    return scores


def _dimension_scores_for_coverage_reflection(stage: Mapping[str, Any], rubric: Mapping[str, Any]) -> list[dict[str, Any]]:
    stage_ok = stage.get("gate_status") == "pass"
    scores = []
    for dim in _dimensions(rubric):
        dim_id = str(dim.get("id") or "")
        if dim_id in {"evidence_boundary", "cost_quality_efficiency", "permissions_and_auditability"}:
            score = 3.2 if stage_ok else 1.0
            basis = "coverage gap classification and bounded second-pass policy"
        elif dim_id in {"mandate_fit", "economic_relationship_reasoning", "financial_metric_reasoning"}:
            score = 3.0 if stage_ok else 1.0
            basis = "reflection over passed evidence-operator artifacts"
        else:
            score = 2.4 if stage_ok else 0.5
            basis = "not fully evaluated until specialist/memo stages"
        scores.append(_dimension_result(dim, score, basis))
    return scores


def _dimension_scores_for_real_chain(
    stages: list[Mapping[str, Any]],
    flags: list[str],
    output_audit: Mapping[str, Any],
    rubric: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_stage = {str(stage.get("stage_id") or ""): stage for stage in stages}
    scores = []
    for dim in _dimensions(rubric):
        dim_id = str(dim.get("id") or "")
        score = 3.2
        basis = "all layer gates passed"
        if dim_id == "mandate_fit":
            score, basis = _score_from_stage(by_stage.get("research_lead"), "Research Lead layer")
        elif dim_id == "evidence_boundary":
            evidence_score, _ = _score_from_stage(by_stage.get("evidence_operators"), "Evidence operator layer")
            verifier_score, _ = _score_from_stage(by_stage.get("verifier"), "Verifier layer")
            score = min(evidence_score, verifier_score)
            basis = "evidence operators + verifier"
        elif dim_id == "financial_metric_reasoning":
            score, basis = _score_from_stage(by_stage.get("specialists"), "Specialist ClaimCards")
        elif dim_id == "economic_relationship_reasoning":
            universe_score, _ = _score_from_stage(by_stage.get("universe_relationship"), "Universe relationship")
            specialist_score, _ = _score_from_stage(by_stage.get("specialists"), "Specialist relationship consumption")
            score = min(universe_score if universe_score else 2.4, specialist_score)
            basis = "relationship + industry specialist gates"
        elif dim_id == "investment_thesis_quality":
            memo_score, _ = _score_from_stage(by_stage.get("memo_writer"), "Memo Writer")
            specialist_score, _ = _score_from_stage(by_stage.get("specialists"), "Specialists")
            score = min(memo_score, specialist_score)
            basis = "specialists + memo writer"
        elif dim_id == "risk_counterevidence_balance":
            score, basis = _score_from_stage(by_stage.get("specialists"), "Risk and specialist gates")
        elif dim_id == "answer_usability":
            score, basis = _score_from_stage(by_stage.get("renderer"), "Renderer")
        elif dim_id == "cost_quality_efficiency":
            score, basis = _cost_efficiency_score(flags, output_audit)
        elif dim_id == "permissions_and_auditability":
            score, basis = _permissions_score(stages)
        if "high_risk_quality_case_present" in flags and dim_id in {"investment_thesis_quality", "answer_usability", "cost_quality_efficiency"}:
            score = min(score, 2.0)
            basis += "; high-risk output-quality audit"
        scores.append(_dimension_result(dim, score, basis))
    return scores


def _neutral_dimensions(rubric: Mapping[str, Any], *, score: float, basis: str) -> list[dict[str, Any]]:
    return [_dimension_result(dim, score, basis) for dim in _dimensions(rubric)]


def _base_audit(
    *,
    summary: Mapping[str, Any],
    rubric: Mapping[str, Any],
    source_type: str,
    summary_path: Path | None,
    stages: list[Mapping[str, Any]],
    dimensions: list[Mapping[str, Any]],
    quality_flags: list[str],
    gate_status: str,
    next_actions: list[str],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    weighted = _weighted_score(dimensions)
    payload = {
        "schema_version": QUALITY_SCHEMA_VERSION,
        "rubric_schema_version": str(rubric.get("schema_version") or ""),
        "source_type": source_type,
        "source_summary_path": str(summary_path.resolve()) if summary_path else "",
        "run_id": str(summary.get("run_id") or ""),
        "diagnostic_only": True,
        "gate_status": gate_status,
        "weighted_score": weighted,
        "stages": [dict(stage) for stage in stages],
        "dimension_scores": [dict(dim) for dim in dimensions],
        "quality_flags": sorted(set(quality_flags)),
        "next_actions": next_actions,
    }
    if extra:
        payload.update(dict(extra))
    return payload


def _required_checks(rubric: Mapping[str, Any], stage_id: str) -> list[str]:
    stages = rubric.get("stage_gates") if isinstance(rubric.get("stage_gates"), Mapping) else {}
    stage = stages.get(stage_id) if isinstance(stages.get(stage_id), Mapping) else {}
    return [str(item) for item in stage.get("required_checks") or []]


def _dimensions(rubric: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [row for row in rubric.get("dimensions") or [] if isinstance(row, Mapping)]


def _dimension_result(dim: Mapping[str, Any], score: float, basis: str) -> dict[str, Any]:
    return {
        "id": str(dim.get("id") or ""),
        "label": str(dim.get("label") or dim.get("id") or ""),
        "weight": float(dim.get("weight") or 0),
        "score": round(max(0.0, min(4.0, float(score))), 3),
        "basis": basis,
    }


def _weighted_score(dimensions: list[Mapping[str, Any]]) -> float:
    total_weight = sum(float(dim.get("weight") or 0) for dim in dimensions)
    if total_weight <= 0:
        return 0.0
    total = sum(float(dim.get("score") or 0) * float(dim.get("weight") or 0) for dim in dimensions)
    return round(total / total_weight, 3)


def _score_from_stage(stage: Mapping[str, Any] | None, label: str) -> tuple[float, str]:
    if not stage:
        return 2.4, f"{label} not evaluated"
    status = stage.get("gate_status")
    if status == "pass":
        return 3.2, f"{label} passed"
    if status == "skipped":
        return 2.4, f"{label} skipped for this case set"
    return 1.0, f"{label} failed: {', '.join(stage.get('failed_checks') or [])}"


def _cost_efficiency_score(flags: list[str], output_audit: Mapping[str, Any]) -> tuple[float, str]:
    cost_flags = {
        "high_total_token_cost",
        "memo_writer_high_token_cost",
        "verifier_high_token_cost",
        "low_rendered_claim_token_efficiency",
        "low_claim_card_token_efficiency",
        "low_memo_chars_per_token",
        "memo_writer_retry_cost_present",
    }
    hits = sorted(cost_flags & set(flags))
    if not output_audit:
        return 2.4, "cost-quality audit not available"
    if len(hits) >= 3:
        return 1.6, "multiple cost-quality flags: " + ", ".join(hits)
    if hits:
        return 2.4, "cost-quality flags: " + ", ".join(hits)
    return 3.2, "no major cost-quality flags"


def _permissions_score(stages: list[Mapping[str, Any]]) -> tuple[float, str]:
    for stage in stages:
        failed = set(stage.get("failed_checks") or [])
        if any("ownership" in item or "permission" in item or "duplicate" in item or "budget" in item for item in failed):
            return 1.0, f"permission/audit failure in {stage.get('stage_id')}"
    return 3.2, "no permission or audit gate failure"


def _quality_flags_from_real_chain(summary: Mapping[str, Any], output_audit: Mapping[str, Any]) -> list[str]:
    flags: list[str] = []
    if str(summary.get("gate_status") or "") != "pass":
        flags.append("real_chain_gate_failed")
    if output_audit:
        issue_counts = output_audit.get("issue_counts") if isinstance(output_audit.get("issue_counts"), Mapping) else {}
        for issue, count in issue_counts.items():
            if int(count or 0) > 0:
                flags.append(str(issue))
        if _high_risk_case_count(output_audit) > 0:
            flags.append("high_risk_quality_case_present")
    else:
        flags.append("output_quality_audit_missing")
    return sorted(set(flags))


def _load_output_quality_audit(summary: Mapping[str, Any], artifact_root: Path | None) -> dict[str, Any]:
    if artifact_root:
        path = artifact_root / "multi_agent_output_quality_audit.json"
        if path.exists():
            return _read_json(path)
    embedded = summary.get("output_quality_audit")
    if isinstance(embedded, Mapping) and embedded.get("issue_counts"):
        return dict(embedded)
    return {}


def _high_risk_case_count(output_audit: Mapping[str, Any]) -> int:
    if not output_audit:
        return 0
    cases = output_audit.get("cases") if isinstance(output_audit.get("cases"), list) else []
    if cases:
        return sum(1 for case in cases if isinstance(case, Mapping) and case.get("quality_risk_level") == "high")
    risk_levels = output_audit.get("case_risk_levels") if isinstance(output_audit.get("case_risk_levels"), Mapping) else {}
    return sum(1 for value in risk_levels.values() if str(value) == "high")


def _layer_not_required(stage_id: str, case: Mapping[str, Any], layer: Mapping[str, Any]) -> bool:
    if stage_id == "universe_relationship":
        required = bool(case.get("require_universe_llm_pass")) or "universe_relationship" in set(_string_list(case.get("required_agents")))
        return not required
    if stage_id == "specialists":
        required_agents = _string_list(case.get("expected_specialist_agents"))
        return not required_agents
    return False


def _flatten_bool_mapping(value: Mapping[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for key, item in value.items():
        if isinstance(item, bool):
            checks[str(key)] = item
        elif isinstance(item, Mapping):
            nested = _flatten_bool_mapping(item)
            for nested_key, nested_value in nested.items():
                checks[f"{key}.{nested_key}"] = nested_value
    return checks


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _no_internal_trace_leak(text: str) -> bool:
    lowered = text.lower()
    forbidden = ["tool_call_ledger", "langgraph_native_summary", "api_key", "sk-", "raw_evidence", "prompt_request"]
    return not any(item in lowered for item in forbidden)


def _deliverable_threshold(rubric: Mapping[str, Any]) -> float:
    scale = rubric.get("score_scale") if isinstance(rubric.get("score_scale"), Mapping) else {}
    return float(scale.get("deliverable_min_weighted_score") or 3.0)


def _next_actions(*, stage_gate: bool, source_type: str, flags: list[str] | None = None) -> list[str]:
    flags = flags or []
    if source_type == "research_lead_activation":
        if stage_gate:
            return ["Proceed to S2 Universe / Relationship using the passed activation artifacts."]
        return ["Fix Research Lead mode/scope/evidence requirement failures before running downstream agents."]
    if source_type == "universe_relationship":
        if stage_gate:
            return ["Proceed to S3 Evidence Operators using the passed S1 activation and S2 relationship artifacts."]
        return ["Fix Universe / Relationship lookup, prompt, schema, or relationship-pack selection before retrieval."]
    if source_type == "evidence_operators":
        if stage_gate:
            return ["Proceed to S4 Coverage / Reflection using the passed retrieval rows, runtime ledger, and relationship artifacts."]
        return ["Fix retrieval policy, ledger/source inventory, row selector, or reranker runtime before running specialists."]
    if source_type == "real_llm_full_chain":
        actions = []
        if not stage_gate:
            actions.append("Do not tune final memo from this run; inspect the first failed stage and reuse upstream passed artifacts.")
        if any(flag in flags for flag in ("low_rendered_claim_token_efficiency", "low_memo_chars_per_token", "memo_writer_retry_cost_present")):
            actions.append("Prioritize Memo Writer thesis-plan projection and first-pass schema reduction before raising max tokens.")
        if "source_gaps_without_second_pass" in flags:
            actions.append("Inspect Coverage / Reflection searchable gap classification before downstream prompt tuning.")
        if not actions:
            actions.append("Proceed to broader sector and multi-turn full-chain regression.")
        return actions
    return ["Use a supported summary artifact and rerun the audit."]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "0.000"


def _stdout_summary(audit: Mapping[str, Any], json_out: Path, md_out: Path) -> dict[str, Any]:
    return {
        "schema_version": audit.get("schema_version"),
        "run_id": audit.get("run_id"),
        "source_type": audit.get("source_type"),
        "gate_status": audit.get("gate_status"),
        "weighted_score": audit.get("weighted_score"),
        "quality_flags": audit.get("quality_flags") or [],
        "json_out": str(json_out),
        "md_out": str(md_out),
    }


if __name__ == "__main__":
    raise SystemExit(main())
