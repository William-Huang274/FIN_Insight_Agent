from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_representative_node_program import (
    compile_representative_node_program,
)


S2_01_DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_01_"
    "research_question_method_contract_translation_v1_0.json"
)
POLICY = ROOT / "configs" / "runtime" / (
    "fin_ia_0_1_3_repair_closeout_s2_"
    "representative_node_and_natural_canary_policy_v1_0.json"
)
DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_02_"
    "representative_node_context_precedence_and_canary_entry_v1_0.json"
)
ACTIVE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_02_active_test_suite_successor_v1_0.json"
)
ROOT_CAUSE_LEDGER = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
CAPABILITY_LEDGER = ROOT / "docs" / "project_os" / "capability_status_ledger.jsonl"
METHOD_REGISTRY = ROOT / "docs" / "project_os" / "financial_research_method_registry.jsonl"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(
    path: Path,
    records: list[dict[str, Any]],
    *,
    key_fields: tuple[str, ...],
) -> None:
    existing = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    replacements = {
        tuple(str(record.get(field) or "") for field in key_fields): record
        for record in records
    }
    output: list[dict[str, Any]] = []
    consumed: set[tuple[str, ...]] = set()
    for row in existing:
        key = tuple(str(row.get(field) or "") for field in key_fields)
        if key in replacements:
            output.append(replacements[key])
            consumed.add(key)
        else:
            output.append(row)
    output.extend(record for key, record in replacements.items() if key not in consumed)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
            + "\n"
            for row in output
        ),
        encoding="utf-8",
    )


