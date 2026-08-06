from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


POLICY_SCHEMA = "fin_ia_0_1_3_s3_workpaper_writer_content_policy_v1_0"
PROGRAM_SCHEMA = "fin_ia_0_1_3_s3_workpaper_writer_content_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S3.workpaper_writer_decision_ready_content:v1"
CASES = ("DELL", "MU", "NVDA")
CORE_CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)


class S3WorkpaperWriterContentError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_s3_workpaper_writer_content_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or len(policy.get("required_lenses") or ()) != 8
        or len(policy.get("required_answer_fields") or ()) != 5
        or tuple(sorted(policy.get("case_rules") or {})) != CASES
    ):
        raise S3WorkpaperWriterContentError("s3_writer_policy_invalid")
    boundary = policy.get("authority_boundary") or {}
    if (
        boundary.get("writer_is_no_source") is not True
        or boundary.get("raw_retrieval_visible_to_writer") is not False
        or boundary.get("planned_cells_may_be_rendered_as_findings") is not False
        or boundary.get("fixture_mixed_preview_is_product_delivery") is not False
        or boundary.get("model_visible_writer_input_activated") is not False
        or boundary.get("additional_paid_canary_required_now") is not False
    ):
        raise S3WorkpaperWriterContentError("s3_writer_authority_policy_invalid")
    expected_lenses = set(policy["required_lenses"]) - {"executive_thesis", "gaps_and_what_would_change"}
    for case_key, rule in policy["case_rules"].items():
        if not rule.get("company_name") or rule.get("ticker") != case_key or not rule.get("case_thesis_frame"):
            raise S3WorkpaperWriterContentError("s3_writer_case_rule_invalid")
        if set(rule.get("lens_rules") or {}) != expected_lenses:
            raise S3WorkpaperWriterContentError("s3_writer_lens_rule_surface_invalid")
        for lens_rule in rule["lens_rules"].values():
            if not lens_rule.get("decision_frame") or not isinstance(lens_rule.get("source_cells"), list) or not lens_rule.get("planned_cells"):
                raise S3WorkpaperWriterContentError("s3_writer_lens_rule_invalid")
    return policy


def compile_s3_workpaper_writer_content_program(
    *, policy: Mapping[str, Any], claim_decision: Mapping[str, Any], synthesis_decision: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        claim_decision.get("acceptance", {}).get("S3_02") != "engineering_pass"
        or synthesis_decision.get("acceptance", {}).get("S3_03") != "engineering_pass"
        or not _record_digest_ok(claim_decision)
        or not _record_digest_ok(synthesis_decision)
    ):
        raise S3WorkpaperWriterContentError("s3_writer_upstream_invalid")
    cards = claim_decision["claim_quality_program"]["core_claim_cards"]
    syntheses = synthesis_decision["cross_cell_synthesis_program"]["case_syntheses"]
    planned = claim_decision["claim_quality_program"]["planned_dynamic_cells_without_claim_choice"]
    card_map = {(str(row["case_key"]), str(row["program_cell_id"])): row for row in cards}
    synthesis_map = {str(row["case_key"]): row for row in syntheses}
    planned_map = {
        (str(row["case_key"]), str(row["cell_key"])): row for row in planned
    }
    workpapers = []
    for case_key in CASES:
        workpapers.append(
            _compile_case_workpaper(
                case_key=case_key,
                rule=policy["case_rules"][case_key],
                required_lenses=policy["required_lenses"],
                card_map=card_map,
                synthesis=synthesis_map[case_key],
                planned_map=planned_map,
            )
        )
    observed = {
        "case_workpapers": len(workpapers),
        "content_lenses": sum(len(row["sections"]) for row in workpapers),
        "bounded_judgment_lenses": sum(
            section["coverage_status"] == "bounded_judgment"
            for row in workpapers
            for section in row["sections"]
        ),
        "explicit_research_gap_lenses": sum(
            section["coverage_status"] == "explicit_research_gap"
            for row in workpapers
            for section in row["sections"]
        ),
        "natural_product_candidates": sum(row["workpaper_authority"] == "all_natural_candidate" for row in workpapers),
        "fixture_mixed_engineering_previews": sum(row["workpaper_authority"] == "fixture_mixed_engineering_only" for row in workpapers),
        "planned_cells_rendered_as_findings": 0,
        "writer_raw_source_rows": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "business_runs": 0,
    }
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "upstream_digests": {
            "S3_02": claim_decision["record_digest"],
            "S3_03": synthesis_decision["record_digest"],
        },
        "case_workpapers": workpapers,
        "observed_counts": observed,
        "stage_boundary": {
            "S3_04": "engineering_pass_decision_ready_content_contract_and_fixture_preview",
            "fixture_preview_is_product_delivery": False,
            "all_natural_workpapers": 0,
            "writer_no_source_contract": True,
            "provider_output_schema_changed": False,
            "model_visible_writer_input_activated": False,
            "additional_paid_canary_required_now": False,
            "formal_full_chain": False,
            "eight_dimension_quality_acceptance": False,
            "qualified_human_content_acceptance": False,
            "product_acceptance": False,
            "release": False,
            "S3_05_quality_gate": "next_not_started",
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_s3_workpaper_writer_content_program(program, policy=policy)
    return program


def validate_s3_workpaper_writer_content_program(program: Mapping[str, Any], *, policy: Mapping[str, Any]) -> None:
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("policy_digest") != canonical_digest(policy)
        or program.get("program_digest") != canonical_digest(body)
    ):
        raise S3WorkpaperWriterContentError("s3_writer_program_binding_invalid")
    workpapers = program.get("case_workpapers") or []
    if [row.get("case_key") for row in workpapers] != list(CASES):
        raise S3WorkpaperWriterContentError("s3_writer_case_surface_invalid")
    for row in workpapers:
        validate_s3_case_workpaper(row, policy=policy)
    expected = {
        "case_workpapers": 3,
        "content_lenses": 24,
        "bounded_judgment_lenses": 21,
        "explicit_research_gap_lenses": 3,
        "natural_product_candidates": 0,
        "fixture_mixed_engineering_previews": 3,
        "planned_cells_rendered_as_findings": 0,
        "writer_raw_source_rows": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "business_runs": 0,
    }
    if program.get("observed_counts") != expected:
        raise S3WorkpaperWriterContentError("s3_writer_observed_counts_invalid")


