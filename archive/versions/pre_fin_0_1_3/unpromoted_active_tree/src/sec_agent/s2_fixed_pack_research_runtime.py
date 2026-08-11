from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from sec_agent.s1_six_case_local_evidence_pack import canonical_digest
from sec_agent.s2_fixed_pack_research import (
    CASES,
    validate_case_model_input,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_case_admission_v1_0"
CAPTURE_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_raw_capture_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_terminal_v1_0"
SCOPE = "FIN_0_1_3_S2_FIXED_PACK_RESEARCH_ONE_CASE_EXACT_ONCE"
SPECIALIST_FAMILIES = (
    "demand_authenticity_and_sustainability",
    "product_and_technology_position",
    "supply_capacity_and_competition",
    "financial_transmission_profit_and_cash",
    "capital_allocation_valuation_and_price_in",
    "counter_thesis_risk_and_what_would_change",
)
NODE_ORDER = (
    "direct_baseline",
    "research_lead",
    *tuple(f"specialist::{family}" for family in SPECIALIST_FAMILIES),
    "cross_unit_synthesis",
    "draft_writer",
    "red_team_critic",
    "final_writer",
    "verifier",
)

ProviderCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]
_DIGEST = re.compile(r"[0-9a-f]{64}")
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
_NUMERIC = re.compile(r"(?<![A-Za-z0-9])\(?[-+]?\d[\d,]*(?:\.\d+)?%?\)?")
COMPACT_VERIFIER_INPUT_SCHEMA = (
    "fin_ia_0_1_3_s2_compact_verifier_input_projection_v1_0"
)
COMPACT_VERIFIER_OUTPUT_SCHEMA = (
    "fin_ia_0_1_3_s2_compact_verifier_output_v1_0"
)
_VERIFIER_STATUSES = {"supported", "bounded", "unsupported", "contradicted"}
_VERIFIER_VERDICTS = {"pass", "pass_with_findings", "fail"}
_VERIFIER_FINDING_CODES = {
    "evidence_mismatch",
    "boundary_overreach",
    "identity_mismatch",
    "period_mismatch",
    "unit_mismatch",
    "numeric_mismatch",
    "causal_overreach",
    "gap_not_preserved",
    "contradicted_by_evidence",
}
_MAX_VERIFIER_REASON_CHARACTERS = 120


class S2FixedPackRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S2FixedPackRuntimeError(code)


def _utc(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError as exc:
        raise S2FixedPackRuntimeError("fixed_pack_runtime_timestamp_invalid") from exc


def _digest(value: str, code: str) -> str:
    candidate = str(value or "").lower()
    _require(bool(_DIGEST.fullmatch(candidate)), code)
    return candidate


def issue_case_admission(
    *,
    case_input: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    contract_sha256: str,
    profile_sha256: str,
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    credential_present: bool,
    execution_mode: str = "live",
) -> dict[str, Any]:
    validate_case_model_input(case_input, profile=profile)
    _require(
        bool(_GIT_COMMIT.fullmatch(str(execution_git_commit or ""))),
        "fixed_pack_admission_git_commit_invalid",
    )
    for value in (runner_sha256, contract_sha256, profile_sha256):
        _digest(value, "fixed_pack_admission_runtime_digest_invalid")
    _require(
        execution_mode in {"live", "fixture"},
        "fixed_pack_admission_execution_mode_invalid",
    )
    if execution_mode == "live":
        _require(credential_present is True, "fixed_pack_admission_credential_missing")
    else:
        _require(
            credential_present is False,
            "fixed_pack_fixture_admission_must_not_claim_credential",
        )
    _require(
        _utc(expires_at) > _utc(issued_at),
        "fixed_pack_admission_expiry_invalid",
    )
    case_key = str(case_input.get("case_key") or "")
    _require(case_key in CASES, "fixed_pack_admission_case_invalid")
    run_id = "fin013_s2_fixed_pack_" + case_key.lower() + "_" + canonical_digest(
        {
            "case_key": case_key,
            "git": execution_git_commit,
            "nonce": run_nonce,
            "input": case_input["model_visible_digest"],
        }
    )[:20]
    capacity = deepcopy(dict(profile.get("capacity") or {}))
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "scope": SCOPE,
        "admission_id": "admission::" + run_id,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "case_key": case_key,
        "case_input_digest": str(case_input["model_visible_digest"]),
        "source_pack_digest": str(case_input["source_pack_digest"]),
        "execution_git_commit": execution_git_commit,
        "runner_sha256": runner_sha256,
        "contract_sha256": contract_sha256,
        "profile_sha256": profile_sha256,
        "provider": {
            "name": str(profile.get("provider") or ""),
            "model": str(profile.get("model") or ""),
            "model_tier": str(profile.get("model_tier") or ""),
            "base_url": str(profile.get("base_url") or ""),
            "chat_completions_path": str(
                profile.get("chat_completions_path") or ""
            ),
        },
        "capacity": capacity,
        "node_order": list(NODE_ORDER),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": canonical_digest(run_nonce),
        "credential_present": credential_present,
        "execution_mode": execution_mode,
        "state": "issued_unconsumed",
        "promotion_authority": False,
    }
    return {**body, "admission_digest": canonical_digest(body)}