def _project_os_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    root_causes = [
        {
            "schema_version": "fin_insight_root_cause_issue_ledger_v0_1",
            "recorded_at": "2026-08-06T23:59:10+08:00",
            "sequence_after_projection": "v2_93",
            "status": "closed_by_FIN_0_1_3_013_S2_02_hermetic_low_level_builder_and_explicit_research_lead_autoload_policy",
            "severity": "closed",
            "full_chain_blocker": False,
            "owned_by_project": True,
            "external_boundary": False,
            "model_or_provider_fault_established": False,
            "runtime_L1_failure_established": False,
            "product_L4_failure_established": False,
            "blocking_run_scopes": [],
            "allowed_run_scopes": [
                "FIN_0_1_3_S2_02_three_family_natural_output_canary_admission",
                "zero_call_representative_node_regression",
            ],
            "issue_id": "RC-P36-138-fin-0-1-3-specialist-explicit-evidence-vs-repository-autoload-precedence-and-test-isolation",
            "state_detail": "Low-level Agent data-view and Specialist request builders now default to hermetic no-autoload when the caller supplies no policy. Production LangGraph still receives an explicit Research Lead enable or disable decision.",
            "layer": "FIN_0_1_3_013_S2_02_representative_node_context_injection_precedence_and_hermetic_fixture",
            "root_cause": "Returning None from multi_agent_runtime._product_intelligence_autoload_arg delegated to the repository loader default true behavior and made working-directory data an undeclared input.",
            "required_fix": "complete; retain explicit Research Lead autoload ownership, working-directory invariance, explicit-autoload positive coverage and request digest binding",
            "evidence_refs": [
                "src/sec_agent/multi_agent_runtime.py",
                "src/sec_agent/s2_representative_node_program.py",
                "tests/test_multi_agent_specialist_llm.py",
                "tests/contract/test_fin_0_1_3_repair_closeout_s2_02_representative_node_and_context_precedence.py",
                "configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json",
            ],
            "verification": {
                "legacy_specialist_before": "60 passed / 3 failed",
                "legacy_specialist_after": "63 passed",
                "active_suite": "161 passed / 1 historical event-time assertion deselected",
                "working_directory_invariance": True,
                "production_explicit_autoload_available": True,
                "model_provider_network_calls": [0, 0, 0],
            },
            "known_boundary": "Closure proves context precedence and isolation, not natural model output, context economy, final research quality, product acceptance or release.",
        },
        {
            "schema_version": "fin_insight_root_cause_issue_ledger_v0_1",
            "recorded_at": "2026-08-06T23:59:11+08:00",
            "sequence_after_projection": "v2_93",
            "status": "open_S2_02_runtime_node_consumption_proven_natural_canary_and_S2_03_S3_quality_pending",
            "severity": "critical",
            "full_chain_blocker": True,
            "owned_by_project": True,
            "external_boundary": False,
            "model_or_provider_fault_established": False,
            "runtime_L1_failure_established": False,
            "product_L4_failure_established": True,
            "blocking_run_scopes": [
                "claiming_FIN_0_1_3_research_content_pass_from_local_representative_synthesis",
                "claiming_RG3_or_release_without_per_case_content_acceptance",
            ],
            "allowed_run_scopes": [
                "FIN_0_1_3_S2_02_three_family_natural_output_canary",
                "FIN_0_1_3_S2_03_context_yield_capacity",
                "FIN_0_1_3_S3_dynamic_research_composition_quality",
            ],
            "issue_id": "RC-P36-131-fin-0-1-2-t08-prd-to-runtime-decision-surface-and-research-semantic-depth-gap",
            "state_detail": "All nine company-specific alias-only requests now enter representative Specialist nodes, materialize nine local Claims and feed three local Lead syntheses with exact S1/S2 lineage. Natural DeepSeek behavior and final content quality remain unproven.",
            "layer": "FIN_0_1_3_S2_natural_node_capability_and_S3_dynamic_research_composition_quality",
            "root_cause": "Partially repaired through contract translation and deterministic runtime consumption; paid natural behavior, context economy, dynamic planning and final content acceptance remain open.",
            "required_fix": "Run only the preregistered three-family canary after fresh admission, close S2-03 context yield, then implement S3 dynamic DecisionSurface and eight-dimension quality acceptance.",
            "evidence_refs": [
                "src/sec_agent/s2_representative_node_program.py",
                "configs/runtime/fin_ia_0_1_3_repair_closeout_s2_representative_node_and_natural_canary_policy_v1_0.json",
                "configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json",
            ],
            "verification": {
                "representative_specialist_nodes": 9,
                "materialized_claims": 9,
                "representative_lead_nodes": 3,
                "runtime_injected_into_representative_node": True,
                "node_level_consumed": True,
                "natural_model_outputs": 0,
                "eight_dimension_case_passes": 0,
            },
            "known_boundary": "Local deterministic Claim and Lead materialization cannot substitute for natural model capability, final report depth or human acceptance.",
        },
    ]
    capabilities = [
        {
            "schema_version": "fin_insight_capability_status_ledger_v0_1",
            "recorded_at": "2026-08-06T23:59:12+08:00",
            "sequence_after_projection": "v2_93",
            "capability_id": "fin_0_1_3_013_S2_02_context_precedence_and_representative_node_consumption",
            "status": "S2_02_zero_call_node_consumption_pass_natural_canary_entry_ready",
            "scope": "hermetic_current_pack_precedence_nine_specialist_claim_nodes_three_case_lead_synthesis_and_preregistered_canary",
            "authority": {"user_instruction": "继续", "model_provider_network_source_business_runs": [0, 0, 0, 0, 0]},
            "product_capability_delta": "The representative Agent path now consumes the exact current governed request rather than silently changing with repository-local Product Intelligence data.",
            "research_quality_delta": "Company-specific mechanisms, Evidence, typed gaps and observable what-would-change conditions survive node consumption with exact lineage.",
            "verification": {
                "RC_P36_138": "closed",
                "legacy_specialist": "63 passed",
                "active_suite": "161 passed / 1 historical event-time assertion deselected",
                "representative_topology": {"specialist_nodes": 9, "claims": 9, "lead_syntheses": 3},
            },
            "stage_acceptance": {
                "S0": "pass_closed",
                "S1": "pass_closed",
                "S2_01": "engineering_pass",
                "S2_02_zero_call": "pass",
                "S2_02_natural_canary": "entry_ready_not_run",
                "S2_03_to_S5": "not_started",
                "product_acceptance": False,
                "release": False,
            },
            "issues": {"RC_P36_138": "closed", "RC_P36_131": "open_natural_canary_S2_03_S3", "RC_P36_132": "open_S4_S5"},
            "source_refs": [
                "src/sec_agent/multi_agent_runtime.py",
                "src/sec_agent/s2_representative_node_program.py",
                "configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json",
                "tests/contract/test_fin_0_1_3_repair_closeout_s2_02_representative_node_and_context_precedence.py",
            ],
            "current_next": "FIN-0.1.3-013-S2-02-THREE-FAMILY-NATURAL-OUTPUT-CANARY-FRESH-ADMISSION-AUTHORITY-DECISION",
            "known_boundary": "Representative deterministic consumption is not natural DeepSeek qualification, final research-content quality, Human acceptance or release.",
        }
    ]
    methods = [
        {
            "schema_version": "fin_insight_financial_research_method_registry_v0_1",
            "updated_at": "2026-08-06",
            "method_id": "fin_0_1_3_company_specific_research_question_and_bounded_judgment_choice_method",
            "research_domain": "three_case_evidence_to_company_specific_mechanism_and_what_would_change_translation",
            "source_basis": [
                "configs/runtime/fin_ia_0_1_3_repair_closeout_s2_research_question_method_contract_policy_v1_0.json",
                "src/sec_agent/s2_representative_node_program.py",
                "configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json",
            ],
            "summary": "The company-specific alias-only method now enters representative Specialist nodes, resolves governed selections into local Claims and feeds bounded case-level Lead synthesis without repository-environment drift.",
            "required_packs": ["S1CurrentGovernedRetrievalPack", "RepresentativeResearchQuestionMethodContract", "HermeticContextInjectionContract", "RepresentativeSpecialistClaimNode", "RepresentativeLeadSynthesis"],
            "agent_implication": "A representative Specialist selects only local aliases/enums; local runtime resolves mechanism, Evidence, gap, WWC, identity and lineage. Lead receives only bounded Claims.",
            "runtime_consumer_contract_ref": "fin_0_1_3.S2.representative_evidence_claim_lead_node:v1",
            "status": "runtime_injected_node_level_consumed_natural_canary_pending",
            "verification": {"specialist_nodes": 9, "materialized_claims": 9, "lead_syntheses": 3, "model_calls": 0},
            "known_boundary": "Node-level deterministic consumption does not establish natural-output quality, context economy, S3 synthesis or product acceptance.",
        },
        {
            "schema_version": "fin_insight_financial_research_method_registry_v0_1",
            "updated_at": "2026-08-06",
            "method_id": "fin_0_1_3_hermetic_current_pack_and_explicit_production_autoload_method",
            "research_domain": "agent_context_precedence_reproducibility_and_product_intelligence_injection",
            "source_basis": ["src/sec_agent/multi_agent_runtime.py", "src/sec_agent/product_intelligence_runtime.py", "tests/test_multi_agent_specialist_llm.py"],
            "summary": "Low-level Agent view construction is hermetic unless the production Research Lead or operator explicitly enables repository Product Intelligence autoload.",
            "required_packs": ["ExplicitCurrentGovernedPack", "ResearchLeadAutoloadDecision", "AgentDataViewDigest", "HermeticWorkingDirectoryFixture"],
            "agent_implication": "The model-visible evidence surface may not acquire undeclared repository rows; any production merge requires an explicit Research Lead decision.",
            "runtime_consumer_contract_ref": "fin_0_1_3.S2.representative_evidence_claim_lead_node:v1",
            "status": "runtime_injected_node_level_proven",
            "verification": {"working_directory_invariant": True, "explicit_autoload_positive_path": True, "RC_P36_138": "closed", "model_calls": 0},
            "known_boundary": "This method controls context provenance, not evidence ranking or model reasoning quality.",
        },
    ]
    return root_causes, capabilities, methods


