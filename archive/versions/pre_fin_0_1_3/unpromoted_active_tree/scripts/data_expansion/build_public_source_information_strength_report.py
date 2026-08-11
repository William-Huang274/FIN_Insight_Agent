from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_SCHEMA_VERSION = "fin_agent_public_source_information_strength_matrix_v0.1"
SUMMARY_SCHEMA_VERSION = "fin_agent_public_source_information_strength_summary_v0.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build no-commercial public source information-strength matrix.")
    parser.add_argument("--strength-config", default="configs/data_sources/public_source_information_strength_v0_1.yaml")
    parser.add_argument("--coverage-registry", default="configs/data_sources/public_source_coverage_v0_1.yaml")
    parser.add_argument("--availability-audit", default="data/manifests/public_source_full_availability_audit_v0_1.jsonl")
    parser.add_argument("--mapping-gate-summary", default="data/manifests/public_source_mapping_endpoint_gate_summary_v0_1.json")
    parser.add_argument("--inventory-adapter-summary", default="data/manifests/public_source_inventory_adapter_summary_v0_1.json")
    parser.add_argument("--matrix-output", default="data/manifests/public_source_information_strength_matrix_v0_1.jsonl")
    parser.add_argument("--summary-output", default="data/manifests/public_source_information_strength_summary_v0_1.json")
    parser.add_argument("--report-output", default="docs/internal/vnext_20260610/no_commercial_public_source_research_ceiling.zh-CN.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    strength_path = _resolve(args.strength_config)
    registry_path = _resolve(args.coverage_registry)
    audit_path = _resolve(args.availability_audit)
    mapping_summary_path = _resolve(args.mapping_gate_summary)
    adapter_summary_path = _resolve(args.inventory_adapter_summary)
    matrix_output = _resolve(args.matrix_output)
    summary_output = _resolve(args.summary_output)
    report_output = _resolve(args.report_output)
    generated_at = datetime.now(timezone.utc).isoformat()

    strength_config = _load_yaml(strength_path)
    registry = _load_yaml(registry_path)
    audit_rows = _read_jsonl(audit_path) if audit_path.exists() else []
    mapping_summary = _read_json(mapping_summary_path) if mapping_summary_path.exists() else {}
    adapter_summary = _read_json(adapter_summary_path) if adapter_summary_path.exists() else {}

    validation = validate_strength_config(strength_config, registry)
    if validation["error_count"]:
        print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
        return 2

    matrix_rows = build_matrix_rows(
        strength_config=strength_config,
        registry=registry,
        audit_rows=audit_rows,
        generated_at=generated_at,
    )
    summary = build_summary(
        strength_config=strength_config,
        matrix_rows=matrix_rows,
        validation=validation,
        mapping_summary=mapping_summary,
        adapter_summary=adapter_summary,
        generated_at=generated_at,
        inputs={
            "strength_config": strength_path,
            "coverage_registry": registry_path,
            "availability_audit": audit_path,
            "mapping_gate_summary": mapping_summary_path,
            "inventory_adapter_summary": adapter_summary_path,
        },
        outputs={
            "matrix": matrix_output,
            "summary": summary_output,
            "report": report_output,
        },
    )
    _write_jsonl(matrix_output, matrix_rows)
    _write_json(summary_output, summary)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_markdown_report(summary, matrix_rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def validate_strength_config(strength_config: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if strength_config.get("schema_version") != "fin_agent_public_source_information_strength_v0_1":
        errors.append({"type": "unsupported_schema_version", "schema_version": strength_config.get("schema_version")})
    tiers = strength_config.get("information_strength_tiers") or {}
    modes = strength_config.get("integration_modes") or {}
    assessments = strength_config.get("source_assessments") or []
    registry_sources = {str(source.get("source_id") or ""): source for source in registry.get("sources") or []}
    assessed_sources: set[str] = set()
    for assessment in assessments:
        source_id = str(assessment.get("source_id") or "")
        if not source_id:
            errors.append({"type": "assessment_missing_source_id"})
            continue
        if source_id in assessed_sources:
            errors.append({"type": "duplicate_source_assessment", "source_id": source_id})
        assessed_sources.add(source_id)
        if source_id not in registry_sources:
            errors.append({"type": "assessment_source_not_in_registry", "source_id": source_id})
        if assessment.get("information_strength_tier") not in tiers:
            errors.append({"type": "unknown_information_strength_tier", "source_id": source_id, "tier": assessment.get("information_strength_tier")})
        if assessment.get("integration_mode") not in modes:
            errors.append({"type": "unknown_integration_mode", "source_id": source_id, "integration_mode": assessment.get("integration_mode")})
        if not assessment.get("evidence_admissibility"):
            errors.append({"type": "missing_evidence_admissibility", "source_id": source_id})
        if not assessment.get("next_gate"):
            errors.append({"type": "missing_next_gate", "source_id": source_id})
        registry_source = registry_sources.get(source_id) or {}
        if registry_source.get("auth_status") == "commercial_deferred" and assessment.get("integration_mode") != "deferred_no_commercial_api":
            errors.append({"type": "commercial_source_not_deferred", "source_id": source_id})
        if assessment.get("information_strength_tier") == "S0_deferred_or_unofficial" and assessment.get("integration_mode") == "primary_evidence_authority":
            errors.append({"type": "s0_source_cannot_be_primary_evidence", "source_id": source_id})
        if assessment.get("information_strength_tier") in {"S1_resolver_or_lead", "S2_official_macro_industry_context"}:
            forbidden = " ".join(str(item) for item in assessment.get("forbidden_research_use") or [])
            if "company" not in forbidden and "financial" not in forbidden:
                warnings.append({"type": "low_strength_source_missing_company_fact_forbidden_use", "source_id": source_id})
    missing = sorted(set(registry_sources) - assessed_sources)
    extra = sorted(assessed_sources - set(registry_sources))
    for source_id in missing:
        errors.append({"type": "registry_source_missing_assessment", "source_id": source_id})
    for source_id in extra:
        errors.append({"type": "assessment_without_registry_source", "source_id": source_id})
    return {
        "schema_version": "fin_agent_public_source_information_strength_validation_v0.1",
        "source_count": len(registry_sources),
        "assessed_source_count": len(assessed_sources),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def build_matrix_rows(
    *,
    strength_config: dict[str, Any],
    registry: dict[str, Any],
    audit_rows: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    tiers = strength_config.get("information_strength_tiers") or {}
    modes = strength_config.get("integration_modes") or {}
    registry_by_source = {str(source.get("source_id") or ""): source for source in registry.get("sources") or []}
    audit_by_source = {str(row.get("source_id") or ""): row for row in audit_rows}
    rows: list[dict[str, Any]] = []
    for assessment in strength_config.get("source_assessments") or []:
        source_id = str(assessment.get("source_id") or "")
        registry_row = registry_by_source.get(source_id) or {}
        audit_row = audit_by_source.get(source_id) or {}
        tier_id = str(assessment.get("information_strength_tier") or "")
        mode_id = str(assessment.get("integration_mode") or "")
        tier = tiers.get(tier_id) or {}
        mode = modes.get(mode_id) or {}
        rows.append(
            {
                "schema_version": MATRIX_SCHEMA_VERSION,
                "generated_at": generated_at,
                "source_id": source_id,
                "provider": registry_row.get("provider", ""),
                "auth_status": registry_row.get("auth_status", ""),
                "source_families": registry_row.get("source_families") or [],
                "registry_claim_scope": registry_row.get("claim_scope", ""),
                "registry_gap_type": registry_row.get("gap_type", ""),
                "collector_status": registry_row.get("collector_status", ""),
                "parser_status": registry_row.get("parser_status", ""),
                "information_strength_tier": tier_id,
                "information_strength_score": tier.get("score"),
                "information_strength_label": tier.get("label", ""),
                "can_support_company_facts_by_source_strength": bool(tier.get("can_support_company_facts")),
                "integration_mode": mode_id,
                "runtime_surface": mode.get("runtime_surface", ""),
                "feature_flag_required": bool(mode.get("feature_flag_required")),
                "default_admissibility": mode.get("default_admissibility", ""),
                "readiness": assessment.get("readiness", ""),
                "evidence_admissibility": assessment.get("evidence_admissibility", ""),
                "current_quality_contribution": assessment.get("current_quality_contribution", ""),
                "potential_quality_contribution": assessment.get("potential_quality_contribution", ""),
                "allowed_research_use": assessment.get("allowed_research_use") or [],
                "forbidden_research_use": assessment.get("forbidden_research_use") or [],
                "next_gate": assessment.get("next_gate", ""),
                "availability_audit_status": audit_row.get("audit_status", ""),
                "availability_decision": audit_row.get("availability_decision", ""),
                "availability_scope": audit_row.get("availability_scope", ""),
                "target_universe_mapping": audit_row.get("target_universe_mapping", ""),
                "required_before_agent_use": audit_row.get("required_before_agent_use") or [],
            }
        )
    return sorted(rows, key=lambda row: (-int(row.get("information_strength_score") or 0), str(row.get("source_id") or "")))


def build_summary(
    *,
    strength_config: dict[str, Any],
    matrix_rows: list[dict[str, Any]],
    validation: dict[str, Any],
    mapping_summary: dict[str, Any],
    adapter_summary: dict[str, Any],
    generated_at: str,
    inputs: dict[str, Path],
    outputs: dict[str, Path],
) -> dict[str, Any]:
    runtime_surfaces = Counter(str(row.get("runtime_surface") or "") for row in matrix_rows)
    readiness_counts = Counter(str(row.get("readiness") or "") for row in matrix_rows)
    tier_counts = Counter(str(row.get("information_strength_tier") or "") for row in matrix_rows)
    integration_counts = Counter(str(row.get("integration_mode") or "") for row in matrix_rows)
    claim_evidence_sources = [
        row["source_id"]
        for row in matrix_rows
        if row.get("runtime_surface") in {"bounded_evidence", "exact_value_or_structured_fact", "company_product_operating_metric"}
    ]
    matrix_source_ids = {str(row.get("source_id") or "") for row in matrix_rows}
    adapter_runtime_sources = set((adapter_summary.get("runtime_counts_by_source") or {}).keys())
    current_runtime_candidates = sorted(
        (adapter_runtime_sources & matrix_source_ids)
        | {
            row["source_id"]
            for row in matrix_rows
            if row.get("readiness") in {"accepted_core", "accepted_context_path", "validated_context_candidate"}
        }
    )
    blocked_or_deferred = [
        row["source_id"]
        for row in matrix_rows
        if row.get("readiness") in {"blocked_credential", "profile_validation_pending", "parser_required", "source_plan_only", "deferred_no_commercial_api"}
    ]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass" if validation["error_count"] == 0 else "fail",
        "generated_at": generated_at,
        "policy": strength_config.get("policy") or {},
        "quality_ceiling": strength_config.get("research_quality_ceiling") or {},
        "validation": validation,
        "source_count": len(matrix_rows),
        "tier_counts": dict(sorted(tier_counts.items())),
        "integration_mode_counts": dict(sorted(integration_counts.items())),
        "runtime_surface_counts": dict(sorted(runtime_surfaces.items())),
        "readiness_counts": dict(sorted(readiness_counts.items())),
        "claim_evidence_source_count": len(claim_evidence_sources),
        "claim_evidence_sources": sorted(claim_evidence_sources),
        "current_runtime_candidate_sources": current_runtime_candidates,
        "blocked_or_deferred_source_count": len(blocked_or_deferred),
        "blocked_or_deferred_sources": sorted(blocked_or_deferred),
        "mapping_gate_status": mapping_summary.get("status", ""),
        "mapping_gate_universe_company_count": mapping_summary.get("universe_company_count"),
        "inventory_adapter_status": adapter_summary.get("status", ""),
        "inventory_adapter_runtime_sources": sorted(adapter_runtime_sources),
        "inventory_adapter_synthetic_or_internal_sources": sorted(adapter_runtime_sources - matrix_source_ids),
        "inventory_adapter_runtime_eligible_row_count": adapter_summary.get("runtime_eligible_row_count"),
        "inventory_adapter_bounded_evidence_eligible_row_count": adapter_summary.get("bounded_evidence_eligible_row_count"),
        "inventory_adapter_exact_value_authority_row_count": adapter_summary.get("exact_value_authority_row_count"),
        "inputs": {key: _repo_path(value) for key, value in inputs.items()},
        "outputs": {key: _repo_path(value) for key, value in outputs.items()},
    }


def render_markdown_report(summary: dict[str, Any], matrix_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 不使用商业 API 的公开数据源研报质量上限",
        "",
        "## 状态",
        "",
        f"- 生成时间：`{summary.get('generated_at')}`",
        "- 策略：不采购商业 API；只使用公开、官方、免费 key、open-bulk 和已审计 no-key 来源。",
        f"- 数据源数量：`{summary.get('source_count')}`",
        f"- 当前 runtime 候选：`{len(summary.get('current_runtime_candidate_sources') or [])}` 个 source",
        f"- parser/gate 通过后可成为 claim evidence 的 source 候选：`{summary.get('claim_evidence_source_count')}` 个",
        "",
        "## 研报质量上限",
        "",
        f"- 当前已验证上限：`{(summary.get('quality_ceiling') or {}).get('overall_current_verified_ceiling')}`",
        f"- 公开源 buildout 完成后的潜在上限：`{(summary.get('quality_ceiling') or {}).get('overall_potential_after_public_buildout')}`",
        "",
        "| 研究维度 | 当前上限 | 潜在上限 | 硬边界 |",
        "| --- | --- | --- | --- |",
    ]
    for item in (summary.get("quality_ceiling") or {}).get("dimensions") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("dimension") or ""),
                    str(item.get("current_ceiling") or ""),
                    str(item.get("potential_ceiling") or ""),
                    str(item.get("hard_limit") or "").replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 信息强度矩阵",
            "",
            "| 强度层级 | Source | 接入方式 | 当前可用度 | 当前贡献 | 潜在贡献 | 下一道 gate |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in matrix_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("information_strength_tier") or ""),
                    str(row.get("source_id") or ""),
                    str(row.get("integration_mode") or ""),
                    str(row.get("readiness") or ""),
                    str(row.get("current_quality_contribution") or "").replace("|", "/"),
                    str(row.get("potential_quality_contribution") or "").replace("|", "/"),
                    str(row.get("next_gate") or "").replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## 硬边界",
            "",
            "- S5/S4 来源只有在 parser、citation、period、unit 和 source-boundary gate 通过后，才能支持公司级事实。",
            "- S3 来源支持官方监管、产品状态、ownership 或 entity context，但不能证明商业采用、销售或盈利。",
            "- S2 来源只能支持宏观/行业上下文，不能被改写为公司级收入、利润、客户或产品销量事实。",
            "- S1 来源是 resolver、discovery、technology signal 或 event lead，进入 claim 前必须回到更高强度来源核验。",
            "- S0 和 commercial-deferred 来源在当前 no-commercial policy 下只能作为显式 source gap 或 provisional context。",
            "",
        ]
    )
    return "\n".join(lines)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