def validate_case_admission(
    admission: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    contract_sha256: str,
    profile_sha256: str,
    observed_at: str,
) -> None:
    body = deepcopy(dict(admission))
    digest = str(body.pop("admission_digest", ""))
    expected_runtime = (
        execution_git_commit,
        runner_sha256,
        contract_sha256,
        profile_sha256,
    )
    actual_runtime = tuple(
        admission.get(key)
        for key in (
            "execution_git_commit",
            "runner_sha256",
            "contract_sha256",
            "profile_sha256",
        )
    )
    _require(
        admission.get("schema_version") == ADMISSION_SCHEMA
        and admission.get("scope") == SCOPE
        and admission.get("state") == "issued_unconsumed"
        and admission.get("promotion_authority") is False
        and digest == canonical_digest(body),
        "fixed_pack_admission_digest_or_state_invalid",
    )
    _require(
        admission.get("case_key") == case_input.get("case_key")
        and admission.get("case_input_digest")
        == case_input.get("model_visible_digest")
        and admission.get("source_pack_digest") == case_input.get("source_pack_digest")
        and actual_runtime == expected_runtime
        and admission.get("node_order") == list(NODE_ORDER),
        "fixed_pack_admission_execution_binding_invalid",
    )
    _require(
        admission.get("provider", {}).get("name") == profile.get("provider")
        and admission.get("provider", {}).get("model") == profile.get("model")
        and admission.get("capacity") == profile.get("capacity"),
        "fixed_pack_admission_provider_or_capacity_invalid",
    )
    mode = str(admission.get("execution_mode") or "")
    _require(
        mode in {"live", "fixture"},
        "fixed_pack_admission_execution_mode_invalid",
    )
    if mode == "live":
        _require(
            admission.get("credential_present") is True,
            "fixed_pack_admission_credential_missing",
        )
    else:
        _require(
            admission.get("credential_present") is False,
            "fixed_pack_fixture_admission_must_not_claim_credential",
        )
    _require(
        _utc(observed_at) <= _utc(str(admission.get("expires_at") or "")),
        "fixed_pack_admission_expired",
    )


def _compact_case_input(case_input: Mapping[str, Any]) -> dict[str, Any]:
    value = {
        "case_key": case_input["case_key"],
        "issuer": deepcopy(case_input["issuer"]),
        "research_as_of": case_input["research_as_of"],
        "research_objective_zh": case_input["research_objective_zh"],
        "research_questions_zh": deepcopy(case_input["research_questions_zh"]),
        "report_section_order": deepcopy(case_input["report_section_order"]),
        "input_density": deepcopy(case_input["input_density"]),
        "evidence_items": deepcopy(case_input["evidence_items"]),
        "residual_gaps": deepcopy(case_input["residual_gaps"]),
        "model_rules": deepcopy(case_input["model_rules"]),
        "model_visible_digest": case_input["model_visible_digest"],
    }
    for key in (
        "base_model_visible_digest",
        "successor_contract_ref",
        "numeric_authority",
        "successor_boundary",
    ):
        if key in case_input:
            value[key] = deepcopy(case_input[key])
    return value


def _common_system(case_input: Mapping[str, Any]) -> str:
    numeric_rule = ""
    if case_input.get("numeric_authority"):
        numeric_rule = (
            "任何 material number 都必须在同一判断的 numeric_refs 中引用当前 Numeric authority："
            "原始披露数字及其本地可复算展示引用 NUM ref，派生比例引用 FORM ref；"
            "无需为同一 NUM 冗余选择 PRES ref，Harness 会从 NUM 确定性解析获准展示面。"
            "前序节点是只读历史上下文，其数字不得原样复制而不重新绑定当前 ref。"
        )
    return (
        "你是受证据边界约束的机构级金融研究员。只能使用用户消息中的冻结 Evidence Pack，"
        "不得调用工具、联网或补入外部知识。精确数字可以读取、分析和引用，但必须绑定同一条"
        "Evidence alias；不得改变主体、期间、币种、单位或关系方向。明确区分事实、有限推断、"
        "假设与证据缺口。输出有效 JSON 对象，不要 Markdown 代码围栏。"
        + numeric_rule
        + "研究主体为 "
        + str(case_input["case_key"])
        + "。"
    )


def _report_schema_instruction() -> str:
    return (
        "返回 {\"sections\":[{\"section_id\":字符串,\"points\":[{\"text\":中文分析,"
        "\"epistemic_status\":\"fact|bounded_inference|hypothesis|gap\","
        "\"evidence_aliases\":[\"E001\"],\"gap_aliases\":[\"G001\"],"
        "\"numeric_refs\":[\"NUM/PRES/FORM ref\"]}]}],"
        "\"overall_confidence\":\"high|medium|low\",\"limitations\":[字符串]}。"
        "每个实质判断都必须列 evidence_aliases；缺证据时写 gap，不得补造。"
    )


def _claim_rows(final_report: Any, *, case_key: str) -> list[dict[str, Any]]:
    if not isinstance(final_report, dict):
        return []
    rows: list[dict[str, Any]] = []
    for section_index, section in enumerate(final_report.get("sections") or (), start=1):
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or f"section_{section_index:02d}")
        for point_index, point in enumerate(section.get("points") or (), start=1):
            if not isinstance(point, dict) or not str(point.get("text") or "").strip():
                continue
            rows.append(
                {
                    "claim_id": f"CLM:{case_key}:{len(rows) + 1:03d}",
                    "section_id": section_id,
                    "point_index": point_index,
                    "text": str(point.get("text") or ""),
                    "epistemic_status": str(point.get("epistemic_status") or ""),
                    "evidence_aliases": [
                        str(value) for value in point.get("evidence_aliases") or ()
                    ],
                    "gap_aliases": [
                        str(value) for value in point.get("gap_aliases") or ()
                    ],
                    "numeric_refs": [
                        str(value) for value in point.get("numeric_refs") or ()
                    ],
                }
            )
    return rows


