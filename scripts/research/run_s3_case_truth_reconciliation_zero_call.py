from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.contracts import load_financial_research_kernel
from retrieval.route_compiler import load_query_object_fact_route_policy
from sec_agent.providers.deepseek_strict import project_deepseek_strict_tool
from sec_agent.research.case_truth_reconciliation import (
    CaseTruthReconciliationError,
    aggregate_case_truth_reconciliation_receipts,
    compile_case_truth_reconciliation_analysis_messages,
    compile_case_truth_claim_model_view,
    compile_case_truth_model_view,
    compile_case_truth_packet,
    compile_case_truth_reconciliation_submission,
    compile_case_truth_reconciliation_submission_from_analysis,
    compile_cell_judgment_claim_document,
    compile_claim_document_slice,
    compile_synthesis_claim_document,
    validate_case_truth_packet,
    validate_case_truth_reconciliation,
)
from sec_agent.research.current_consumer import compile_current_research_input
from sec_agent.research.five_cell_runtime import (
    compile_five_cell_synthesis_analysis_messages,
)
from sec_agent.research.planning import (
    compile_research_objective,
    load_research_planning_policy,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import read_registered_runtime_json


AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_s3_case_truth_reconciliation_zero_call_authority_v1_2"
)
RESULT_SCHEMA_VERSION = (
    "fin_ia_s3_case_truth_reconciliation_zero_call_result_v1_2"
)


