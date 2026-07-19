"""Deterministic historical-case and sector-report calibration audits."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


HISTORICAL_SOURCE_SCHEMA = "finsight_historical_case_audit_sources_v0_1"
HISTORICAL_AUDIT_SCHEMA = "finsight_historical_case_performance_audit_v0_1"
ARCHETYPE_SOURCE_SCHEMA = "finsight_sector_report_archetype_sources_v0_1"
ARCHETYPE_AUDIT_SCHEMA = "finsight_sector_report_archetype_audit_v0_1"
CALIBRATION_SELECTION_SCHEMA = "finsight_calibration_case_selection_v0_1"


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_rows(path: Path, source: Mapping[str, Any]) -> list[dict[str, Any]]:
    if source.get("format") == "jsonl" or path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    payload = load_json(path)
    rows = payload.get(str(source.get("rows_key") or "cases"), [])
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _sector_from_text(*values: Any) -> str:
    text = " ".join(str(value or "") for value in values).lower()
    rules = (
        ("banks_financials", ("bank", "financial", "jpm", "bac", "credit", "deposit", "capital market")),
        ("healthcare_pharma_medtech", ("health", "pharma", "biotech", "medtech", "lly", "nvo", "drug")),
        ("retail_consumer", ("retail", "consumer", "cpg", "restaurant", "travel", "wmt", "cost", "inventory")),
        ("energy_utilities_industrials", ("energy", "utility", "industrial", "materials", "xom", "cvx", "power", "wind")),
        ("auto_mobility", ("auto", "mobility", "transport", "tsla", "vehicle", "ev_")),
        ("technology_software_services", ("software", "cloud", "saas", "developer", "cyber", "crm", "ddog")),
        ("semiconductors_ai_infrastructure", ("semi", "ai_infra", "ai infrastructure", "nvda", "asml", "accelerator")),
        ("consumer_hardware", ("hardware", "device", "aapl", "hpq", "sony")),
    )
    for sector, needles in rules:
        if any(needle in text for needle in needles):
            return sector
    return "cross_sector_or_unclassified"


def _maturity_from_readiness(row: Mapping[str, Any]) -> str:
    artifact = str((row.get("artifact_backed_evidence_depth") or {}).get("status") or "")
    specialist = str((row.get("fresh_all_specialist_gold_pass") or {}).get("status") or "")
    contract = str((row.get("runtime_contract") or {}).get("status") or "")
    if specialist == "pass":
        return "fresh_specialist_proven"
    if artifact == "pass":
        return "artifact_backed"
    if contract == "pass":
        return "contract_ready"
    return "catalog_only"


def validate_historical_source_config(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != HISTORICAL_SOURCE_SCHEMA:
        errors.append("historical_source_schema_invalid")
    source_ids: list[str] = []
    for source in [*(payload.get("catalog_sources") or []), *(payload.get("readiness_sources") or [])]:
        source_id = str(source.get("source_id") or "")
        source_ids.append(source_id)
        if not source_id or not source.get("path"):
            errors.append("historical_source_identity_or_path_missing")
    if len(source_ids) != len(set(source_ids)):
        errors.append("historical_source_id_duplicate")
    run_ids = [str(row.get("run_evidence_id") or "") for row in payload.get("run_evidence_sources") or []]
    if len(run_ids) != len(set(run_ids)) or any(not value for value in run_ids):
        errors.append("historical_run_evidence_id_invalid")
    maturity = payload.get("maturity_order") or []
    if len(maturity) != len(set(maturity)) or "catalog_only" not in maturity:
        errors.append("historical_maturity_order_invalid")
    return errors


def build_historical_case_audit(repo_root: str | Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    errors = validate_historical_source_config(payload)
    maturity_order = list(payload.get("maturity_order") or [])
    maturity_rank = {name: index for index, name in enumerate(maturity_order)}
    cases: dict[str, dict[str, Any]] = {}
    source_counts: dict[str, int] = {}

    for source in payload.get("catalog_sources") or []:
        path = root / str(source["path"])
        if not path.exists():
            errors.append(f"catalog_source_missing:{source['source_id']}")
            continue
        rows = _load_rows(path, source)
        source_counts[str(source["source_id"])] = len(rows)
        for row in rows:
            case_id = str(row.get("case_id") or "")
            if not case_id:
                errors.append(f"catalog_case_id_missing:{source['source_id']}")
                continue
            candidate_maturity = str(source.get("evidence_level") or "catalog_only")
            current = cases.setdefault(
                case_id,
                {
                    "case_id": case_id,
                    "sector": _sector_from_text(
                        row.get("industry_schema"), row.get("case_family"), row.get("category"),
                        row.get("prompt"), row.get("focus_tickers"),
                    ),
                    "case_family": row.get("case_family") or row.get("category") or "unspecified",
                    "focus_tickers": row.get("focus_tickers") or [],
                    "source_memberships": [],
                    "maturity": candidate_maturity,
                    "runtime_contract_status": "not_explicitly_proven",
                    "artifact_depth_status": "not_explicitly_proven",
                    "fresh_specialist_status": "not_explicitly_proven",
                    "full_chain_status": "not_explicitly_proven",
                    "human_acceptance_status": "not_explicitly_proven",
                    "blocking_reasons": [],
                },
            )
            current["source_memberships"].append(str(source["source_id"]))
            if maturity_rank.get(candidate_maturity, 0) > maturity_rank.get(current["maturity"], 0):
                current["maturity"] = candidate_maturity

    readiness_rows = 0
    readiness_source_summaries = []
    for source in sorted(payload.get("readiness_sources") or [], key=lambda item: item.get("authority_rank", 0)):
        path = root / str(source["path"])
        if not path.exists():
            errors.append(f"readiness_source_missing:{source['source_id']}")
            continue
        data = load_json(path)
        rows = data.get(str(source.get("rows_key") or "case_results"), [])
        readiness_rows += len(rows)
        metrics = data.get("metrics") or {}
        readiness_source_summaries.append(
            {
                "source_id": source["source_id"],
                "status": data.get("status"),
                "case_count": data.get("case_count", metrics.get("case_count", len(rows))),
                "artifact_ready_count": data.get("artifact_ready_count", metrics.get("artifact_ready_count")),
                "fresh_specialist_pass_count": data.get("fresh_specialist_pass_count", metrics.get("fresh_all_specialist_pass_count")),
                "runtime_contract_ready_count": data.get("runtime_contract_ready_count", metrics.get("runtime_contract_ready_count")),
                "blocking_case_count": data.get("blocking_case_count", metrics.get("blocking_case_count")),
                "adapter": source.get("adapter", "nested_readiness"),
            }
        )
        for row in rows:
            case_id = str(row.get("case_id") or "")
            if not case_id:
                continue
            current = cases.setdefault(
                case_id,
                {
                    "case_id": case_id,
                    "sector": _sector_from_text(row.get("vertical"), row.get("case_type"), case_id),
                    "case_family": row.get("case_type") or "readiness_case",
                    "focus_tickers": [],
                    "source_memberships": [],
                    "full_chain_status": "not_explicitly_proven",
                    "human_acceptance_status": "not_explicitly_proven",
                },
            )
            if str(source["source_id"]) not in current["source_memberships"]:
                current["source_memberships"].append(str(source["source_id"]))
            if source.get("adapter") == "no_paid_multicase_audit":
                fresh_status = row.get("fresh_all_specialist_status") or "not_required_or_not_proven"
                evidence_status = row.get("evidence_depth_status")
                maturity = (
                    "fresh_specialist_fixture_proven"
                    if fresh_status == "pass"
                    else "exemplar_artifact_backed" if evidence_status == "pass" else "contract_ready"
                )
                artifact_basis = (
                    "case_specific_ai_semis_gold_pack"
                    if row.get("case_type") == "deep_gold_case"
                    else "gold_exemplar_backed_not_live_runtime"
                )
                readiness_projection = {
                    "maturity": maturity,
                    "runtime_contract_status": "pass",
                    "artifact_depth_status": evidence_status,
                    "artifact_basis": artifact_basis,
                    "fresh_specialist_status": fresh_status,
                    "matrix_audit_status": data.get("status"),
                    "blocking_reasons": row.get("blocking_reasons") or [],
                    "next_repair": [],
                }
            else:
                readiness_projection = {
                    "maturity": "live_artifact_backed" if _maturity_from_readiness(row) == "artifact_backed" else _maturity_from_readiness(row),
                    "runtime_contract_status": (row.get("runtime_contract") or {}).get("status"),
                    "artifact_depth_status": (row.get("artifact_backed_evidence_depth") or {}).get("status"),
                    "artifact_basis": "historical_readiness_projection",
                    "fresh_specialist_status": (row.get("fresh_all_specialist_gold_pass") or {}).get("status"),
                    "matrix_audit_status": row.get("matrix_audit_status"),
                    "blocking_reasons": row.get("blocking_reasons") or [],
                    "next_repair": row.get("next_repair") or [],
                }
            current.update(
                {
                    "vertical": row.get("vertical"),
                    **readiness_projection,
                }
            )

    rows = sorted(cases.values(), key=lambda item: item["case_id"])
    maturity_counts = Counter(row.get("maturity", "catalog_only") for row in rows)
    sector_counts = Counter(row["sector"] for row in rows)
    comparable_rows = [
        row for row in rows
        if row.get("maturity") in {"node_level_proven", "full_chain_proven", "human_accepted"}
    ]
    run_evidence = []
    for source in payload.get("run_evidence_sources") or []:
        row = dict(source)
        artifact_path = row.get("artifact_path")
        worklog_path = row.get("worklog_path")
        row["artifact_present"] = bool(artifact_path and (root / str(artifact_path)).exists())
        row["worklog_present"] = bool(worklog_path and (root / str(worklog_path)).exists())
        if artifact_path and not row["artifact_present"]:
            errors.append(f"run_evidence_artifact_missing:{row['run_evidence_id']}")
        if worklog_path and not row["worklog_present"]:
            errors.append(f"run_evidence_worklog_missing:{row['run_evidence_id']}")
        run_evidence.append(row)
    legacy_diagnostics = [row for row in run_evidence if row.get("runtime_generation") == "legacy_sec_benchmark_pipeline"]
    current_diagnostics = [row for row in run_evidence if row.get("runtime_generation") != "legacy_sec_benchmark_pipeline"]
    return {
        "schema_version": HISTORICAL_AUDIT_SCHEMA,
        "audit_id": payload.get("audit_id"),
        "status": "pass" if not errors else "fail",
        "source_membership_row_count": sum(source_counts.values()),
        "unique_case_count": len(rows),
        "catalog_source_counts": source_counts,
        "readiness_row_count": readiness_rows,
        "readiness_source_summaries": readiness_source_summaries,
        "maturity_counts": dict(sorted(maturity_counts.items())),
        "sector_counts": dict(sorted(sector_counts.items())),
        "artifact_backed_case_count": sum(row.get("maturity") in {"exemplar_artifact_backed", "live_artifact_backed", "fresh_specialist_fixture_proven", "node_level_proven", "full_chain_proven", "human_accepted"} for row in rows),
        "exemplar_artifact_backed_case_count": sum(row.get("maturity") == "exemplar_artifact_backed" for row in rows),
        "live_or_case_specific_artifact_case_count": sum(row.get("artifact_basis") == "case_specific_ai_semis_gold_pack" for row in rows),
        "fresh_specialist_fixture_proven_case_count": sum(row.get("maturity") == "fresh_specialist_fixture_proven" for row in rows),
        "fresh_specialist_proven_case_count": sum(row.get("maturity") == "node_level_proven" for row in rows),
        "explicit_full_chain_proven_case_count": sum(row.get("maturity") == "full_chain_proven" for row in rows),
        "explicit_human_accepted_case_count": sum(row.get("maturity") == "human_accepted" for row in rows),
        "cross_sector_comparable_performance_case_count": len(comparable_rows),
        "generalization_status": "not_proven" if len({row["sector"] for row in comparable_rows}) < 3 else "provisionally_proven",
        "historical_run_evidence": run_evidence,
        "legacy_benchmark_diagnostic_run_count": len(legacy_diagnostics),
        "current_multi_agent_or_manual_run_evidence_count": len(current_diagnostics),
        "current_runtime_cross_sector_generalization_status": "not_proven",
        "cases": rows,
        "errors": errors,
        "boundaries": {
            "catalog_count_is_not_performance": True,
            "fixture_definition_is_not_runtime_consumption": True,
            "artifact_file_presence_is_not_full_chain_acceptance": True,
            "paid_model_or_full_chain_executed": False,
            "legacy_sec_benchmark_is_not_current_agentic_runtime": True,
            "diagnostic_gate_pass_is_not_client_ready_acceptance": True,
        },
    }


def validate_archetype_source_config(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != ARCHETYPE_SOURCE_SCHEMA:
        errors.append("archetype_source_schema_invalid")
    ids = [str(row.get("source_id") or "") for row in payload.get("sources") or []]
    if not ids or any(not value for value in ids):
        errors.append("archetype_source_id_missing")
    if len(ids) != len(set(ids)):
        errors.append("archetype_source_id_duplicate")
    for row in payload.get("sources") or []:
        if not (row.get("url") or row.get("local_manifest_path")) or not row.get("sector") or not row.get("observed_sections"):
            errors.append(f"archetype_source_required_field_missing:{row.get('source_id')}")
    return errors


def build_sector_report_archetype_audit(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors = validate_archetype_source_config(payload)
    sources = list(payload.get("sources") or [])
    section_counts = Counter(section for row in sources for section in row.get("observed_sections") or [])
    sector_rows: dict[str, dict[str, Any]] = {}
    for sector, grouped in _group_by(sources, "sector").items():
        sector_rows[sector] = {
            "sector": sector,
            "source_ids": [row["source_id"] for row in grouped],
            "section_archetypes": sorted({value for row in grouped for value in row.get("observed_sections") or []}),
            "decision_mechanisms": sorted({value for row in grouped for value in row.get("decision_mechanisms") or []}),
            "key_metrics": sorted({value for row in grouped for value in row.get("key_metrics") or []}),
            "evidence_families": sorted({value for row in grouped for value in row.get("evidence_families") or []}),
        }
    universal = sorted(section for section, count in section_counts.items() if count >= 4)
    return {
        "schema_version": ARCHETYPE_AUDIT_SCHEMA,
        "audit_id": payload.get("audit_id"),
        "status": "pass" if not errors else "fail",
        "source_count": len(sources),
        "sector_count": len(sector_rows),
        "universal_section_archetypes": universal,
        "section_frequency": dict(sorted(section_counts.items())),
        "sector_archetypes": [sector_rows[key] for key in sorted(sector_rows)],
        "report_type_archetypes": payload.get("report_type_archetypes") or [],
        "sources": sources,
        "design_conclusions": {
            "three_layer_cell_model_required": True,
            "universal_archetype_plus_sector_pack_plus_case_instance": True,
            "report_type_is_orthogonal_to_sector": True,
            "valuation_method_must_be_sector_aware": True,
            "commercial_gap_policy_must_be_sector_aware": True,
            "what_would_change_is_a_research_surface": True,
        },
        "errors": errors,
    }


def _group_by(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return grouped


def build_calibration_case_selection(
    historical_audit: Mapping[str, Any], archetype_audit: Mapping[str, Any]
) -> dict[str, Any]:
    known = {row["case_id"]: row for row in historical_audit.get("cases") or []}
    positive_specs = [
        ("ai_infra_anchor", "ai_semis_dell_nvda_anchor_v0_1", "supply_chain_capital_intensive", "anchor_artifact_backed"),
        ("saas_platform_shadow", "v3_software_cloud_developer_products_financial_product_bridge_001", "subscription_platform", "shadow_contract_calibration"),
        ("regulated_product_shadow", "v4_pharma_biotech_medtech_financial_product_bridge_001", "regulated_milestone", "shadow_contract_calibration"),
        ("balance_sheet_shadow", "v6_banks_financials_capital_markets_financial_product_bridge_001", "balance_sheet_credit", "ontology_stress_shadow"),
    ]
    negative_ids = [
        "negative_relationship_graph_not_financial_fact_v0_1",
        "negative_parser_gap_not_public_source_absent_v0_1",
        "negative_commercial_tracker_boundary_v0_1",
    ]
    positives = [
        {
            "selection_id": selection_id,
            "case_id": case_id,
            "mechanism": mechanism,
            "role": role,
            "historical_maturity": known.get(case_id, {}).get("maturity", "missing"),
            "selection_status": "selected" if case_id in known else "blocked_missing_case",
        }
        for selection_id, case_id, mechanism, role in positive_specs
    ]
    negatives = [
        {
            "case_id": case_id,
            "historical_maturity": known.get(case_id, {}).get("maturity", "missing"),
            "selection_status": "selected" if case_id in known else "blocked_missing_case",
        }
        for case_id in negative_ids
    ]
    errors = []
    if historical_audit.get("status") != "pass":
        errors.append("historical_audit_not_pass")
    if archetype_audit.get("status") != "pass":
        errors.append("archetype_audit_not_pass")
    if any(row["selection_status"] != "selected" for row in [*positives, *negatives]):
        errors.append("selected_case_missing")
    return {
        "schema_version": CALIBRATION_SELECTION_SCHEMA,
        "status": "pass" if not errors else "fail",
        "positive_cases": positives,
        "negative_controls": negatives,
        "selection_rationale": [
            "Retain the only artifact-backed AI/Semis case as an anchor, not as proof of generalization.",
            "Add SaaS, regulated healthcare and bank shadow cases because their economic mechanisms and valuation ontologies differ materially.",
            "Use negative controls to test evidence authority, parser/source-gap typing and commercial-data boundaries.",
        ],
        "execution_policy": {
            "phase_1": "deterministic_compiler_and_reviewer_calibration_only",
            "paid_node_allowed_after_gate": True,
            "full_chain_allowed": False,
            "shadow_cases_are_not_quality_passes": True,
        },
        "promotion_gates": [
            "decision_surface_schema_valid",
            "sector_required_cells_present",
            "forbidden_substitution_rules_present",
            "negative_controls_fail_closed",
            "human_reviewer_cell_granularity_accepted",
            "legacy_projection_diff_explained",
        ],
        "errors": errors,
    }


def render_historical_audit_markdown(audit: Mapping[str, Any]) -> str:
    readiness = audit.get("readiness_source_summaries") or []
    lines = [
        "# 历史 Case 表现审计",
        "",
        "日期：2026-07-11",
        "",
        f"状态：`{audit['status']}`。本审计未运行 paid model 或 full-chain。",
        "",
        "## 核心结论",
        "",
        f"- Catalog/source memberships：{audit['source_membership_row_count']}；去重 case：{audit['unique_case_count']}。",
        f"- Artifact-backed cases：{audit['artifact_backed_case_count']}，其中 gold-exemplar-backed {audit['exemplar_artifact_backed_case_count']}，case-specific AI/Semis pack {audit['live_or_case_specific_artifact_case_count']}。",
        f"- No-paid fresh specialist fixture proven：{audit['fresh_specialist_fixture_proven_case_count']}；真实 node-level fresh specialist proof：{audit['fresh_specialist_proven_case_count']}。",
        f"- Explicit full-chain proven：{audit['explicit_full_chain_proven_case_count']}。",
        f"- Explicit human-accepted：{audit['explicit_human_accepted_case_count']}。",
        f"- 跨行业可比表现 case：{audit['cross_sector_comparable_performance_case_count']}；泛化状态：`{audit['generalization_status']}`。",
        "",
        "历史 case 数量说明测试意图覆盖较宽，但不能证明 agent 已跨行业稳定运行。只有显式 readiness、node/full-chain gate 和 reviewer record 才能提升成熟度。",
        "",
        "需要同时保留一个正向事实：旧 SEC benchmark 曾在 cross-industry10 和 combined40 上通过 deterministic diagnostics。这证明旧链路的 SEC 检索、exact-value ledger、Judgment Plan 和受约束合成有可复用资产，但它不是当前 DecisionSurface / agentic-research runtime 的泛化证明。",
        "",
        "## Readiness 权威记录",
        "",
        "| Source | Status | Cases | Artifact ready | Fresh specialist | Contract ready | Blocking |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in readiness:
        lines.append(
            f"| {row['source_id']} | {row.get('status')} | {row.get('case_count')} | "
            f"{row.get('artifact_ready_count')} | {row.get('fresh_specialist_pass_count')} | "
            f"{row.get('runtime_contract_ready_count')} | {row.get('blocking_case_count')} |"
        )
    lines.extend(["", "## 成熟度分布", ""])
    for key, value in audit.get("maturity_counts", {}).items():
        lines.append(f"- `{key}`：{value}")
    lines.extend(["", "## 历史运行证据", "", "| Run | Generation | Scope | Result | Boundary |", "| --- | --- | --- | --- | --- |"])
    for row in audit.get("historical_run_evidence") or []:
        lines.append(
            f"| {row['run_evidence_id']} | {row['runtime_generation']} | {row['scope']} | "
            f"{row['result_class']} | {row['claim_boundary']} |"
        )
    lines.extend(
        [
            "",
            "## 对首批 Calibration 的影响",
            "",
            "1. P36/AI infrastructure 只能作为 artifact-backed anchor，不能作为泛化证明。",
            "2. SaaS、Healthcare、Banks 应作为 shadow calibration case，引入不同经济机制和估值本体。",
            "3. 第一轮只校准 DecisionSurface compiler、cell 粒度、sector required cells 和 forbidden substitutions。",
            "4. 不用新 paid/full-chain run 补审计证据；后续单节点 paid run 必须经过 deterministic 与人工 gate。",
            "",
            "## 审计边界",
            "",
            "- `catalog_only`：只有题目/预期合同。",
            "- `fixture_defined`：有行业 fixture，但不表示 runtime 消费。",
            "- `contract_ready`：合同已编译，不表示 evidence/artifact 质量通过。",
            "- `exemplar_artifact_backed`：gold exemplar 已编译成 pack，不表示 live source/runtime。",
            "- `live_artifact_backed`：存在 case-specific evidence artifact，但仍不等于 fresh specialist/full-chain。",
            "- `fresh_specialist_fixture_proven`：no-paid specialist fixture 通过，不表示真实模型节点或 full-chain。",
            "- 输出目录或历史文件名不自动晋升成熟度。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_archetype_audit_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# 跨行业投研报告结构审计",
        "",
        "日期：2026-07-11",
        "",
        f"状态：`{audit['status']}`；来源 {audit['source_count']} 个，覆盖 {audit['sector_count']} 个 sector/archetype groups。",
        "",
        "## 核心结论",
        "",
        "公开专业报告支持三层 DecisionSurface：通用 archetype + sector cell pack + case instance。行业差异不只体现在 metric 名称，还体现在经济机制、证据 authority、commercial gap 和估值方法。",
        "",
        "报告类型与行业是两个正交轴。Initiation、earnings/event update、sector thematic 和 peer comparison 即使处于同一行业，也需要不同的 required surfaces。",
        "",
        "## Sector Archetypes",
        "",
        "| Sector | Decision mechanisms | Key metrics | Evidence families |",
        "| --- | --- | --- | --- |",
    ]
    for row in audit.get("sector_archetypes") or []:
        lines.append(
            f"| {row['sector']} | {', '.join(row['decision_mechanisms'])} | "
            f"{', '.join(row['key_metrics']) or '-'} | {', '.join(row['evidence_families'])} |"
        )
    lines.extend(
        [
            "",
            "## 需要进入设计的结论",
            "",
            "1. 通用 cells 稳定 thesis、business model、financial quality、valuation/price-in、risk/counterevidence、what-would-change。",
            "2. Sector pack 拥有本行业的 mechanism、metric ontology、source policy、forbidden substitutions 和 valuation method。",
            "3. Case instance 只实例化、裁剪和增加少量事件特有 cell，不能随手改写 archetype。",
            "4. Banks 必须 balance-sheet-first；Healthcare 必须分开 regulatory eligibility、reimbursement、adoption；Retail 必须拆 traffic/ticket/price/mix/inventory；Energy/Industrial 必须包含项目经济、物理产能和政策；Technology 必须连接 product adoption、monetization、recurring mix 和 capital allocation。",
            "5. What-Would-Change 是独立研究表面，应包含 threshold、current state、所需 evidence 和未闭环 gap，不并入主结论冒充已证实判断。",
            "",
            "## Sources",
            "",
        ]
    )
    for row in audit.get("sources") or []:
        if row.get("url"):
            label = f"[{row['title']}]({row['url']})"
        else:
            label = f"{row['title']}（`{row['local_manifest_path']}`）"
        lines.append(f"- {label}：{row['audit_note']}")
    return "\n".join(lines) + "\n"


def render_calibration_selection_markdown(selection: Mapping[str, Any]) -> str:
    lines = [
        "# 首批 Calibration Case 选择",
        "",
        "日期：2026-07-11",
        "",
        f"状态：`{selection['status']}`。此选择用于 DecisionSurface shadow calibration，不是 full-chain release set。",
        "",
        "## Positive Cases",
        "",
        "| Case | Mechanism | Role | Historical maturity |",
        "| --- | --- | --- | --- |",
    ]
    for row in selection.get("positive_cases") or []:
        lines.append(f"| {row['case_id']} | {row['mechanism']} | {row['role']} | {row['historical_maturity']} |")
    lines.extend(["", "## Negative Controls", ""])
    for row in selection.get("negative_controls") or []:
        lines.append(f"- `{row['case_id']}`：{row['historical_maturity']}")
    lines.extend(
        [
            "",
            "## 执行边界",
            "",
            "- Phase 1：deterministic compiler + reviewer calibration。",
            "- AI/Semis 是 anchor；SaaS、Healthcare、Banks 是 shadow，不得写成历史质量 pass。",
            "- Deterministic 和人工 gate 通过后，允许 DecisionSurface Compiler 单节点 paid comparison。",
            "- 不允许 full-chain，不进入 Writer，不据此宣称行业 runtime 已完成。",
        ]
    )
    return "\n".join(lines) + "\n"