def _bounded_verifier_source_view(
    material: Mapping[str, Any],
    *,
    bound_evidence: list[dict[str, Any]],
    bound_numeric_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    source_text = str(material.get("source_text") or "")
    anchors: list[str] = []
    anchors.extend(
        str(row.get("source_token") or "")
        for row in bound_numeric_facts
        if str(row.get("source_token") or "")
    )
    anchors.extend(
        str(row.get("claim_text") or "")
        for row in bound_evidence
        if str(row.get("claim_text") or "")
    )
    spans: list[tuple[int, int]] = []
    for anchor in anchors:
        position = source_text.find(anchor)
        if position < 0 and len(anchor) > 96:
            position = source_text.find(anchor[:96])
        if position >= 0:
            spans.append(
                (
                    max(0, position - 220),
                    min(len(source_text), position + min(len(anchor), 900) + 220),
                )
            )
    if not spans:
        spans = [(0, min(len(source_text), 900))]
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1] + 80:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    excerpt = "\n[…captured source window…]\n".join(
        source_text[start:end] for start, end in merged
    )
    maximum = 2400
    if len(excerpt) > maximum:
        excerpt = excerpt[:maximum]
    return {
        "source_material_alias": str(material.get("source_material_alias") or ""),
        "source_record_id": str(material.get("source_record_id") or ""),
        "source_text_digest": str(material.get("source_text_digest") or ""),
        "source_url": str(material.get("source_url") or ""),
        "source_type": str(material.get("source_type") or ""),
        "source_tier": str(material.get("source_tier") or ""),
        "evidence_owner_ticker": str(material.get("evidence_owner_ticker") or ""),
        "publication_date": str(material.get("publication_date") or ""),
        "period_end": str(material.get("period_end") or ""),
        "captured_source_excerpt": excerpt,
        "source_text_characters": len(source_text),
        "excerpt_characters": len(excerpt),
        "excerpt_complete": len(excerpt) == len(source_text),
        "excerpt_strategy": "claim_and_numeric_anchor_windows_fail_closed_to_chunk_head",
    }


def build_compact_verifier_projection(
    *,
    case_input: Mapping[str, Any],
    final_report: Any,
) -> dict[str, Any]:
    """Select only the claims and frozen authority required by the Verifier."""

    case_key = str(case_input.get("case_key") or "")
    claims = _claim_rows(final_report, case_key=case_key)
    evidence_index = {
        str(row.get("evidence_alias") or ""): deepcopy(dict(row))
        for row in case_input.get("evidence_items") or ()
    }
    material_index = {
        str(row.get("source_material_alias") or ""): deepcopy(dict(row))
        for row in case_input.get("source_materials") or ()
    }
    gap_index = {
        str(row.get("gap_alias") or ""): deepcopy(dict(row))
        for row in case_input.get("residual_gaps") or ()
    }
    numeric_reference_index = _numeric_reference_index(case_input)
    referenced_evidence_set = {
        alias for row in claims for alias in row["evidence_aliases"]
    }
    referenced_gaps = sorted({alias for row in claims for alias in row["gap_aliases"]})
    referenced_numeric = sorted(
        {ref for row in claims for ref in row["numeric_refs"]}
    )
    for ref in referenced_numeric:
        referenced_evidence_set.update(
            str(alias)
            for alias in (numeric_reference_index.get(ref) or {}).get(
                "evidence_aliases"
            )
            or ()
        )
    referenced_evidence = sorted(referenced_evidence_set)
    selected_evidence = [
        evidence_index[alias]
        for alias in referenced_evidence
        if alias in evidence_index
    ]
    selected_material_aliases = sorted(
        {
            str(row.get("source_material_alias") or "")
            for row in selected_evidence
            if str(row.get("source_material_alias") or "")
        }
    )
    numeric = deepcopy(dict(case_input.get("numeric_authority") or {}))
    selected_fact_refs = set(referenced_numeric)
    formula_rows: list[dict[str, Any]] = []
    for formula in numeric.get("formula_traces") or ():
        row = deepcopy(dict(formula))
        if str(row.get("formula_ref") or "") in referenced_numeric:
            formula_rows.append(row)
            selected_fact_refs.update(
                str(value) for value in row.get("input_numeric_refs") or ()
            )
    fact_rows = [
        deepcopy(dict(row))
        for row in numeric.get("source_numeric_facts") or ()
        if str(row.get("numeric_ref") or "") in selected_fact_refs
        or any(
            str(surface.get("presentation_ref") or "") in referenced_numeric
            for surface in row.get("display_surfaces") or ()
        )
    ]
    body = {
        "schema_version": COMPACT_VERIFIER_INPUT_SCHEMA,
        "case_identity": {
            "case_key": case_key,
            "issuer": deepcopy(dict(case_input.get("issuer") or {})),
            "research_as_of": str(case_input.get("research_as_of") or ""),
        },
        "claims": claims,
        "expected_claim_ids": [row["claim_id"] for row in claims],
        "selected_evidence": selected_evidence,
        "selected_source_materials": [
            _bounded_verifier_source_view(
                material_index[alias],
                bound_evidence=[
                    row
                    for row in selected_evidence
                    if str(row.get("source_material_alias") or "") == alias
                ],
                bound_numeric_facts=[
                    row
                    for row in fact_rows
                    if str(row.get("source_material_alias") or "") == alias
                ],
            )
            for alias in selected_material_aliases
            if alias in material_index
        ],
        "selected_gaps": [
            gap_index[alias] for alias in referenced_gaps if alias in gap_index
        ],
        "selected_numeric_authority": {
            "source_numeric_facts": fact_rows,
            "formula_traces": formula_rows,
        },
        "selection_diagnostics": {
            "unknown_evidence_aliases": sorted(
                set(referenced_evidence) - set(evidence_index)
            ),
            "unknown_gap_aliases": sorted(set(referenced_gaps) - set(gap_index)),
            "unknown_numeric_refs": sorted(
                set(referenced_numeric) - set(numeric_reference_index)
            ),
        },
        "output_contract": {
            "schema_version": COMPACT_VERIFIER_OUTPUT_SCHEMA,
            "claim_id_exact_coverage_required": True,
            "claim_text_echo_forbidden": True,
            "allowed_statuses": sorted(_VERIFIER_STATUSES),
            "allowed_finding_codes": sorted(_VERIFIER_FINDING_CODES),
            "maximum_reason_characters": _MAX_VERIFIER_REASON_CHARACTERS,
            "allowed_verdicts": sorted(_VERIFIER_VERDICTS),
        },
    }
    return {**body, "projection_digest": canonical_digest(body)}