def main() -> int:
    s2_decision = _load(S2_01_DECISION)
    policy = _load(POLICY)
    program = compile_representative_node_program(s2_decision=s2_decision)
    preregistered = policy["natural_canary"]
    request_by_id = {
        row["request_id"]: row
        for row in s2_decision["research_question_method_program"][
            "representative_requests"
        ]
    }
    canary_requests = [
        request_by_id[row["request_id"]]
        for row in preregistered["selected_requests"]
    ]
    canary_chars = sum(
        len(
            json.dumps(
                row["model_visible_request"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        for row in canary_requests
    )
    decision_body = {
        "schema_version": (
            "fin_ia_0_1_3_repair_closeout_s2_02_"
            "representative_node_context_precedence_and_canary_entry_v1_0"
        ),
        "task_id": "FIN-0.1.3-013-S2-02",
        "status": "S2_02_zero_call_node_consumption_pass_natural_canary_entry_ready",
        "s2_01_decision_ref": str(S2_01_DECISION.relative_to(ROOT)).replace("\\", "/"),
        "s2_01_decision_sha256": _sha256(S2_01_DECISION),
        "policy_ref": str(POLICY.relative_to(ROOT)).replace("\\", "/"),
        "policy_sha256": _sha256(POLICY),
        "representative_node_program": program,
        "root_cause_corrections": {
            "RC-P36-138": {
                "status": "closed_zero_call",
                "earliest_fault": (
                    "low-level Specialist data-view builders inherited repository "
                    "Product Intelligence autoload when no explicit policy was present"
                ),
                "repair": (
                    "direct builders default to hermetic no-autoload; production "
                    "Research Lead retains explicit enable/disable ownership"
                ),
                "legacy_specialist_regression": "63 passed",
            }
        },
        "natural_canary_entry": {
            "status": "eligible_for_fresh_admission_not_issued_not_run",
            "selected_request_ids": [row["request_id"] for row in canary_requests],
            "selected_families": [row["program_cell_id"] for row in canary_requests],
            "aggregate_model_visible_characters": canary_chars,
            "maximum_provider_calls": preregistered["budgets"][
                "maximum_provider_calls"
            ],
            "retry_count": 0,
            "fallback_count": 0,
            "full_chain_calls": 0,
            "rubric": preregistered["rubric"],
            "hard_fail_conditions": preregistered["hard_fail_conditions"],
            "stop_rule": preregistered["stop_rule"],
        },
        "acceptance": {
            "explicit_pack_precedence": "pass",
            "working_directory_invariance": "pass",
            "production_autoload_explicit_path": "pass",
            "representative_specialist_nodes": "9/9 consumed",
            "representative_claims": "9/9 materialized",
            "representative_leads": "3/3 synthesized",
            "cross_case_and_free_text_mutations": "fail_closed",
            "natural_model_output": "not_run",
            "eight_dimension_product_content_quality": "not_proven",
        },
        "known_boundary": (
            "This decision closes RC-P36-138 and proves deterministic representative "
            "node consumption. It does not prove DeepSeek natural contract adherence, "
            "S2-03 context economy, S3 dynamic DecisionSurface, final research-content "
            "quality, product acceptance or release."
        ),
        "model_provider_network_source_business_runs": [0, 0, 0, 0, 0],
        "current_next": (
            "FIN-0.1.3-013-S2-02-THREE-FAMILY-NATURAL-OUTPUT-CANARY-"
            "FRESH-ADMISSION-AUTHORITY-DECISION"
        ),
    }
    decision = {**decision_body, "record_digest": canonical_digest(decision_body)}
    _write(DECISION, decision)

    previous = _load(
        ROOT
        / "configs"
        / "releases"
        / "fin_ia_0_1_3_repair_closeout_s2_01_active_test_suite_successor_v1_0.json"
    )
    selected = list(previous["selected_test_files"])
    selected.extend(
        [
            "tests/test_multi_agent_specialist_llm.py",
            (
                "tests/contract/test_fin_0_1_3_repair_closeout_s2_02_"
                "representative_node_and_context_precedence.py"
            ),
        ]
    )
    active_body = {
        "schema_version": (
            "fin_ia_0_1_3_repair_closeout_s2_02_"
            "active_test_suite_successor_v1_0"
        ),
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S2-02-ACTIVE-SUITE-R10",
        "status": "current_S2_02_zero_call_pass_natural_canary_entry_ready",
        "decision_ref": str(DECISION.relative_to(ROOT)).replace("\\", "/"),
        "decision_sha256": _sha256(DECISION),
        "selected_test_files": selected,
        "historical_event_time_deselections": previous[
            "historical_event_time_deselections"
        ],
        "observed_result": "161 passed / 1 historical event-time assertion deselected",
        "stage_boundary": {
            "S1": "pass_closed",
            "S2_01": "engineering_pass",
            "S2_02_zero_call": "pass",
            "S2_02_natural_canary": "not_run",
            "S2_03_to_S5": "not_started",
            "model_or_full_chain_authorized": False,
            "release": False,
        },
    }
    active = {**active_body, "suite_digest": canonical_digest(active_body)}
    _write(ACTIVE, active)
    root_causes, capabilities, methods = _project_os_records()
    _upsert_jsonl(
        ROOT_CAUSE_LEDGER,
        root_causes,
        key_fields=("issue_id", "sequence_after_projection"),
    )
    _upsert_jsonl(
        CAPABILITY_LEDGER,
        capabilities,
        key_fields=("capability_id",),
    )
    _upsert_jsonl(
        METHOD_REGISTRY,
        methods,
        key_fields=("method_id",),
    )
    print(decision["record_digest"])
    print(active["suite_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