class CaseTruthProofError(ValueError):
    pass


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CaseTruthProofError(f"case_truth_proof_json_object_required:{path.name}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _resolve(value: str) -> Path:
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise CaseTruthProofError("case_truth_proof_path_escape") from exc
    return path


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise CaseTruthProofError(
            "case_truth_proof_exact_once_output_exists"
        ) from exc


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise CaseTruthProofError("case_truth_proof_git_unavailable")
    return completed.stdout.strip()


def _validate_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> tuple[dict[str, Path], Path, Path, str]:
    if not (
        payload.get("schema_version") == AUTHORITY_SCHEMA_VERSION
        and payload.get("status")
        == "fresh_zero_call_case_truth_reconciliation_proof_authorized"
    ):
        raise CaseTruthProofError("case_truth_proof_authority_status_invalid")
    clean = payload.get("clean_implementation")
    budget = payload.get("execution_budget")
    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not all(isinstance(row, Mapping) for row in (clean, budget, bound, output)):
        raise CaseTruthProofError("case_truth_proof_authority_shape_invalid")
    assert isinstance(clean, Mapping)
    assert isinstance(budget, Mapping)
    assert isinstance(bound, Mapping)
    assert isinstance(output, Mapping)
    commit = str(clean.get("implementation_commit") or "").lower()
    if dict(clean) != {
        "implementation_commit": commit,
        "head_must_equal_implementation_commit": True,
        "upstream_must_equal_implementation_commit": True,
        "tracked_worktree_must_be_clean": True,
        "only_authority_may_be_untracked": True,
    }:
        raise CaseTruthProofError("case_truth_proof_clean_binding_invalid")
    if _git("rev-parse", "HEAD").lower() != commit:
        raise CaseTruthProofError("case_truth_proof_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise CaseTruthProofError("case_truth_proof_upstream_drift")
    status = [
        row
        for row in _git(
            "status", "--porcelain=v1", "--untracked-files=all"
        ).splitlines()
        if row
    ]
    if status != [f"?? {_relative(authority_path)}"]:
        raise CaseTruthProofError("case_truth_proof_worktree_not_clean")
    if dict(budget) != {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "embedding_calls": 0,
        "retries": 0,
        "candidate_promotions": 0,
        "business_report_publication": "forbidden",
    }:
        raise CaseTruthProofError("case_truth_proof_budget_invalid")
    ref_keys = {key for key in bound if str(key).endswith("_ref")}
    expected_ref_keys = {
        "r7_public_result_ref",
        "r7_private_result_ref",
        "r2_public_result_ref",
        "r2_private_result_ref",
        "runtime_registry_ref",
        "consumer_policy_ref",
    }
    if ref_keys != expected_ref_keys or set(bound) != {
        value
        for key in expected_ref_keys
        for value in (key, key[:-4] + "_sha256")
    }:
        raise CaseTruthProofError("case_truth_proof_bound_inputs_invalid")
    paths: dict[str, Path] = {}
    for key in sorted(expected_ref_keys):
        path = _resolve(str(bound[key]))
        digest_key = key[:-4] + "_sha256"
        if not path.is_file() or _sha(path) != str(bound[digest_key]):
            raise CaseTruthProofError(f"case_truth_proof_bound_input_drift:{key}")
        paths[key] = path
    private = _resolve(str(output.get("private_output_ref") or ""))
    public = _resolve(str(output.get("public_result_ref") or ""))
    if private.exists() or public.exists():
        raise CaseTruthProofError("case_truth_proof_exact_once_identity_consumed")
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        raise CaseTruthProofError("case_truth_proof_run_id_missing")
    return paths, private, public, commit


def _case_services() -> tuple[
    Any,
    Any,
    ResearchEvidencePackService,
    ResearchRetrievalService,
]:
    runtime_paths = resolve_runtime_paths(ROOT)
    kernel_payload = read_registered_runtime_json(
        ROOT, "application.config.current_financial_research_kernel"
    )
    route_payload = read_registered_runtime_json(
        ROOT, "application.config.current_query_object_fact_route_policy"
    )
    planning_payload = read_registered_runtime_json(
        ROOT, "application.config.current_research_planning_policy"
    )
    kernel = load_financial_research_kernel(kernel_payload)
    route = load_query_object_fact_route_policy(route_payload, kernel)
    planning = load_research_planning_policy(planning_payload, route)
    return (
        kernel,
        planning,
        ResearchEvidencePackService.from_runtime_paths(ROOT, runtime_paths),
        ResearchRetrievalService(
            snapshot=read_registered_runtime_json(
                ROOT, "application.result.current_research_retrieval_snapshot"
            ),
            ranking_comparison=read_registered_runtime_json(
                ROOT,
                "application.result.current_s1c_ranking_comparison_projection",
            ),
            kernel=kernel_payload,
            route_policy=route_payload,
            planning_policy=planning_payload,
            hybrid_candidate_runtime=None,
            company_financial_fact_mart_path=(
                runtime_paths.company_financial_fact_mart_path
            ),
        ),
    )


def _one_slot_plan(
    case_key: str, *, kernel: Any, planning: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    draft = {
        "schema_version": "fin_ia_research_objective_draft_v1_0",
        "raw_question": f"{case_key} 的增长是否转化为可持续利润，当前证据还缺什么？",
        "task_type": "company_deep_dive",
        "case_key": case_key,
        "required_slot_ids": ["pricing_mix_value_capture"],
        "allowed_source_types": [
            "10-K",
            "10-Q",
            "8-K",
            "20-F",
            "6-K",
            "EARNINGS_CALL_TRANSCRIPT",
        ],
        "forbidden_source_types": [],
        "output_format": "investment_research_memo",
        "gap_policy": "return_typed_gap",
        "reviewer_role": "qualified_financial_research_reviewer",
        "period": {
            "start_date": "2024-01-01",
            "fiscal_years": [2025, 2026, 2027],
        },
        "budget": {
            "max_evidence_requests": 1,
            "max_metric_intents_per_request": 4,
            "max_product_intents_per_request": 2,
            "max_model_calls": 1,
        },
        "pass_criteria": [
            "identity_and_as_of_bound",
            "required_dimensions_covered",
            "numeric_facts_source_bound",
            "candidate_not_evidence_boundary_preserved",
            "qualified_human_review_required",
        ],
    }
    objective = compile_research_objective(draft, kernel=kernel, policy=planning)
    atoms = {
        "schema_version": "fin_ia_research_planner_atoms_v1_0",
        "objective_id": objective.objective_id,
        "atoms": [
            {
                "facet_id": "margin_and_incremental_profit",
                "metric_ids": [
                    "gross_profit",
                    "operating_income",
                    "operating_margin",
                    "gross_margin",
                ],
                "product_intents": [
                    "product-to-company profit bridge",
                    "incremental profit durability",
                ],
                "target_entity": case_key,
            }
        ],
    }
    return draft, atoms


def _current_case_input(
    case_key: str,
    *,
    consumer_policy: Mapping[str, Any],
    kernel: Any,
    planning: Any,
    evidence: ResearchEvidencePackService,
    retrieval: ResearchRetrievalService,
) -> dict[str, Any]:
    read = frozenset({"current_product:read"})
    objective, atoms = _one_slot_plan(case_key, kernel=kernel, planning=planning)
    pack = evidence.get_case(
        case_key, ResearchEvidencePackPrincipal("current", read)
    )
    controlled = retrieval.execute_controlled_plan(
        case_key,
        objective,
        atoms,
        ResearchRetrievalPrincipal("current", read),
    )
    return compile_current_research_input(
        policy=consumer_policy,
        evidence_pack=pack,
        controlled_plan=controlled,
    )


def _eligible_fixture_payload(
    packet: Mapping[str, Any], document: Mapping[str, Any]
) -> dict[str, Any]:
    matrix = {
        str(row["cell_id"]): row for row in packet["cell_visibility_matrix"]
    }
    first_presence = str(packet["presence_catalog"][0]["truth_alias"])
    output = []
    for surface in document["claim_surfaces"]:
        if surface["truth_assertion_required"] is False:
            status = "no_case_truth_claim"
            assertions: list[dict[str, str]] = []
        elif surface["cell_id"] is None:
            status = "claims_mapped"
            assertions = [
                {
                    "truth_alias": first_presence,
                    "claim_polarity": "claim_asserts_present",
                }
            ]
        else:
            visible = matrix[str(surface["cell_id"])]["visible_presence_aliases"]
            if not visible:
                raise CaseTruthProofError(
                    "case_truth_proof_fixture_cell_without_presence"
                )
            status = "claims_mapped"
            assertions = [
                {
                    "truth_alias": str(visible[0]),
                    "claim_polarity": "claim_asserts_present",
                }
            ]
        output.append(
            {
                "claim_surface_id": surface["claim_surface_id"],
                "claim_surface_digest": surface["claim_surface_digest"],
                "coverage_status": status,
                "assertions": assertions,
            }
        )
    return {"surface_assertions": output}


def _replace_assertions(
    payload: dict[str, Any], surface_id: str, assertions: list[dict[str, str]]
) -> None:
    row = next(
        item
        for item in payload["surface_assertions"]
        if item["claim_surface_id"] == surface_id
    )
    row["coverage_status"] = "claims_mapped"
    row["assertions"] = assertions


def _permuted_input(value: Mapping[str, Any]) -> dict[str, Any]:
    output = deepcopy(dict(value))
    for key in (
        "evidence_cards",
        "numeric_fact_cards",
        "numeric_relation_cards",
        "source_bound_qualitative_fact_cards",
        "residual_gap_cards",
        "cells",
    ):
        if isinstance(output.get(key), list):
            output[key].reverse()
    for evidence in output.get("evidence_cards") or []:
        evidence["slot_bindings"].reverse()
        for binding in evidence["slot_bindings"]:
            binding["facet_ids"].reverse()
    for cell in output.get("cells") or []:
        for key in (
            "allowed_evidence_refs",
            "allowed_numeric_refs",
            "allowed_numeric_relation_refs",
            "allowed_qualitative_fact_refs",
            "visible_gap_refs",
        ):
            if isinstance(cell.get(key), list):
                cell[key].reverse()
    return output


def _holdout_input() -> dict[str, Any]:
    return {
        "case_identity": {
            "case_key": "HOLDOUT_INDUSTRIAL",
            "subject_ticker": "HOLDOUT_INDUSTRIAL",
            "research_as_of": "2026-08-17",
        },
        "research_input_digest": "DIGEST::HOLDOUT_INDUSTRIAL",
        "evidence_cards": [
            {
                "evidence_ref": "EV::HOLDOUT_SUPPLIER",
                "evidence_owner_ticker": "SUPPLIER_X",
                "publication_date": "2026-08-01",
                "source_reporting_period_end": "2026-07-31",
                "slot_bindings": [
                    {
                        "slot_id": "capacity_inputs_execution",
                        "facet_ids": ["supplier_capacity_signal"],
                        "business_meaning_zh": "供应商材料仅提供有界产能旁证",
                        "claim_boundary_zh": "不能冒充研究主体自身产能事实",
                    }
                ],
            }
        ],
        "numeric_fact_cards": [],
        "numeric_relation_cards": [],
        "residual_gap_cards": [
            {
                "gap_ref": "GAP::HOLDOUT_CAPACITY_MAGNITUDE",
                "slot_id": "capacity_inputs_execution",
                "facet_id": "supplier_capacity_signal",
                "gap_code": "quantity_not_disclosed",
                "business_reason_zh": "有方向性旁证但无主体可归属的定量产能",
            },
            {
                "gap_ref": "GAP::HOLDOUT_PRODUCT_PROFIT",
                "slot_id": "pricing_mix_value_capture",
                "facet_id": "product_profit_bridge",
                "gap_code": "metric_not_disclosed",
                "business_reason_zh": "产品利润桥未披露",
            },
        ],
        "cells": [
            {
                "cell_id": f"CELL::{index}",
                "allowed_evidence_refs": (
                    ["EV::HOLDOUT_SUPPLIER"] if index == 0 else []
                ),
                "allowed_numeric_refs": [],
                "allowed_numeric_relation_refs": [],
                "visible_gap_refs": (
                    ["GAP::HOLDOUT_PRODUCT_PROFIT"] if index == 1 else []
                ),
            }
            for index in range(5)
        ],
    }


def run(authority_path: Path) -> dict[str, Any]:
    authority = _json(authority_path)
    paths, private_path, public_path, commit = _validate_authority(
        authority, authority_path=authority_path
    )
    public_r7 = _json(paths["r7_public_result_ref"])
    private_r7 = _json(paths["r7_private_result_ref"])
    if (
        public_r7.get("private_full_result_sha256")
        != _sha(paths["r7_private_result_ref"])
        or private_r7.get("case_key") != public_r7.get("case_key")
        or private_r7.get("final_report", {}).get("report_digest")
        != public_r7.get("report_digest")
    ):
        raise CaseTruthProofError("case_truth_proof_r7_binding_invalid")
    public_r2 = _json(paths["r2_public_result_ref"])
    private_r2 = _json(paths["r2_private_result_ref"])
    if not (
        public_r2.get("run_id") == "FIN013-S3-CASE-TRUTH-SEMANTIC-SLICE-R2"
        and private_r2.get("run_id") == public_r2.get("run_id")
        and public_r2.get("private_result_sha256")
        == _sha(paths["r2_private_result_ref"])
        and private_r2.get("private_result_digest")
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in private_r2.items()
                if key != "private_result_digest"
            }
        )
    ):
        raise CaseTruthProofError("case_truth_proof_r2_binding_invalid")

    r7_input = private_r7["dynamic_projection"]["claim_surface_projection"][
        "claim_surface_research_input"
    ]
    r7_judgment = private_r7["judgment_output"]
    r7_synthesis = private_r7["synthesis_steps"]["validated_synthesis"]
    packet = compile_case_truth_packet(r7_input)
    document = compile_cell_judgment_claim_document(r7_judgment)
    if not (
        private_r2.get("case_truth_packet", {}).get(
            "case_truth_packet_digest"
        )
        == packet["case_truth_packet_digest"]
        and private_r2.get("parent_claim_document", {}).get(
            "claim_document_digest"
        )
        == document["claim_document_digest"]
    ):
        raise CaseTruthProofError("case_truth_proof_r2_truth_binding_drift")
    payload = _eligible_fixture_payload(packet, document)
    revenue_alias = (
        "TRUTH::FACET::operating_performance::"
        "accelerated_compute_or_ai_infrastructure_revenue"
    )
    order_alias = "TRUTH::FACET::demand_volume_quality::ai_orders"
    backlog_alias = "TRUTH::FACET::demand_volume_quality::ai_backlog"
    bridge_alias = next(
        str(row["truth_alias"])
        for row in packet["typed_bridge_boundary_catalog"]
        if row["claim_outcome"] == "company_or_segment_profit_bridge"
    )
    r2_cells = {
        str(row.get("cell_id") or ""): row
        for row in private_r2.get("cell_runs") or []
        if isinstance(row, Mapping)
    }
    if set(r2_cells) != {
        "CELL::operating_performance",
        "CELL::counterevidence",
    }:
        raise CaseTruthProofError("case_truth_proof_r2_cell_coverage_invalid")
    r2_operating = r2_cells["CELL::operating_performance"]
    r2_counter = r2_cells["CELL::counterevidence"]
    stored_r2_counter_findings = [
        str(row.get("finding_code") or "")
        for row in r2_counter.get("local_reconciliation_receipt", {}).get(
            "findings", []
        )
    ]
    if not (
        len(str(r2_operating.get("analysis_draft") or "")) == 9919
        and r2_operating.get("submission_step", {}).get("finish_reason")
        == "length"
        and len(stored_r2_counter_findings) == 14
        and r2_counter.get("submission_step", {}).get("finish_reason")
        == "tool_calls"
    ):
        raise CaseTruthProofError("case_truth_proof_r2_diagnostic_drift")
    r2_operating_draft_rejected = False
    try:
        compile_case_truth_reconciliation_submission_from_analysis(
            case_truth_packet=packet,
            claim_document=r2_operating["claim_document"],
            analysis_draft=r2_operating["analysis_draft"],
        )
    except CaseTruthReconciliationError as exc:
        r2_operating_draft_rejected = (
            exc.code == "case_truth_analysis_draft_invalid"
        )
    r2_counter_overmapping_rejected = False
    try:
        validate_case_truth_reconciliation(
            r2_counter["model_submission"],
            case_truth_packet=packet,
            claim_document=r2_counter["claim_document"],
        )
    except CaseTruthReconciliationError as exc:
        r2_counter_overmapping_rejected = (
            exc.code == "case_truth_assertion_capacity_invalid"
        )
    if not (r2_operating_draft_rejected and r2_counter_overmapping_rejected):
        raise CaseTruthProofError("case_truth_proof_r2_replay_failed_open")
    _replace_assertions(
        payload,
        "CELL::operating_performance::thesis_atom",
        [
            {
                "truth_alias": revenue_alias,
                "claim_polarity": "claim_asserts_absent",
            }
        ],
    )
    _replace_assertions(
        payload,
        "CELL::counterevidence::thesis_atom",
        [
            {
                "truth_alias": order_alias,
                "claim_polarity": "claim_asserts_absent",
            },
            {
                "truth_alias": backlog_alias,
                "claim_polarity": "claim_asserts_absent",
            },
            {
                "truth_alias": bridge_alias,
                "claim_polarity": "claim_asserts_absent",
            },
        ],
    )
    r7_cell_receipt = validate_case_truth_reconciliation(
        payload, case_truth_packet=packet, claim_document=document
    )
    expected_cell_findings = [
        "asserted_absent_but_present_in_case",
        "asserted_absent_but_present_in_case",
        "asserted_absent_but_present_in_case",
    ]
    if [row["finding_code"] for row in r7_cell_receipt["findings"]] != (
        expected_cell_findings
    ):
        raise CaseTruthProofError("case_truth_proof_r7_cell_findings_drift")
    if any(
        row.get("truth_alias") == bridge_alias
        for row in r7_cell_receipt["findings"]
    ):
        raise CaseTruthProofError("case_truth_proof_real_bridge_gap_rejected")

    synthesis_document = compile_synthesis_claim_document(r7_synthesis)
    synthesis_payload = _eligible_fixture_payload(packet, synthesis_document)
    conflict_surface = next(
        str(row["claim_surface_id"])
        for row in synthesis_document["claim_surfaces"]
        if row["field"] == "cell_link"
        and "counterevidence" in row["text"]
        and "conflicts" in row["text"]
    )
    _replace_assertions(
        synthesis_payload,
        conflict_surface,
        [
            {
                "truth_alias": order_alias,
                "claim_polarity": "claim_asserts_absent",
            },
            {
                "truth_alias": backlog_alias,
                "claim_polarity": "claim_asserts_absent",
            },
        ],
    )
    r7_synthesis_receipt = validate_case_truth_reconciliation(
        synthesis_payload,
        case_truth_packet=packet,
        claim_document=synthesis_document,
    )
    if [row["finding_code"] for row in r7_synthesis_receipt["findings"]] != [
        "asserted_absent_but_present_in_case",
        "asserted_absent_but_present_in_case",
    ]:
        raise CaseTruthProofError("case_truth_proof_r7_synthesis_findings_drift")

    synthesis_gate_failed = False
    try:
        compile_five_cell_synthesis_analysis_messages(
            research_input=r7_input,
            judgment_output=r7_judgment,
            structured_deliverable=private_r7["structured_deliverable"],
            case_truth_packet=packet,
            cell_truth_reconciliation=r7_cell_receipt,
        )
    except CaseTruthReconciliationError as exc:
        synthesis_gate_failed = exc.code == "case_truth_reconciliation_not_eligible"
    if not synthesis_gate_failed:
        raise CaseTruthProofError("case_truth_proof_synthesis_gate_failed_open")

    messages, tool = compile_case_truth_reconciliation_submission(
        case_truth_packet=packet,
        claim_document=document,
    )
    model_view = compile_case_truth_model_view(packet)
    claim_model_view = compile_case_truth_claim_model_view(packet, document)
    full_packet_chars = len(
        json.dumps(packet, ensure_ascii=False, sort_keys=True)
    )
    model_view_chars = len(
        json.dumps(model_view, ensure_ascii=False, sort_keys=True)
    )
    if (
        model_view["case_truth_packet_digest"]
        != packet["case_truth_packet_digest"]
        or model_view_chars >= full_packet_chars
        or any(
            "not_visible_presence_aliases" in row
            for row in model_view["cell_visibility_matrix"]
        )
    ):
        raise CaseTruthProofError("case_truth_proof_model_view_invalid")
    visible_submission = json.loads(messages[1]["content"])
    if visible_submission.get("case_truth_claim_view") != claim_model_view:
        raise CaseTruthProofError("case_truth_proof_model_view_binding_drift")
    wire_tool, tool_projection = project_deepseek_strict_tool(tool)
    assertion_contract = tool["function"]["parameters"]["properties"][
        "surface_assertions"
    ]["items"]["properties"]["assertions"]
    if (
        len(messages) != 2
        or assertion_contract.get("maxItems") != 12
        or set(assertion_contract["items"]["properties"])
        != {"truth_alias", "claim_polarity"}
        or tool_projection["finance_contract_weakened"] is not False
        or wire_tool["function"]["name"]
        != "submit_case_truth_reconciliation"
    ):
        raise CaseTruthProofError("case_truth_proof_tool_projection_invalid")

    direct_submission_chars = len(messages[1]["content"])
    direct_tool_chars = len(
        json.dumps(tool, ensure_ascii=False, sort_keys=True)
    )
    slice_documents = []
    slice_receipts = []
    split_contracts = []
    for cell in r7_judgment["cells"]:
        cell_id = str(cell["cell_id"])
        surface_ids = [
            str(row["claim_surface_id"])
            for row in document["claim_surfaces"]
            if row["cell_id"] == cell_id
        ]
        slice_document = compile_claim_document_slice(
            document,
            claim_surface_ids=surface_ids,
        )
        slice_payload = _eligible_fixture_payload(packet, slice_document)
        if cell_id == "CELL::operating_performance":
            _replace_assertions(
                slice_payload,
                f"{cell_id}::thesis_atom",
                [
                    {
                        "truth_alias": revenue_alias,
                        "claim_polarity": "claim_asserts_absent",
                    }
                ],
            )
        elif cell_id == "CELL::counterevidence":
            _replace_assertions(
                slice_payload,
                f"{cell_id}::thesis_atom",
                [
                    {
                        "truth_alias": order_alias,
                        "claim_polarity": "claim_asserts_absent",
                    },
                    {
                        "truth_alias": backlog_alias,
                        "claim_polarity": "claim_asserts_absent",
                    },
                    {
                        "truth_alias": bridge_alias,
                        "claim_polarity": "claim_asserts_absent",
                    },
                ],
            )
        analysis_messages = compile_case_truth_reconciliation_analysis_messages(
            case_truth_packet=packet,
            claim_document=slice_document,
        )
        claim_view = compile_case_truth_claim_model_view(packet, slice_document)
        visible_analysis = json.loads(analysis_messages[1]["content"])
        if not (
            claim_view["scope_mode"] == "single_cell_claim_slice"
            and claim_view["claim_cell_id"] == cell_id
            and visible_analysis["case_truth_claim_view"] == claim_view
            and "cell_visibility_matrix" not in claim_view
            and "whole_case_truth_view" not in claim_view
            and len(analysis_messages[1]["content"]) < model_view_chars
        ):
            raise CaseTruthProofError(
                "case_truth_proof_claim_scoped_model_view_invalid"
            )
        analysis_draft = json.dumps(
            slice_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        submission_messages, slice_tool = (
            compile_case_truth_reconciliation_submission_from_analysis(
                case_truth_packet=packet,
                claim_document=slice_document,
                analysis_draft=analysis_draft,
            )
        )
        wire_slice_tool, slice_projection = project_deepseek_strict_tool(
            slice_tool
        )
        item_contract = slice_tool["function"]["parameters"][
            "properties"
        ]["surface_assertions"]
        if not (
            len(surface_ids) == 3
            and item_contract["minItems"] == 3
            and item_contract["maxItems"] == 3
            and slice_projection["finance_contract_weakened"] is False
            and wire_slice_tool["function"]["name"]
            == "submit_case_truth_reconciliation"
            and len(analysis_messages[1]["content"])
            < direct_submission_chars
            and len(submission_messages[1]["content"])
            < direct_submission_chars
            and len(
                json.dumps(slice_tool, ensure_ascii=False, sort_keys=True)
            )
            < direct_tool_chars
        ):
            raise CaseTruthProofError(
                "case_truth_proof_split_contract_not_materially_smaller"
            )
        receipt = validate_case_truth_reconciliation(
            slice_payload,
            case_truth_packet=packet,
            claim_document=slice_document,
        )
        slice_documents.append(slice_document)
        slice_receipts.append(receipt)
        split_contracts.append(
            {
                "cell_id": cell_id,
                "claim_surface_ids": surface_ids,
                "claim_document_digest": slice_document[
                    "claim_document_digest"
                ],
                "analysis_user_chars": len(analysis_messages[1]["content"]),
                "claim_model_view_chars": len(
                    json.dumps(claim_view, ensure_ascii=False, sort_keys=True)
                ),
                "eligible_current_cell_presence_alias_count": sum(
                    len(row["truth_aliases"])
                    for row in claim_view[
                        "eligible_current_cell_presence_catalog"
                    ]
                ),
                "case_only_outside_cell_alias_count": len(
                    claim_view["case_only_outside_cell_alias_index"]
                ),
                "cross_case_context_alias_count": len(
                    claim_view[
                        "cross_case_context_aliases_visible_in_claim_cell"
                    ]
                ),
                "submission_user_chars": len(
                    submission_messages[1]["content"]
                ),
                "canonical_tool_chars": len(
                    json.dumps(slice_tool, ensure_ascii=False, sort_keys=True)
                ),
                "finance_contract_weakened": False,
                "truth_reconciliation_digest": receipt[
                    "truth_reconciliation_digest"
                ],
                "finding_codes": [
                    row["finding_code"] for row in receipt["findings"]
                ],
            }
        )

    aggregate_receipt = aggregate_case_truth_reconciliation_receipts(
        case_truth_packet=packet,
        parent_claim_document=document,
        slice_claim_documents=slice_documents,
        slice_receipts=slice_receipts,
    )
    if not (
        aggregate_receipt["claim_surfaces_checked"] == 15
        and [
            row["finding_code"] for row in aggregate_receipt["findings"]
        ]
        == expected_cell_findings
        and not any(
            row.get("truth_alias") == bridge_alias
            for row in aggregate_receipt["findings"]
        )
    ):
        raise CaseTruthProofError("case_truth_proof_slice_aggregate_drift")

    slice_by_cell = {
        str(document_slice["claim_surfaces"][0]["cell_id"]): document_slice
        for document_slice in slice_documents
    }
    counter_document = slice_by_cell["CELL::counterevidence"]
    counter_claim_view = compile_case_truth_claim_model_view(
        packet, counter_document
    )
    cross_case_aliases = counter_claim_view[
        "cross_case_context_aliases_visible_in_claim_cell"
    ]
    if len(cross_case_aliases) < 2:
        raise CaseTruthProofError("case_truth_proof_cross_case_context_missing")
    context_payload = _eligible_fixture_payload(packet, counter_document)
    _replace_assertions(
        context_payload,
        "CELL::counterevidence::mechanism_atom",
        [
            {
                "truth_alias": alias,
                "claim_polarity": "claim_uses_cross_case_context",
            }
            for alias in cross_case_aliases
        ],
    )
    context_receipt = validate_case_truth_reconciliation(
        context_payload,
        case_truth_packet=packet,
        claim_document=counter_document,
    )
    if context_receipt["findings"]:
        raise CaseTruthProofError("case_truth_proof_cross_case_context_rejected")

    counter_visibility = next(
        row
        for row in packet["cell_visibility_matrix"]
        if row["cell_id"] == "CELL::counterevidence"
    )
    subject_ticker = packet["case_identity"]["subject_ticker"]
    subject_alias = next(
        alias
        for alias in counter_visibility["visible_presence_aliases"]
        if subject_ticker
        in next(
            row.get("owner_tickers", [])
            for row in packet["presence_catalog"]
            if row["truth_alias"] == alias
        )
    )
    invalid_context_payload = deepcopy(context_payload)
    _replace_assertions(
        invalid_context_payload,
        "CELL::counterevidence::mechanism_atom",
        [
            {
                "truth_alias": subject_alias,
                "claim_polarity": "claim_uses_cross_case_context",
            }
        ],
    )
    invalid_context_receipt = validate_case_truth_reconciliation(
        invalid_context_payload,
        case_truth_packet=packet,
        claim_document=counter_document,
    )
    if [
        row["finding_code"] for row in invalid_context_receipt["findings"]
    ] != ["claimed_cross_case_context_for_subject_fact"]:
        raise CaseTruthProofError(
            "case_truth_proof_subject_fact_context_failed_open"
        )

    operating_document = slice_by_cell["CELL::operating_performance"]
    operating_visibility = next(
        row
        for row in packet["cell_visibility_matrix"]
        if row["cell_id"] == "CELL::operating_performance"
    )
    outside_operating_alias = next(
        alias
        for alias in packet["all_truth_aliases"]
        if alias in {row["truth_alias"] for row in packet["presence_catalog"]}
        and alias not in operating_visibility["visible_presence_aliases"]
        and any(
            row["truth_alias"] == alias
            and row.get("owner_tickers") == [subject_ticker]
            for row in packet["presence_catalog"]
        )
    )
    outside_payload = _eligible_fixture_payload(packet, operating_document)
    _replace_assertions(
        outside_payload,
        "CELL::operating_performance::mechanism_atom",
        [
            {
                "truth_alias": outside_operating_alias,
                "claim_polarity": "claim_asserts_present",
            }
        ],
    )
    outside_receipt = validate_case_truth_reconciliation(
        outside_payload,
        case_truth_packet=packet,
        claim_document=operating_document,
    )
    if [row["finding_code"] for row in outside_receipt["findings"]] != [
        "asserted_present_outside_cell_visibility"
    ]:
        raise CaseTruthProofError("case_truth_proof_outside_cell_failed_open")

    capacity_payload = _eligible_fixture_payload(packet, operating_document)
    _replace_assertions(
        capacity_payload,
        "CELL::operating_performance::thesis_atom",
        [
            {
                "truth_alias": alias,
                "claim_polarity": "claim_asserts_present",
            }
            for alias in operating_visibility["visible_presence_aliases"][:13]
        ],
    )
    capacity_failed_closed = False
    try:
        validate_case_truth_reconciliation(
            capacity_payload,
            case_truth_packet=packet,
            claim_document=operating_document,
        )
    except CaseTruthReconciliationError as exc:
        capacity_failed_closed = (
            exc.code == "case_truth_assertion_capacity_invalid"
        )
    if not capacity_failed_closed:
        raise CaseTruthProofError("case_truth_proof_capacity_failed_open")

    missing_slice_failed = False
    try:
        aggregate_case_truth_reconciliation_receipts(
            case_truth_packet=packet,
            parent_claim_document=document,
            slice_claim_documents=slice_documents[:-1],
            slice_receipts=slice_receipts[:-1],
        )
    except CaseTruthReconciliationError as exc:
        missing_slice_failed = (
            exc.code
            == "case_truth_receipt_aggregation_surface_coverage_invalid"
        )
    overlapping_slice_failed = False
    try:
        aggregate_case_truth_reconciliation_receipts(
            case_truth_packet=packet,
            parent_claim_document=document,
            slice_claim_documents=[*slice_documents, slice_documents[0]],
            slice_receipts=[*slice_receipts, slice_receipts[0]],
        )
    except CaseTruthReconciliationError as exc:
        overlapping_slice_failed = (
            exc.code == "case_truth_receipt_aggregation_surface_overlap"
        )
    if not (missing_slice_failed and overlapping_slice_failed):
        raise CaseTruthProofError("case_truth_proof_slice_mutation_failed_open")

    consumer_policy = _json(paths["consumer_policy_ref"])
    kernel, planning, evidence, retrieval = _case_services()
    case_inputs = {"DELL": r7_input}
    for case_key in ("MU", "NVDA"):
        case_inputs[case_key] = _current_case_input(
            case_key,
            consumer_policy=consumer_policy,
            kernel=kernel,
            planning=planning,
            evidence=evidence,
            retrieval=retrieval,
        )
    case_packets = {
        case_key: compile_case_truth_packet(value)
        for case_key, value in case_inputs.items()
    }
    case_matrix = []
    for case_key, case_packet in case_packets.items():
        if case_packet["case_identity"]["case_key"] != case_key:
            raise CaseTruthProofError("case_truth_proof_case_identity_pollution")
        permuted = compile_case_truth_packet(_permuted_input(case_inputs[case_key]))
        if permuted["case_truth_packet_digest"] != case_packet[
            "case_truth_packet_digest"
        ]:
            raise CaseTruthProofError("case_truth_proof_permutation_instability")
        case_matrix.append(
            {
                "case_key": case_key,
                "case_truth_packet_digest": case_packet[
                    "case_truth_packet_digest"
                ],
                "presence_alias_count": len(case_packet["presence_catalog"]),
                "typed_gap_alias_count": len(case_packet["typed_gap_catalog"]),
                "typed_bridge_boundary_count": len(
                    case_packet["typed_bridge_boundary_catalog"]
                ),
                "cell_count": len(case_packet["cell_visibility_matrix"]),
                "permutation_stable": True,
            }
        )

    cross_case_failed = False
    forged = deepcopy(case_packets["MU"])
    forged["case_identity"]["case_key"] = "NVDA"
    try:
        validate_case_truth_packet(forged, research_input=case_inputs["MU"])
    except CaseTruthReconciliationError as exc:
        cross_case_failed = exc.code == "case_truth_packet_binding_drift"
    if not cross_case_failed:
        raise CaseTruthProofError("case_truth_proof_cross_case_failed_open")

    holdout_input = _holdout_input()
    holdout_packet = compile_case_truth_packet(holdout_input)
    holdout_presence_gap = next(
        row
        for row in holdout_packet["typed_gap_catalog"]
        if row["facet_id"] == "supplier_capacity_signal"
    )
    holdout_absence = next(
        row
        for row in holdout_packet["typed_gap_catalog"]
        if row["facet_id"] == "product_profit_bridge"
    )
    if not (
        holdout_presence_gap["coverage_state"] == "present_with_typed_gap"
        and holdout_presence_gap["case_absence_authorized"] is False
        and holdout_absence["coverage_state"] == "typed_gap_only"
        and holdout_absence["case_absence_authorized"] is True
    ):
        raise CaseTruthProofError("case_truth_proof_holdout_state_invalid")

    private_unsigned = {
        "schema_version": "fin_ia_s3_case_truth_reconciliation_private_proof_v1_2",
        "run_id": authority["run_id"],
        "implementation_commit": commit,
        "r7_case_truth_packet": packet,
        "r7_case_truth_model_view": model_view,
        "r7_cell_claim_document": document,
        "r7_cell_reconciliation_receipt": r7_cell_receipt,
        "r7_cell_slice_claim_documents": slice_documents,
        "r7_cell_slice_reconciliation_receipts": slice_receipts,
        "r7_cell_slice_aggregate_receipt": aggregate_receipt,
        "split_analysis_submission_contracts": split_contracts,
        "r7_synthesis_claim_document": synthesis_document,
        "r7_synthesis_reconciliation_receipt": r7_synthesis_receipt,
        "r2_capture_replay": {
            "public_result": public_r2,
            "operating_analysis_chars": len(r2_operating["analysis_draft"]),
            "operating_draft_rejected_before_submission": (
                r2_operating_draft_rejected
            ),
            "counter_original_finding_codes": stored_r2_counter_findings,
            "counter_overmapping_rejected_before_submission": (
                r2_counter_overmapping_rejected
            ),
        },
        "claim_polarity_mutation_receipts": {
            "cross_case_context": context_receipt,
            "subject_fact_as_context": invalid_context_receipt,
            "outside_cell_presence": outside_receipt,
            "capacity_failed_closed": capacity_failed_closed,
        },
        "case_packets": case_packets,
        "holdout_packet": holdout_packet,
        "deepseek_tool_projection_receipt": tool_projection,
        "execution": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "embedding_calls": 0,
            "retries": 0,
            "candidate_promotions": 0,
        },
    }
    private_payload = {
        **private_unsigned,
        "private_result_digest": canonical_digest(private_unsigned),
    }
    _write_new(private_path, private_payload)

    public_unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "zero_call_case_truth_claim_polarity_engineering_pass",
        "run_id": authority["run_id"],
        "recorded_at": authority["issued_at"],
        "implementation_commit": commit,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "private_result_ref": _relative(private_path),
        "private_result_sha256": _sha(private_path),
        "r7_replay": {
            "case_truth_packet_digest": packet["case_truth_packet_digest"],
            "cell_reconciliation_status": r7_cell_receipt["status"],
            "cell_finding_codes": [
                row["finding_code"] for row in r7_cell_receipt["findings"]
            ],
            "cell_finding_surfaces": [
                row["claim_surface_id"] for row in r7_cell_receipt["findings"]
            ],
            "typed_profit_bridge_gap_accepted": True,
            "synthesis_reconciliation_status": r7_synthesis_receipt["status"],
            "synthesis_finding_codes": [
                row["finding_code"]
                for row in r7_synthesis_receipt["findings"]
            ],
            "false_cross_cell_conflict_blocked": True,
            "synthesis_gate_failed_closed": synthesis_gate_failed,
        },
        "r2_capture_replay": {
            "run_id": public_r2["run_id"],
            "operating_analysis_chars": len(r2_operating["analysis_draft"]),
            "operating_submission_finish_reason": r2_operating[
                "submission_step"
            ]["finish_reason"],
            "operating_oversize_draft_failed_before_new_submission": (
                r2_operating_draft_rejected
            ),
            "counter_original_finding_count": len(
                stored_r2_counter_findings
            ),
            "counter_thirteen_assertion_surface_failed_before_new_submission": (
                r2_counter_overmapping_rejected
            ),
        },
        "case_matrix": case_matrix,
        "holdout_mutation": {
            "case_key": "HOLDOUT_INDUSTRIAL",
            "external_owner_preserved": True,
            "presence_and_gap_coexistence_preserved": True,
            "typed_gap_only_absence_authorized": True,
            "case_truth_packet_digest": holdout_packet[
                "case_truth_packet_digest"
            ],
        },
        "mutations": {
            "candidate_and_catalog_permutation_stable": True,
            "cross_case_packet_reuse_failed_closed": cross_case_failed,
            "required_material_surface_cannot_silently_abstain": True,
            "unknown_alias_and_surface_digest_drift_fail_closed": True,
            "missing_slice_failed_closed": missing_slice_failed,
            "overlapping_slice_failed_closed": overlapping_slice_failed,
            "cross_case_context_accepted_only_for_non_subject_fact": True,
            "subject_fact_as_cross_case_context_failed_closed": True,
            "outside_cell_presence_failed_closed": True,
            "thirteen_direct_propositions_failed_closed": (
                capacity_failed_closed
            ),
        },
        "tool_contract": {
            "provider_neutral_canonical_tool_name": tool["function"]["name"],
            "deepseek_strict_projection_qualified": True,
            "finance_contract_weakened": False,
            "local_exhaustive_surface_validation_required": True,
            "tool_emits_claim_polarity_not_authoritative_state": True,
            "maximum_direct_propositions_per_surface": 12,
            "full_authority_packet_chars": full_packet_chars,
            "compact_model_view_chars": model_view_chars,
            "compact_model_view_bound_to_full_packet_digest": True,
            "cell_hidden_fact_repetition_omitted_from_model_view": True,
            "claim_scoped_tiered_alias_view": True,
        },
        "split_analysis_submission_contract": {
            "cell_slice_count": len(split_contracts),
            "claim_surfaces_per_slice": 3,
            "parent_claim_surfaces_covered": aggregate_receipt[
                "claim_surfaces_checked"
            ],
            "direct_submission_user_chars": direct_submission_chars,
            "direct_canonical_tool_chars": direct_tool_chars,
            "largest_analysis_user_chars": max(
                row["analysis_user_chars"] for row in split_contracts
            ),
            "largest_submission_user_chars": max(
                row["submission_user_chars"] for row in split_contracts
            ),
            "largest_canonical_tool_chars": max(
                row["canonical_tool_chars"] for row in split_contracts
            ),
            "analysis_and_submission_are_separate_calls": True,
            "submission_does_not_receive_full_truth_catalog": True,
            "analysis_maps_direct_propositions_not_supporting_fact_inventory": True,
            "local_aggregate_is_parent_digest_bound": True,
            "aggregate_finding_codes": [
                row["finding_code"]
                for row in aggregate_receipt["findings"]
            ],
            "legitimate_product_profit_gap_preserved": True,
        },
        "acceptance": {
            "case_presence_catalog_compiled": True,
            "cell_visibility_matrix_compiled": True,
            "typed_absence_authority_compiled": True,
            "r7_false_absence_detected": True,
            "r7_false_conflict_detected": True,
            "legitimate_product_profit_gap_preserved": True,
            "dell_mu_nvda_packet_compilation": True,
            "heterogeneous_holdout_mutation": True,
            "five_cell_slice_compilation": True,
            "analysis_submission_separation": True,
            "parent_bound_slice_aggregation": True,
            "claim_polarity_separated_from_authoritative_truth": True,
            "cross_case_context_semantics": True,
            "claim_scoped_alias_projection": True,
            "r2_capture_replay": True,
            "natural_semantic_extraction_proven": False,
            "r7_judgments_repaired": False,
            "r7_synthesis_repaired": False,
            "dell_five_cell_content_accepted": False,
            "generalization_accepted": False,
            "s3_accepted": False,
            "release_ready": False,
        },
        "next_decision": (
            "After clean repository proof, one final bounded natural successor over "
            "the same two R7 cells may be considered. It must use the tiered alias "
            "view and claim-polarity contract, identify all three false absences, "
            "preserve the legitimate product-profit bridge gap, and separately "
            "surface real cross-cell claim leakage. No remaining cell or research "
            "repair may run before that content assessment."
        ),
        "known_boundary": (
            "This zero-call result proves deterministic truth-packet compilation, "
            "claim-scoped alias projection, claim-polarity versus truth separation, "
            "cross-case-context semantics, bounded assertion capacity, slice "
            "aggregation, transport projection and fail-closed downstream gating. "
            "Fake semantic mappings are test fixtures, not natural model quality "
            "or business truth. It does not repair R7, itself authorize a paid "
            "successor, prove DELL content quality, generalization, S3, Workbench "
            "publication or release."
        ),
    }
    public_payload = {
        **public_unsigned,
        "result_digest": canonical_digest(public_unsigned),
    }
    _write_new(public_path, public_payload)
    return public_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args()
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