def validate_s3_case_workpaper(workpaper: Mapping[str, Any], *, policy: Mapping[str, Any]) -> None:
    case_key = str(workpaper.get("case_key") or "")
    if case_key not in CASES:
        raise S3WorkpaperWriterContentError("s3_writer_case_invalid")
    case_rule = policy["case_rules"][case_key]
    if workpaper.get("company_name") != case_rule["company_name"] or workpaper.get("ticker") != case_key:
        raise S3WorkpaperWriterContentError("s3_writer_identity_invalid")
    sections = workpaper.get("sections") or []
    if [row.get("lens_id") for row in sections] != list(policy["required_lenses"]):
        raise S3WorkpaperWriterContentError("s3_writer_lens_surface_invalid")
    claim_ids = set(workpaper.get("claim_card_ids") or [])
    if len(claim_ids) != 3 or workpaper.get("workpaper_authority") != "fixture_mixed_engineering_only":
        raise S3WorkpaperWriterContentError("s3_writer_authority_invalid")
    if workpaper.get("display_ready") is not False or workpaper.get("product_candidate") is not False:
        raise S3WorkpaperWriterContentError("s3_writer_fixture_promotion_forbidden")
    forbidden = [str(value).lower() for value in policy["forbidden_generic_fragments"]]
    seen_substantive = 0
    for section in sections:
        answers = section.get("answers") or {}
        if set(answers) != set(policy["required_answer_fields"]):
            raise S3WorkpaperWriterContentError("s3_writer_answer_surface_invalid")
        text = json.dumps(answers, ensure_ascii=False).lower()
        if any(fragment in text for fragment in forbidden):
            raise S3WorkpaperWriterContentError("s3_writer_generic_content_forbidden")
        if section.get("coverage_status") == "bounded_judgment":
            seen_substantive += 1
            if not section.get("claim_card_ids") or set(section["claim_card_ids"]) - claim_ids:
                raise S3WorkpaperWriterContentError("s3_writer_claim_binding_invalid")
            if not section.get("mechanism_atoms") or not answers.get("conclusion") or not answers.get("why"):
                raise S3WorkpaperWriterContentError("s3_writer_substantive_content_missing")
            for fact in section.get("numeric_facts") or []:
                if fact.get("case_key") != case_key or fact.get("rendered") != _render_numeric_fact(fact):
                    raise S3WorkpaperWriterContentError("s3_writer_numeric_rendering_invalid")
        elif section.get("coverage_status") == "explicit_research_gap":
            if section.get("claim_card_ids") or section.get("numeric_facts") or not section.get("planned_cell_ids"):
                raise S3WorkpaperWriterContentError("s3_writer_planned_cell_promotion_invalid")
            if "不作" not in str(answers.get("conclusion") or ""):
                raise S3WorkpaperWriterContentError("s3_writer_gap_conclusion_invalid")
        else:
            raise S3WorkpaperWriterContentError("s3_writer_coverage_status_invalid")
    if seen_substantive < 6:
        raise S3WorkpaperWriterContentError("s3_writer_content_density_invalid")
    packet = workpaper.get("writer_no_source_packet") or {}
    if (
        packet.get("source_access_allowed") is not False
        or packet.get("raw_retrieval_rows") != []
        or set(packet.get("claim_card_ids") or []) != claim_ids
        or packet.get("synthesis_id") != workpaper.get("lead_synthesis_id")
        or packet.get("section_material_ref") != "case_workpaper.sections"
        or packet.get("section_digests") != [canonical_digest(section) for section in sections]
    ):
        raise S3WorkpaperWriterContentError("s3_writer_no_source_packet_invalid")
    digest_body = {key: deepcopy(value) for key, value in workpaper.items() if key != "workpaper_digest"}
    if workpaper.get("workpaper_digest") != canonical_digest(digest_body):
        raise S3WorkpaperWriterContentError("s3_writer_workpaper_digest_invalid")