def validate_compact_verifier_output(
    *,
    verifier_output: Any,
    projection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return hard-incomplete findings; an empty list means shape-complete only."""

    findings: list[dict[str, Any]] = []
    if not isinstance(verifier_output, dict):
        return [
            {
                "level": "L1",
                "code": "verification_incomplete_output_not_object",
                "disposition": "terminal_failure_no_promotion",
            }
        ]
    if verifier_output.get("schema_version") != COMPACT_VERIFIER_OUTPUT_SCHEMA:
        findings.append(
            {
                "level": "L1",
                "code": "verification_incomplete_schema_mismatch",
                "disposition": "terminal_failure_no_promotion",
            }
        )
    expected = [str(value) for value in projection.get("expected_claim_ids") or ()]
    checks = verifier_output.get("claim_checks")
    if not isinstance(checks, list):
        checks = []
        findings.append(
            {
                "level": "L1",
                "code": "verification_incomplete_claim_checks_missing",
                "disposition": "terminal_failure_no_promotion",
            }
        )
    observed_ids: list[str] = []
    for row in checks:
        if not isinstance(row, dict):
            findings.append(
                {
                    "level": "L1",
                    "code": "verification_incomplete_claim_check_invalid",
                    "disposition": "terminal_failure_no_promotion",
                }
            )
            continue
        claim_id = str(row.get("claim_id") or "")
        observed_ids.append(claim_id)
        status = str(row.get("status") or "")
        codes = row.get("finding_codes")
        reason = str(row.get("reason") or "")
        if status not in _VERIFIER_STATUSES:
            findings.append(
                {
                    "level": "L1",
                    "code": "verification_incomplete_status_invalid",
                    "claim_id": claim_id,
                    "disposition": "terminal_failure_no_promotion",
                }
            )
        if not isinstance(codes, list) or any(
            str(code) not in _VERIFIER_FINDING_CODES for code in codes
        ):
            findings.append(
                {
                    "level": "L1",
                    "code": "verification_incomplete_finding_code_invalid",
                    "claim_id": claim_id,
                    "disposition": "terminal_failure_no_promotion",
                }
            )
        if not reason or len(reason) > _MAX_VERIFIER_REASON_CHARACTERS:
            findings.append(
                {
                    "level": "L1",
                    "code": "verification_incomplete_reason_length_invalid",
                    "claim_id": claim_id,
                    "disposition": "terminal_failure_no_promotion",
                }
            )
    if (
        observed_ids != expected
        or len(observed_ids) != len(set(observed_ids))
        or set(observed_ids) != set(expected)
    ):
        findings.append(
            {
                "level": "L1",
                "code": "verification_incomplete_claim_coverage_invalid",
                "missing_claim_ids": sorted(set(expected) - set(observed_ids)),
                "unknown_claim_ids": sorted(set(observed_ids) - set(expected)),
                "disposition": "terminal_failure_no_promotion",
            }
        )
    global_codes = verifier_output.get("global_finding_codes")
    if not isinstance(global_codes, list) or any(
        str(code) not in _VERIFIER_FINDING_CODES for code in global_codes
    ):
        findings.append(
            {
                "level": "L1",
                "code": "verification_incomplete_global_finding_invalid",
                "disposition": "terminal_failure_no_promotion",
            }
        )
    if str(verifier_output.get("verdict") or "") not in _VERIFIER_VERDICTS:
        findings.append(
            {
                "level": "L1",
                "code": "verification_incomplete_verdict_invalid",
                "disposition": "terminal_failure_no_promotion",
            }
        )
    return findings


def build_node_request(
    *,
    node_key: str,
    case_input: Mapping[str, Any],
    prior_outputs: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    compact = _compact_case_input(case_input)
    if node_key == "direct_baseline":
        task = (
            "直接完成一份可供投研讨论的完整报告。这是与多节点链路的同输入基线。"
            + _report_schema_instruction()
        )
        context: Any = deepcopy(dict(case_input))
        node_type = node_key
    elif node_key == "research_lead":
        task = (
            "制定研究组织方案。六个 mandatory_research_families 都必须覆盖。返回 "
            "{\"thesis_hypotheses\":[字符串],\"research_units\":[{\"family\":字符串,"
            "\"question\":字符串,\"evidence_aliases\":[字符串],\"gap_aliases\":[字符串],"
            "\"counter_thesis\":字符串}]}。研究单元只作分析规划，不能改写证据。"
        )
        context = deepcopy(dict(case_input))
        node_type = node_key
    elif node_key.startswith("specialist::"):
        family = node_key.split("::", 1)[1]
        task = (
            f"你只负责研究家族 {family}。返回 "
            "{\"family\":字符串,\"findings\":[{\"text\":中文机制分析,"
            "\"epistemic_status\":\"fact|bounded_inference|hypothesis|gap\","
            "\"evidence_aliases\":[字符串],\"gap_aliases\":[字符串],"
            "\"numeric_refs\":[字符串],"
            "\"counterevidence\":字符串,\"confidence\":\"high|medium|low\"}],"
            "\"unresolved\":[字符串]}。不要写通用模板话。"
        )
        context = {
            "case_input": deepcopy(dict(case_input)),
            "lead_output": deepcopy(prior_outputs.get("research_lead")),
            "assigned_family": family,
        }
        node_type = "specialist"
    elif node_key == "cross_unit_synthesis":
        task = (
            "综合六个研究家族，解释需求、产品、供给、竞争、利润、现金、估值和反证之间"
            "的经济机制，不要简单拼接。返回 {\"cross_mechanism_findings\":[{\"text\":字符串,"
            "\"epistemic_status\":字符串,\"evidence_aliases\":[字符串],"
            "\"gap_aliases\":[字符串],\"numeric_refs\":[字符串]}],"
            "\"thesis\":字符串,\"antithesis\":字符串,"
            "\"unresolved_conflicts\":[字符串]}。"
        )
        context = {
            "case_input": compact,
            "specialist_outputs": [
                deepcopy(prior_outputs.get(key))
                for key in NODE_ORDER
                if key.startswith("specialist::")
            ],
        }
        node_type = node_key
    elif node_key == "draft_writer":
        task = "根据综合结果写成完整研究初稿。" + _report_schema_instruction()
        context = {
            "case_input": compact,
            "synthesis": deepcopy(prior_outputs.get("cross_unit_synthesis")),
            "specialist_outputs": [
                deepcopy(prior_outputs.get(key))
                for key in NODE_ORDER
                if key.startswith("specialist::")
            ],
        }
        node_type = node_key
    elif node_key == "red_team_critic":
        task = (
            "以反方和事实审计员身份批评初稿。返回 {\"issues\":[{\"severity\":"
            "\"L1|L2|L3|L4\",\"text\":字符串,\"affected_section\":字符串,"
            "\"evidence_aliases\":[字符串],\"numeric_refs\":[字符串]}],"
            "\"missing_counter_thesis\":[字符串],"
            "\"rewrite_instructions\":[字符串]}。不得声称自己拥有最终验证权。"
        )
        context = {
            "case_input": compact,
            "draft": deepcopy(prior_outputs.get("draft_writer")),
        }
        node_type = node_key
    elif node_key == "final_writer":
        task = (
            "根据初稿和红队意见完成最终报告；保留证据不足，不得为了流畅而删掉关键缺口。"
            + _report_schema_instruction()
        )
        context = {
            "case_input": compact,
            "draft": deepcopy(prior_outputs.get("draft_writer")),
            "critic": deepcopy(prior_outputs.get("red_team_critic")),
        }
        node_type = node_key
    elif node_key == "verifier":
        task = (
            "只审查 compact projection 中每个 claim 与所选冻结原文、Evidence、Gap 和 Numeric authority 是否一致。"
            "不得重抄 claim text，不得新增 claim，不得省略或改变 claim 顺序。返回 "
            f"{{\"schema_version\":\"{COMPACT_VERIFIER_OUTPUT_SCHEMA}\","
            "\"claim_checks\":[{\"claim_id\":\"CLM:CASE:001\","
            "\"status\":\"supported|bounded|unsupported|contradicted\","
            "\"finding_codes\":[\"允许枚举值\"],\"reason\":\"不超过120字符的短原因\"}],"
            "\"global_finding_codes\":[\"允许枚举值\"],"
            "\"verdict\":\"pass|pass_with_findings|fail\"}}。"
            "finding_codes 只能使用 projection.output_contract.allowed_finding_codes；"
            "没有 finding 时返回空数组。这是审查建议，不是晋升权威。"
        )
        context = build_compact_verifier_projection(
            case_input=case_input,
            final_report=prior_outputs.get("final_writer"),
        )
        node_type = node_key
    else:
        raise S2FixedPackRuntimeError("fixed_pack_runtime_node_unknown")

    messages = [
        {"role": "system", "content": _common_system(case_input)},
        {
            "role": "user",
            "content": task
            + "\n冻结上下文 JSON：\n"
            + json.dumps(context, ensure_ascii=False, separators=(",", ":")),
        },
    ]
    request = {
        "node_key": node_key,
        "node_type": node_type,
        "case_key": case_input["case_key"],
        "case_input_digest": case_input["model_visible_digest"],
        "model": profile["model"],
        "messages": messages,
        "temperature": profile["temperature"],
        "stream": profile["stream"],
        "enable_thinking": profile["enable_thinking"],
        "max_tokens": profile["maximum_output_tokens"][node_type],
        "response_format": {"type": "json_object"},
    }
    size = len(json.dumps(request, ensure_ascii=False, separators=(",", ":")))
    _require(
        size <= int(profile["maximum_input_characters_per_call"]),
        f"fixed_pack_runtime_node_capacity_exceeded:{node_key}",
    )
    return request


def _parse_json_object(content: str) -> tuple[dict[str, Any] | None, str | None]:
    candidate = str(content or "").strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            return None, "model_output_json_object_missing"
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None, "model_output_json_parse_failed"
    if not isinstance(value, dict):
        return None, "model_output_json_not_object"
    return value, None


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def perform_node_call(
    *,
    call_index: int,
    node_key: str,
    request: Mapping[str, Any],
    provider_call: ProviderCall,
    captures_root: Path,
    observed_at: str,
    logical_node_index: int | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any] | str,
    list[dict[str, Any]],
    str | None,
]:
    call_id = f"call_{call_index:02d}_{node_key.replace('::', '__')}"
    call_root = captures_root / call_id
    _atomic_json(
        call_root / "request.json",
        {
            "call_id": call_id,
            "observed_at": observed_at,
            "request": deepcopy(dict(request)),
            "request_digest": canonical_digest(request),
        },
    )
    try:
        response = dict(provider_call(request))
    except Exception as exc:  # terminalized below; no provider retry is allowed.
        response = {
            "status": "provider_error",
            "failure_reason": f"{type(exc).__name__}: {str(exc)[:1000]}",
            "content": "",
        }
    capture_body = {
        "schema_version": CAPTURE_SCHEMA,
        "call_id": call_id,
        "call_index": call_index,
        "node_key": node_key,
        "request_digest": canonical_digest(request),
        "request": deepcopy(dict(request)),
        "provider_response": deepcopy(response),
        "observed_at": observed_at,
    }
    if logical_node_index is not None:
        capture_body["logical_node_index"] = logical_node_index
    capture = {**capture_body, "capture_digest": canonical_digest(capture_body)}
    _atomic_json(call_root / "capture.json", capture)
    status = str(response.get("status") or "")
    content = str(response.get("content") or "")
    findings: list[dict[str, Any]] = []
    fatal_code: str | None = None
    parsed: dict[str, Any] | None = None
    if status != "ok":
        fatal_code = f"fixed_pack_runtime_provider_failure:{node_key}:{status}"
    elif not content.strip():
        fatal_code = f"fixed_pack_runtime_empty_output:{node_key}"
    elif node_key == "verifier" and str(response.get("finish_reason") or "").lower() == "length":
        fatal_code = "verification_incomplete_finish_reason_length"
        findings.append(
            {
                "level": "L1",
                "code": fatal_code,
                "node_key": node_key,
                "disposition": "raw_capture_preserved_terminal_failure_no_promotion",
            }
        )
    else:
        parsed, parse_finding = _parse_json_object(content)
        if parse_finding:
            is_verifier = node_key == "verifier"
            finding_code = (
                "verification_incomplete_invalid_json"
                if is_verifier
                else parse_finding
            )
            findings.append(
                {
                    "level": "L1" if is_verifier else "L2",
                    "code": finding_code,
                    "node_key": node_key,
                    "disposition": (
                        "raw_capture_preserved_terminal_failure_no_promotion"
                        if is_verifier
                        else "raw_text_preserved_chain_continues_no_promotion"
                    ),
                }
            )
            if is_verifier:
                fatal_code = finding_code
    output: dict[str, Any] | str = parsed if parsed is not None else content
    receipt = {
        "call_id": call_id,
        "node_key": node_key,
        "capture_ref": (
            Path("raw_model_only") / "calls" / call_id / "capture.json"
        ).as_posix(),
        "capture_digest": capture["capture_digest"],
        "request_digest": capture["request_digest"],
        "status": status,
        "finish_reason": response.get("finish_reason"),
        "input_tokens": int(response.get("input_tokens") or 0),
        "output_tokens": int(response.get("output_tokens") or 0),
        "total_tokens": int(response.get("total_tokens") or 0),
    }
    if logical_node_index is not None:
        receipt["logical_node_index"] = logical_node_index
    return receipt, output, findings, fatal_code


def _collect_point_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            rows.append(dict(value))
        for child in value.values():
            rows.extend(_collect_point_rows(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_collect_point_rows(child))
    return rows


def _normalize_numeric(token: str) -> str:
    return token.strip().strip("()").replace(",", "").lstrip("+")


def _numeric_reference_index(case_input: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    numeric = dict(case_input.get("numeric_authority") or {})
    index: dict[str, dict[str, Any]] = {}
    for fact in numeric.get("source_numeric_facts") or ():
        row = dict(fact)
        source_tokens = [
            _normalize_numeric(value)
            for value in _NUMERIC.findall(str(row.get("source_token") or ""))
        ]
        linked_surface_tokens = [
            _normalize_numeric(str(surface.get("numeric_token") or ""))
            for surface in row.get("display_surfaces") or ()
            if str(surface.get("numeric_token") or "")
        ]
        index[str(row.get("numeric_ref") or "")] = {
            "ref_type": "source_numeric_fact",
            "canonical_ref": str(row.get("numeric_ref") or ""),
            "numeric_tokens": sorted(set(source_tokens + linked_surface_tokens)),
            "evidence_aliases": list(row.get("evidence_aliases") or ()),
        }
        for surface in row.get("display_surfaces") or ():
            surface_row = dict(surface)
            index[str(surface_row.get("presentation_ref") or "")] = {
                "ref_type": "presentation_alias",
                "canonical_ref": str(row.get("numeric_ref") or ""),
                "numeric_tokens": [
                    _normalize_numeric(str(surface_row.get("numeric_token") or ""))
                ],
                "evidence_aliases": list(row.get("evidence_aliases") or ()),
            }
    for formula in numeric.get("formula_traces") or ():
        row = dict(formula)
        index[str(row.get("formula_ref") or "")] = {
            "ref_type": "deterministic_formula",
            "canonical_ref": str(row.get("formula_ref") or ""),
            "numeric_tokens": [
                _normalize_numeric(str(surface.get("numeric_token") or ""))
                for surface in row.get("display_surfaces") or ()
            ],
            "evidence_aliases": list(row.get("evidence_aliases") or ()),
        }
    return {key: value for key, value in index.items() if key}


def resolve_final_output_numeric_surfaces(
    *,
    final_output: Any,
    case_input: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Materialize deterministic token-to-authority receipts for report points."""

    if not isinstance(final_output, dict):
        return []
    index = _numeric_reference_index(case_input)
    receipts: list[dict[str, Any]] = []
    for claim in _claim_rows(
        final_output, case_key=str(case_input.get("case_key") or "")
    ):
        refs = [str(value) for value in claim.get("numeric_refs") or ()]
        for token in sorted(set(_material_numeric_tokens(str(claim.get("text") or "")))):
            explicit_refs = sorted(
                ref
                for ref in refs
                if token in set((index.get(ref) or {}).get("numeric_tokens") or ())
            )
            matched_refs = explicit_refs
            binding_mode = "explicit_numeric_ref"
            if not matched_refs:
                claim_evidence = set(claim.get("evidence_aliases") or ())
                canonical_candidates = sorted(
                    {
                        str(authority.get("canonical_ref") or ref)
                        for ref, authority in index.items()
                        if authority.get("ref_type")
                        in {"source_numeric_fact", "presentation_alias"}
                        and token in set(authority.get("numeric_tokens") or ())
                        and claim_evidence
                        & set(authority.get("evidence_aliases") or ())
                    }
                )
                if len(canonical_candidates) == 1:
                    matched_refs = canonical_candidates
                    binding_mode = "deterministic_unique_source_surface"
                elif canonical_candidates:
                    binding_mode = "ambiguous_source_surface"
                else:
                    binding_mode = "unbound"
            receipts.append(
                {
                    "claim_id": claim["claim_id"],
                    "numeric_token": token,
                    "matched_numeric_refs": matched_refs,
                    "authority_evidence_aliases": sorted(
                        {
                            str(alias)
                            for ref in matched_refs
                            for alias in (index.get(ref) or {}).get(
                                "evidence_aliases"
                            )
                            or ()
                        }
                    ),
                    "binding_mode": binding_mode,
                    "status": (
                        "deterministically_bound"
                        if matched_refs
                        else "unbound_material_numeric_surface"
                    ),
                }
            )
    return receipts


def _material_numeric_tokens(text: str) -> list[str]:
    values: list[str] = []
    currency_markers = ("$", "USD", "美元", "亿元", "亿", "million", "billion", "倍", "基点")
    for match in _NUMERIC.finditer(text):
        raw = match.group(0)
        normalized = _normalize_numeric(raw)
        plain = normalized.rstrip("%")
        try:
            number = float(plain)
        except ValueError:
            continue
        if plain.isdigit() and len(plain) == 4 and 1900 <= int(plain) <= 2100:
            continue
        context = text[max(0, match.start() - 12) : match.end() + 12]
        material = (
            "%" in raw
            or "," in raw
            or "." in raw
            or abs(number) >= 100
            or any(marker in context for marker in currency_markers)
        )
        if material:
            values.append(normalized)
    return values


def evaluate_final_output(
    *,
    final_output: Any,
    case_input: Mapping[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    evidence = {
        str(row["evidence_alias"]): dict(row)
        for row in case_input.get("evidence_items") or ()
    }
    materials = {
        str(row["source_material_alias"]): dict(row)
        for row in case_input.get("source_materials") or ()
    }
    if not isinstance(final_output, dict):
        return [
            {
                "level": "L2",
                "code": "final_report_not_structured_json",
                "disposition": "raw_candidate_retained_not_promoted",
            }
        ]
    sections = final_output.get("sections")
    if not isinstance(sections, list) or not sections:
        findings.append(
            {
                "level": "L2",
                "code": "final_report_sections_missing",
                "disposition": "raw_candidate_retained_not_promoted",
            }
        )
    known_aliases = set(evidence)
    known_gaps = {str(row["gap_alias"]) for row in case_input.get("residual_gaps") or ()}
    numeric_index = _numeric_reference_index(case_input)
    numeric_receipts = resolve_final_output_numeric_surfaces(
        final_output=final_output,
        case_input=case_input,
    )
    receipt_index: dict[str, dict[str, dict[str, Any]]] = {}
    for receipt in numeric_receipts:
        receipt_index.setdefault(str(receipt["claim_id"]), {})[
            str(receipt["numeric_token"])
        ] = receipt
    cited_gaps: set[str] = set()
    for point in _claim_rows(
        final_output,
        case_key=str(case_input.get("case_key") or ""),
    ):
        text = str(point.get("text") or "")
        aliases = [str(value) for value in point.get("evidence_aliases") or ()]
        gap_aliases = [str(value) for value in point.get("gap_aliases") or ()]
        numeric_refs = [str(value) for value in point.get("numeric_refs") or ()]
        cited_gaps.update(gap_aliases)
        unknown = (
            (set(aliases) - known_aliases)
            | (set(gap_aliases) - known_gaps)
            | (set(numeric_refs) - set(numeric_index))
        )
        if unknown:
            findings.append(
                {
                    "level": "L2",
                    "code": "final_report_unknown_alias",
                    "aliases": sorted(unknown),
                    "text": text[:240],
                }
            )
        if text and point.get("epistemic_status") != "gap" and not aliases:
            findings.append(
                {
                    "level": "L2",
                    "code": "final_report_substantive_point_uncited",
                    "text": text[:240],
                }
            )
        if numeric_index:
            authorized_numeric: set[str] = set()
            for ref in numeric_refs:
                authority = numeric_index.get(ref) or {}
                authorized_numeric.update(
                    str(value)
                    for value in authority.get("numeric_tokens") or ()
                    if str(value)
                )
            material_tokens = set(_material_numeric_tokens(text))
            unsupported = sorted(
                token
                for token in material_tokens - authorized_numeric
                if not (
                    receipt_index.get(str(point.get("claim_id") or ""), {})
                    .get(token, {})
                    .get("status")
                    == "deterministically_bound"
                )
            )
            if unsupported:
                findings.append(
                    {
                        "level": "L1",
                        "code": (
                            "final_report_material_numeric_ref_missing"
                            if not numeric_refs
                            else "final_report_numeric_surface_not_authorized_by_refs"
                        ),
                        "numeric_tokens": unsupported,
                        "text": text[:240],
                    }
                )
        else:
            allowed_surface = ""
            for alias in aliases:
                item = evidence.get(alias) or {}
                allowed_surface += json.dumps(item, ensure_ascii=False)
                material_alias = str(item.get("source_material_alias") or "")
                if material_alias in materials:
                    allowed_surface += str(
                        materials[material_alias].get("source_text") or ""
                    )
            allowed_numeric = {
                _normalize_numeric(token) for token in _NUMERIC.findall(allowed_surface)
            }
            unsupported = sorted(
                {
                    token
                    for token in (
                        _normalize_numeric(raw) for raw in _NUMERIC.findall(text)
                    )
                    if token and token not in allowed_numeric
                }
            )
            if unsupported:
                findings.append(
                    {
                        "level": "L1",
                        "code": "final_report_numeric_surface_not_in_cited_evidence",
                        "numeric_tokens": unsupported,
                        "text": text[:240],
                    }
                )
    if known_gaps and not cited_gaps:
        findings.append(
            {
                "level": "L2",
                "code": "final_report_residual_gaps_not_cited",
                "disposition": "content_quality_finding",
            }
        )
    return findings


def execute_case(
    *,
    admission: Mapping[str, Any],
    case_input: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    contract_sha256: str,
    profile_sha256: str,
    runtime_root: str | Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    validate_case_admission(
        admission,
        case_input=case_input,
        profile=profile,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        contract_sha256=contract_sha256,
        profile_sha256=profile_sha256,
        observed_at=observed_at,
    )
    root = Path(runtime_root).resolve()
    _require(not root.exists(), "fixed_pack_runtime_root_already_exists")
    ledger_path = shared_ledger.path.resolve()
    _require(
        ledger_path != root and root not in ledger_path.parents,
        "fixed_pack_runtime_ledger_inside_attempt_root",
    )
    root.mkdir(parents=True)
    captures_root = root / "raw_model_only" / "calls"
    shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )
    calls: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {}
    terminal_status = "completed"
    terminal_phase = "verifier"
    terminal_code = "fixed_pack_chain_completed"
    active_node = "initialization"
    try:
        for call_index, node_key in enumerate(NODE_ORDER, start=1):
            active_node = node_key
            maximum_calls = int(
                profile["capacity"]["provider_calls_per_case"]["maximum"]
            )
            if call_index > maximum_calls:
                raise S2FixedPackRuntimeError(
                    "fixed_pack_runtime_provider_call_ceiling_exceeded"
                )
            request = build_node_request(
                node_key=node_key,
                case_input=case_input,
                prior_outputs=outputs,
                profile=profile,
            )
            receipt, output, node_findings, fatal_code = perform_node_call(
                call_index=call_index,
                node_key=node_key,
                request=request,
                provider_call=provider_call,
                captures_root=captures_root,
                observed_at=observed_at,
            )
            calls.append(receipt)
            outputs[node_key] = output
            findings.extend(node_findings)
            if fatal_code:
                raise S2FixedPackRuntimeError(fatal_code)
            if node_key == "verifier":
                projection = build_compact_verifier_projection(
                    case_input=case_input,
                    final_report=outputs.get("final_writer"),
                )
                verifier_findings = validate_compact_verifier_output(
                    verifier_output=output,
                    projection=projection,
                )
                findings.extend(verifier_findings)
                if verifier_findings:
                    raise S2FixedPackRuntimeError(
                        "verification_incomplete_contract_invalid"
                    )
            input_tokens = sum(int(row.get("input_tokens") or 0) for row in calls)
            output_tokens = sum(int(row.get("output_tokens") or 0) for row in calls)
            total_tokens = sum(int(row.get("total_tokens") or 0) for row in calls)
            estimated_usd = (
                input_tokens
                * float(profile["capacity"]["input_usd_per_million_tokens"])
                + output_tokens
                * float(profile["capacity"]["output_usd_per_million_tokens"])
            ) / 1_000_000
            if (
                input_tokens
                > int(profile["capacity"]["maximum_input_tokens_per_case"])
                or output_tokens
                > int(profile["capacity"]["maximum_output_tokens_per_case"])
                or total_tokens
                > int(profile["capacity"]["maximum_total_tokens_per_case"])
                or estimated_usd
                > float(profile["capacity"]["maximum_estimated_usd_per_case"])
            ):
                raise S2FixedPackRuntimeError(
                    "fixed_pack_runtime_cumulative_budget_exceeded_after_capture"
                )
        findings.extend(
            evaluate_final_output(
                final_output=outputs.get("final_writer"),
                case_input=case_input,
            )
        )
        if findings:
            terminal_status = "completed_with_findings"
            terminal_code = "fixed_pack_chain_completed_raw_candidate_not_promoted"
    except S2FixedPackRuntimeError as exc:
        terminal_status = "failed"
        terminal_phase = active_node
        terminal_code = exc.code
        findings.append(
            {
                "level": "L1",
                "code": exc.code,
                "disposition": "terminal_failure_no_retry_no_promotion",
            }
        )

    numeric_surface_receipts = resolve_final_output_numeric_surfaces(
        final_output=outputs.get("final_writer"),
        case_input=case_input,
    )
    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "scope": SCOPE,
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "case_key": case_input["case_key"],
        "case_input_digest": case_input["model_visible_digest"],
        "source_pack_digest": case_input["source_pack_digest"],
        "status": terminal_status,
        "terminal_phase": terminal_phase,
        "terminal_code": terminal_code,
        "call_receipts": calls,
        "observed_counts": {
            "provider_calls": len(calls),
            "model_calls": len(calls),
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "findings": len(findings),
            "input_tokens": sum(int(row.get("input_tokens") or 0) for row in calls),
            "output_tokens": sum(int(row.get("output_tokens") or 0) for row in calls),
            "total_tokens": sum(int(row.get("total_tokens") or 0) for row in calls),
            "estimated_usd": round(
                (
                    sum(int(row.get("input_tokens") or 0) for row in calls)
                    * float(profile["capacity"]["input_usd_per_million_tokens"])
                    + sum(int(row.get("output_tokens") or 0) for row in calls)
                    * float(profile["capacity"]["output_usd_per_million_tokens"])
                )
                / 1_000_000,
                8,
            ),
        },
        "findings": findings,
        "numeric_surface_receipts": numeric_surface_receipts,
        "raw_outputs": outputs,
        "direct_baseline_input_digest": case_input["model_visible_digest"],
        "agent_chain_input_digest": case_input["model_visible_digest"],
        "same_input_pair_proven": True,
        "business_artifact_promoted": False,
        "qualified_human_acceptance_required": True,
        "observed_at": observed_at,
        "known_boundary": (
            "This terminal preserves a raw fixed-pack research candidate. It does not "
            "prove dynamic tool research or authorize product delivery."
        ),
    }
    terminal = {**terminal_body, "terminal_digest": canonical_digest(terminal_body)}
    _atomic_json(root / "terminal.json", terminal)
    receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=terminal_status,
        terminal_phase=terminal_phase,
        terminal_code=terminal_code,
        terminal_result_digest=terminal["terminal_digest"],
        finalized_at=observed_at,
    )
    terminal["shared_admission_receipt"] = receipt.as_dict()
    _atomic_json(root / "terminal_with_receipt.json", terminal)
    return terminal


__all__ = [
    "COMPACT_VERIFIER_INPUT_SCHEMA",
    "COMPACT_VERIFIER_OUTPUT_SCHEMA",
    "NODE_ORDER",
    "S2FixedPackRuntimeError",
    "SPECIALIST_FAMILIES",
    "build_compact_verifier_projection",
    "build_node_request",
    "evaluate_final_output",
    "execute_case",
    "issue_case_admission",
    "perform_node_call",
    "resolve_final_output_numeric_surfaces",
    "validate_case_admission",
    "validate_compact_verifier_output",
]