def _compile_case_workpaper(
    *,
    case_key: str,
    rule: Mapping[str, Any],
    required_lenses: list[str],
    card_map: Mapping[tuple[str, str], Mapping[str, Any]],
    synthesis: Mapping[str, Any],
    planned_map: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    case_cards = [card_map[(case_key, cell)] for cell in CORE_CELLS]
    card_by_id = {str(row["claim_card_id"]): row for row in case_cards}
    sections = []
    for lens_id in required_lenses:
        if lens_id == "executive_thesis":
            sections.append(_compile_executive_section(case_key, rule, case_cards, synthesis))
        elif lens_id == "gaps_and_what_would_change":
            sections.append(_compile_gap_and_wwc_section(case_key, rule, case_cards, synthesis))
        else:
            sections.append(
                _compile_lens_section(
                    case_key=case_key,
                    lens_id=lens_id,
                    lens_rule=rule["lens_rules"][lens_id],
                    card_map=card_map,
                    synthesis=synthesis,
                    planned_map=planned_map,
                )
            )
    workpaper_authority = (
        "all_natural_candidate"
        if all(row["choice_authority"] == "live_natural_exact_once" for row in case_cards)
        else "fixture_mixed_engineering_only"
    )
    body = {
        "case_key": case_key,
        "ticker": case_key,
        "company_name": rule["company_name"],
        "claim_card_ids": [row["claim_card_id"] for row in case_cards],
        "claim_authorities": {row["claim_card_id"]: row["choice_authority"] for row in case_cards},
        "lead_synthesis_id": synthesis["synthesis_id"],
        "workpaper_authority": workpaper_authority,
        "product_candidate": workpaper_authority == "all_natural_candidate",
        "display_ready": workpaper_authority == "all_natural_candidate",
        "sections": sections,
        "writer_no_source_packet": {
            "schema_version": "fin_ia_0_1_3_s3_writer_no_source_packet_v1_0",
            "case_key": case_key,
            "company_name": rule["company_name"],
            "source_access_allowed": False,
            "raw_retrieval_rows": [],
            "claim_card_ids": [row["claim_card_id"] for row in case_cards],
            "synthesis_id": synthesis["synthesis_id"],
            "content_lenses": list(required_lenses),
            "answer_contract": ["conclusion", "why", "opposing_view", "missing_evidence", "what_would_change"],
            "authority": workpaper_authority,
            "section_material_ref": "case_workpaper.sections",
            "section_digests": [canonical_digest(section) for section in sections],
        },
        "content_precheck": {
            "required_lenses": "8/8",
            "answers_conclusion_why_opposing_missing_change": "8/8",
            "core_claims_bound": "3/3",
            "lead_dependency_conflict_gap_bound": True,
            "planned_cells_promoted": 0,
            "generic_placeholder_fragments": 0,
            "raw_source_rows_visible_to_writer": 0,
            "eight_dimension_score": "not_scored_before_natural_final_delivery",
        },
    }
    if workpaper_authority != "all_natural_candidate":
        body["product_candidate"] = False
        body["display_ready"] = False
    with_id = {"workpaper_id": "fin013_s3_workpaper_" + canonical_digest(body)[:24], **body}
    # Validate that every card referenced by a section is a current-case card before sealing.
    if any(set(section["claim_card_ids"]) - set(card_by_id) for section in sections):
        raise S3WorkpaperWriterContentError("s3_writer_cross_case_claim_binding")
    return {**with_id, "workpaper_digest": canonical_digest(with_id)}


def _compile_executive_section(
    case_key: str, rule: Mapping[str, Any], cards: list[Mapping[str, Any]], synthesis: Mapping[str, Any]
) -> dict[str, Any]:
    numerics = _numeric_facts(cards)
    conflict = synthesis["conflicts"][0]
    gaps = synthesis["gaps"]
    return {
        "lens_id": "executive_thesis",
        "coverage_status": "bounded_judgment",
        "authority": _section_authority(cards),
        "claim_card_ids": [row["claim_card_id"] for row in cards],
        "planned_cell_ids": [],
        "mechanism_atoms": [row["mechanism_atom"] for row in cards],
        "numeric_facts": numerics,
        "answers": {
            "conclusion": rule["case_thesis_frame"],
            "why": _why_text(case_key, cards, synthesis),
            "opposing_view": f"最强反方：{conflict['tension']} 处置仍为 {conflict['disposition']}，因为 {conflict['reason']}",
            "missing_evidence": "；".join(f"{row['gap_id']}：{row['impact']}" for row in gaps),
            "what_would_change": _wwc_text(cards),
        },
        "evidence_boundary": _boundaries(cards),
        "lead_links": {
            "dependency": deepcopy(synthesis["dependencies"][0]),
            "conflict": deepcopy(conflict),
            "gap_ids": [row["gap_id"] for row in gaps],
        },
    }


def _compile_gap_and_wwc_section(
    case_key: str, rule: Mapping[str, Any], cards: list[Mapping[str, Any]], synthesis: Mapping[str, Any]
) -> dict[str, Any]:
    gaps = synthesis["gaps"]
    return {
        "lens_id": "gaps_and_what_would_change",
        "coverage_status": "bounded_judgment",
        "authority": _section_authority(cards),
        "claim_card_ids": [row["claim_card_id"] for row in cards],
        "planned_cell_ids": [],
        "mechanism_atoms": [row["mechanism_atom"] for row in cards],
        "numeric_facts": [],
        "answers": {
            "conclusion": f"{case_key} 当前判断必须保持有条件：未关闭的高影响缺口不能被写作层补成事实。",
            "why": "；".join(f"{row['gap_id']} 由 {row['owner']} 负责，影响为 {row['impact']}" for row in gaps),
            "opposing_view": f"{synthesis['conflicts'][0]['tension']}；当前处置为 {synthesis['conflicts'][0]['disposition']}。",
            "missing_evidence": "；".join(f"{row['next_evidence_route']}；停止条件：{row['stop_condition']}" for row in gaps),
            "what_would_change": _wwc_text(cards),
        },
        "evidence_boundary": _boundaries(cards),
        "lead_links": {
            "dependency": deepcopy(synthesis["dependencies"][0]),
            "conflict": deepcopy(synthesis["conflicts"][0]),
            "gap_ids": [row["gap_id"] for row in gaps],
        },
    }


def _compile_lens_section(
    *,
    case_key: str,
    lens_id: str,
    lens_rule: Mapping[str, Any],
    card_map: Mapping[tuple[str, str], Mapping[str, Any]],
    synthesis: Mapping[str, Any],
    planned_map: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, Any]:
    cards = [card_map[(case_key, str(cell))] for cell in lens_rule["source_cells"]]
    planned = [planned_map[(case_key, str(cell))] for cell in lens_rule["planned_cells"]]
    if not cards:
        questions = [row["decision_question"] for row in planned]
        return {
            "lens_id": lens_id,
            "coverage_status": "explicit_research_gap",
            "authority": "planned_no_claim",
            "claim_card_ids": [],
            "planned_cell_ids": [row["cell_key"] for row in planned],
            "mechanism_atoms": [],
            "numeric_facts": [],
            "answers": {
                "conclusion": f"{case_key} 在该维度当前不作实质结论：{lens_rule['decision_frame']}",
                "why": "现有核心 Claim 没有覆盖这些问题，写作层不得用行业常识或通用措辞补齐。",
                "opposing_view": "在形成正面或负面判断前，必须先取得本案、当前、可追溯的证据。",
                "missing_evidence": "；".join(questions),
                "what_would_change": "完成上述 planned Cell 的 Evidence Gate、Claim 选择和 Lead 裁决后，才允许改变该维度状态。",
            },
            "evidence_boundary": [],
            "lead_links": {"dependency": None, "conflict": None, "gap_ids": []},
        }
    claim_ids = {row["claim_card_id"] for row in cards}
    related_gaps = [row for row in synthesis["gaps"] if row["source_claim_id"] in claim_ids]
    dependency = synthesis["dependencies"][0]
    conflict = synthesis["conflicts"][0]
    related_conflict = bool(set(conflict["claim_ids"]) & claim_ids)
    return {
        "lens_id": lens_id,
        "coverage_status": "bounded_judgment",
        "authority": _section_authority(cards),
        "claim_card_ids": [row["claim_card_id"] for row in cards],
        "planned_cell_ids": [row["cell_key"] for row in planned],
        "mechanism_atoms": [row["mechanism_atom"] for row in cards],
        "numeric_facts": _numeric_facts(cards),
        "answers": {
            "conclusion": lens_rule["decision_frame"],
            "why": _why_text(case_key, cards, synthesis),
            "opposing_view": (
                f"{conflict['tension']}；当前处置为 {conflict['disposition']}，原因是 {conflict['reason']}"
                if related_conflict
                else "当前证据边界不允许把公司或分部总量直接外推为该维度的完整因果结论。"
            ),
            "missing_evidence": (
                "；".join(f"{row['gap_id']}：{row['impact']}；下一路线：{row['next_evidence_route']}" for row in related_gaps)
                if related_gaps
                else "；".join(row["decision_question"] for row in planned)
            ),
            "what_would_change": _wwc_text(cards),
        },
        "evidence_boundary": _boundaries(cards),
        "lead_links": {
            "dependency": deepcopy(dependency) if set((dependency["from_claim_id"], dependency["to_claim_id"])) & claim_ids else None,
            "conflict": deepcopy(conflict) if related_conflict else None,
            "gap_ids": [row["gap_id"] for row in related_gaps],
        },
    }


def _section_authority(cards: list[Mapping[str, Any]]) -> str:
    return (
        "all_natural"
        if cards and all(row["choice_authority"] == "live_natural_exact_once" for row in cards)
        else "fixture_mixed_engineering_only"
    )


def _numeric_facts(cards: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for card in cards:
        for fact in card.get("numeric_facts") or []:
            key = (fact["candidate_id"], fact["metric_family"], fact["normalized_value"], fact["unit"])
            if key in seen:
                continue
            seen.add(key)
            row = deepcopy(fact)
            row["rendered"] = _render_numeric_fact(row)
            rows.append(row)
    return rows


def _render_numeric_fact(fact: Mapping[str, Any]) -> str:
    value = Decimal(str(fact["normalized_value"]))
    if value != value.to_integral_value():
        rendered = format(value, "f")
    else:
        rendered = f"{int(value):,}"
    return f"{fact['metric_family']}={fact['unit']} {rendered}（披露日 {fact['published_at']}；口径边界：{fact['claim_boundary']}）"


def _boundaries(cards: list[Mapping[str, Any]]) -> list[str]:
    rows = []
    for card in cards:
        for value in card.get("evidence_boundary") or []:
            if value not in rows:
                rows.append(str(value))
        for gap in card.get("typed_gaps") or []:
            value = str(gap.get("cannot_infer") or "")
            if value and value not in rows:
                rows.append(value)
    return rows


def _why_text(case_key: str, cards: list[Mapping[str, Any]], synthesis: Mapping[str, Any]) -> str:
    mechanisms = "；".join(str(row["mechanism_atom"]) for row in cards)
    numerics = _numeric_facts(cards)
    numeric_text = "；".join(row["rendered"] for row in numerics)
    dependency = synthesis["dependencies"][0]
    parts = [f"{case_key} 的机制链：{mechanisms}", f"跨判断影响：{dependency['decision_effect']}"]
    if numeric_text:
        parts.append(f"本地精确数值：{numeric_text}")
    return "；".join(parts)


def _wwc_text(cards: list[Mapping[str, Any]]) -> str:
    rows = []
    for card in cards:
        for item in card.get("what_would_change") or []:
            rows.append(
                f"{item['metric_or_event']} 向 {item['direction']} 变化，在 {item['time_window']} 达到“{item['threshold']}”；下一证据路线：{item['next_evidence_route']}"
            )
    return "；".join(rows)


def _record_digest_ok(record: Mapping[str, Any]) -> bool:
    return record.get("record_digest") == canonical_digest(
        {key: deepcopy(value) for key, value in record.items() if key != "record_digest"}
    )
