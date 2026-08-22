from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.cuda_execution import required_cuda_fp16_receipt  # noqa: E402
from retrieval.hybrid_candidate_runtime import (  # noqa: E402
    LocalQwenHybridCandidateRuntime,
)
from sec_agent.research.dynamic_truth_spine import (  # noqa: E402
    compile_dynamic_evidence_responses,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest  # noqa: E402


KERNEL_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_4.json"
)
ROUTE_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_4.json"
)
HYBRID_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_5.json"
)
SNAPSHOT_REF = "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_2.json"
FACT_MART_REF = (
    "data/workbench_private/fin_0_1_3_s2_company_financial_fact_mart/"
    "v1/company_financial_facts.sqlite"
)
PACK_REF = (
    "data/workbench_private/fin_0_1_3_s1_dell_external_source_evidence/"
    "dell-r3-capture-replay/successor/pack.json"
)
TRUTH_POLICY_REF = (
    "configs/research/fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_1.json"
)
DEFAULT_OUTPUT = (
    "configs/research/evals/"
    "fin_ia_0_1_3_s1_s3_dell_dynamic_public_reachability_zero_call_result_v1_0.json"
)


REQUEST_SPECS = (
    {
        "request_id": "REQ::DELL::SUBJECT-CONFIGURATION::ZERO-CALL",
        "facet_id": "pricing_and_mix",
        "targets": ["DELL"],
        "product_intents": [
            "Dell AI server product configuration and deployable solution mix"
        ],
    },
    {
        "request_id": "REQ::DELL::CUSTOMER-DEPLOYMENT::ZERO-CALL",
        "facet_id": "conversion_and_durability",
        "targets": ["DELL"],
        "product_intents": [
            "named customer deployment and evidence of actual AI infrastructure use"
        ],
    },
    {
        "request_id": "REQ::DELL::INDUSTRY-DEMAND::ZERO-CALL",
        "facet_id": "industry_demand_context",
        "targets": ["ORG::05BF3EEF551722C8"],
        "product_intents": [
            "AI server shipments infrastructure spending and buyer commitment"
        ],
    },
    {
        "request_id": "REQ::DELL::INDUSTRY-PVM::ZERO-CALL",
        "facet_id": "industry_pricing_mix_context",
        "targets": ["ORG::13AAFF874F67F30C"],
        "product_intents": [
            "AI server unit growth industry value growth and configuration mix"
        ],
    },
    {
        "request_id": "REQ::DELL::CHANNEL-CONFIGURATION::ZERO-CALL",
        "facet_id": "channel_configuration_context",
        "targets": ["ORG::397A7B207441AF01"],
        "product_intents": [
            "Dell PowerEdge channel configuration GPU memory CPU and storage mix"
        ],
    },
    {
        "request_id": "REQ::DELL::VALUE-POOL::ZERO-CALL",
        "facet_id": "trusted_value_pool_context",
        "targets": ["ORG::1663EE18A9AFB7C9", "ORG::8FDBEED39DAE342A"],
        "product_intents": [
            "AI server OEM value pool supplier bargaining and margin pressure"
        ],
    },
    {
        "request_id": "REQ::DELL::INDUSTRY-SUPPLY::ZERO-CALL",
        "facet_id": "industry_supply_context",
        "targets": ["ORG::13AAFF874F67F30C"],
        "product_intents": [
            "advanced process packaging HBM supply constraints and release timing"
        ],
    },
    {
        "request_id": "REQ::DELL::EXTERNAL-COUNTEREVIDENCE::ZERO-CALL",
        "facet_id": "trusted_or_industry_counterevidence",
        "targets": [
            "ORG::13AAFF874F67F30C",
            "ORG::1663EE18A9AFB7C9",
            "ORG::8FDBEED39DAE342A",
        ],
        "product_intents": [
            "AI server demand digestion margin pressure and supplier value capture"
        ],
    },
)


def _resolve(ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(ref: str) -> dict[str, Any]:
    value = json.loads(_resolve(ref).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{ref}")
    return value


def _write_json(ref: str, value: dict[str, Any]) -> None:
    path = _resolve(ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _request(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": spec["request_id"],
        "cell_id": "CELL::value_capture",
        "requester_role": "fundamental_value_capture_analyst",
        "evidence_domain": "financial_research",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "research_as_of": "2026-08-06",
        "target_entities": list(spec["targets"]),
        "requested_facet_ids": [spec["facet_id"]],
        "metric_intents": [],
        "product_intents": list(spec["product_intents"]),
        "period": {
            "start_date": "2023-01-01",
            "end_date": "2026-08-06",
            "fiscal_years": [],
        },
        "granularity": "source_bound_claim",
        "unit": "qualitative_or_industry_reported",
        "acceptable_sources": ["PUBLIC_WEB"],
        "acceptable_proxy": True,
        "forbidden_proxy": [
            "industry fact treated as Dell fact",
            "supplier fact treated as Dell allocation",
        ],
        "stop_condition": "reviewed evidence or actionable typed gap",
        "clarification_policy": "return_typed_gap",
    }


def _reviewed_keys_by_request(
    pack: dict[str, Any],
    requests: list[dict[str, Any]],
) -> dict[str, dict[str, list[str]]]:
    source_by_ref = {
        str(row.get("material_ref") or ""): row
        for row in pack.get("source_materials") or ()
    }
    output: dict[str, dict[str, list[str]]] = {}
    for request in requests:
        targets = set(request["target_entities"])
        by_owner: dict[str, set[str]] = {target: set() for target in targets}
        for item in pack.get("evidence_items") or ():
            material = source_by_ref.get(str(item.get("source_material_ref") or ""))
            if not isinstance(material, dict):
                continue
            owner = str(material.get("evidence_owner_ticker") or "").upper()
            item_slots = {
                str(binding.get("slot_id") or "")
                for binding in item.get("slot_bindings") or ()
            }
            request_slot = {
                "pricing_and_mix": "pricing_mix_value_capture",
                "conversion_and_durability": "demand_volume_quality",
                "industry_demand_context": "demand_volume_quality",
                "industry_pricing_mix_context": "pricing_mix_value_capture",
                "channel_configuration_context": "pricing_mix_value_capture",
                "trusted_value_pool_context": "pricing_mix_value_capture",
                "industry_supply_context": "capacity_inputs_execution",
                "trusted_or_industry_counterevidence": (
                    "counterevidence_and_what_would_change"
                ),
            }[request["requested_facet_ids"][0]]
            if owner in targets and request_slot in item_slots:
                by_owner[owner].add(
                    f"{item['source_record_id']}::{item['source_content_digest']}"
                )
        output[request["request_id"]] = {
            owner: sorted(keys) for owner, keys in sorted(by_owner.items())
        }
    return output


def _candidate_keys(row: dict[str, Any]) -> set[str]:
    digest = str(row.get("source_content_digest") or "")
    lineage = {
        str(value)
        for value in row.get("lineage_source_record_ids") or ()
        if str(value)
    }
    lineage.add(str(row.get("source_record_id") or ""))
    return {f"{source_id}::{digest}" for source_id in lineage if source_id}


def _controlled(batch: dict[str, Any]) -> dict[str, Any]:
    body = {
        "status": "controlled_research_plan_zero_call_executed",
        "objective": {
            "objective_id": "OBJ::DELL::VALUE-CAPTURE-DYNAMIC-REACHABILITY",
            "case_key": "DELL",
            "subject_ticker": "DELL",
            "research_as_of": "2026-08-06",
        },
        "request_results": deepcopy(batch["request_results"]),
    }
    return {**body, "projection_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prove that capture-bound public sources are reachable by typed DELL "
            "requests and reselect only exact reviewed content slices."
        )
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    kernel = _read_json(KERNEL_REF)
    route = _read_json(ROUTE_REF)
    hybrid_policy = _read_json(HYBRID_REF)
    pack = _read_json(PACK_REF)
    truth_policy = _read_json(TRUTH_POLICY_REF)
    cuda = required_cuda_fp16_receipt(
        purpose="DELL dynamic public candidate retrieval zero-call proof"
    )
    hybrid = LocalQwenHybridCandidateRuntime.from_policy(
        ROOT, hybrid_policy
    )
    service = ResearchRetrievalService(
        snapshot=_read_json(SNAPSHOT_REF),
        kernel=kernel,
        route_policy=route,
        hybrid_candidate_runtime=hybrid,
        hybrid_candidate_policy=hybrid_policy,
        company_financial_fact_mart_path=_resolve(FACT_MART_REF),
    )
    principal = ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )
    requests = [_request(dict(spec)) for spec in REQUEST_SPECS]
    expected = _reviewed_keys_by_request(pack, requests)
    batch = service.execute_current_runtime_requests(
        "DELL", requests, principal
    )
    controlled = _controlled(batch)
    responses = compile_dynamic_evidence_responses(
        policy=truth_policy,
        controlled_plan=controlled,
        evidence_pack=pack,
    )

    rows: list[dict[str, Any]] = []
    request_result_by_id = {
        str(row["request"]["request_id"]): row
        for row in batch["request_results"]
    }
    response_by_id = {
        str(row["request_id"]): row for row in responses["responses"]
    }
    for request in requests:
        request_id = request["request_id"]
        request_result = request_result_by_id[request_id]
        selected = request_result["hybrid_object_retrieval"]["candidates"]
        selected_keys = {
            key for row in selected for key in _candidate_keys(dict(row))
        }
        target_hits = {
            owner: sorted(selected_keys.intersection(keys))
            for owner, keys in expected[request_id].items()
        }
        response = response_by_id[request_id]
        rows.append(
            {
                "request_id": request_id,
                "facet_id": request["requested_facet_ids"][0],
                "target_entities": list(request["target_entities"]),
                "selected_candidate_count": len(selected),
                "selected_source_count": len(
                    {str(row["source_record_id"]) for row in selected}
                ),
                "selected_owner_counts": dict(
                    request_result["hybrid_object_retrieval"]["summary"][
                        "selected_candidate_count_by_owner"
                    ]
                ),
                "reviewed_target_hits_by_owner": target_hits,
                "every_reviewed_target_owner_reached": all(
                    bool(values) for values in target_hits.values()
                ),
                "accepted_reviewed_evidence_count": len(response["accepted"]),
                "needs_human_review_count": len(response["needs_human_review"]),
                "typed_gap_codes": [
                    str(row["gap"].get("gap_code") or "")
                    for row in response["typed_gaps"]
                ],
                "top_candidates": [
                    {
                        "rank": row["rank"],
                        "owner": row["ticker"],
                        "source_record_id": row["source_record_id"],
                        "source_content_digest": row["source_content_digest"],
                        "object_kind": row["object_kind"],
                        "route_membership": list(row["route_membership"]),
                        "text": str(row["model_text"])[:240],
                    }
                    for row in selected[:4]
                ],
            }
        )

    mutation_controlled = deepcopy(controlled)
    mutation_result = mutation_controlled["request_results"][0]
    mutation_candidates = mutation_result["hybrid_object_retrieval"]["candidates"]
    for candidate in mutation_candidates:
        candidate["source_content_digest"] = ""
    mutation_controlled["projection_digest"] = canonical_digest(
        {
            key: value
            for key, value in mutation_controlled.items()
            if key != "projection_digest"
        }
    )
    mutation_responses = compile_dynamic_evidence_responses(
        policy=truth_policy,
        controlled_plan=mutation_controlled,
        evidence_pack=pack,
    )
    mutated = mutation_responses["responses"][0]

    checks = {
        "all_requests_have_candidates": all(
            row["selected_candidate_count"] > 0 for row in rows
        ),
        "all_reviewed_target_owners_reached": all(
            row["every_reviewed_target_owner_reached"] for row in rows
        ),
        "all_requests_reselect_reviewed_evidence": all(
            row["accepted_reviewed_evidence_count"] > 0 for row in rows
        ),
        "candidate_owner_scope_exact": all(
            set(row["selected_owner_counts"]).issubset(row["target_entities"])
            and all(
                int(count) > 0
                for count in row["selected_owner_counts"].values()
            )
            for row in rows
        ),
        "candidate_never_grants_evidence_or_numeric_authority": all(
            result["hybrid_object_retrieval"]["candidate_state"]
            == "candidate_not_evidence"
            and result["hybrid_object_retrieval"]["authority"][
                "numeric_authority"
            ]
            is False
            for result in batch["request_results"]
        ),
        "exact_content_digest_required": (
            not mutated["accepted"]
            and bool(mutated["needs_human_review"])
            and {
                str(row["reason"])
                for row in mutated["needs_human_review"]
            }
            == {"public_candidate_source_content_digest_missing"}
        ),
        "no_new_evidence_promotion": (
            responses["summary"]["new_evidence_promotions"] == 0
        ),
        "cuda_fp16_only": (
            cuda["execution_device"].startswith("cuda:")
            and cuda["fp16_smoke_device"].startswith("cuda:")
        ),
        "zero_network_and_generation_calls": (
            batch["summary"]["network_calls"] == 0
            and batch["summary"]["generation_model_calls"] == 0
            and responses["summary"]["model_calls"] == 0
        ),
    }
    body = {
        "schema_version": (
            "fin_ia_s1_s3_dell_dynamic_public_reachability_zero_call_result_v1_0"
        ),
        "status": (
            "pass"
            if all(checks.values())
            else "fail_closed"
        ),
        "recorded_at": "2026-08-23",
        "inputs": {
            "kernel_ref": KERNEL_REF,
            "route_policy_ref": ROUTE_REF,
            "hybrid_policy_ref": HYBRID_REF,
            "snapshot_ref": SNAPSHOT_REF,
            "fact_mart_ref": FACT_MART_REF,
            "evidence_pack_ref": PACK_REF,
            "truth_policy_ref": TRUTH_POLICY_REF,
        },
        "runtime": {
            "request_count": len(requests),
            "selected_candidate_count": sum(
                row["selected_candidate_count"] for row in rows
            ),
            "accepted_reviewed_evidence_count": responses["summary"][
                "accepted_reviewed_evidence_count"
            ],
            "cuda_receipt": cuda,
            "network_calls": 0,
            "generation_model_calls": 0,
        },
        "request_results": rows,
        "mutation": {
            "name": "remove_public_content_slice_digest",
            "accepted_reviewed_evidence_count": len(mutated["accepted"]),
            "needs_human_review_count": len(mutated["needs_human_review"]),
            "reasons": sorted(
                {str(row["reason"]) for row in mutated["needs_human_review"]}
            ),
        },
        "checks": checks,
        "authority": {
            "candidate_is_not_evidence": True,
            "exact_reviewed_content_slice_required": True,
            "numeric_authority_remains_s2": True,
            "model_calls_authorized": False,
            "network_calls_authorized": False,
        },
        "known_boundary": (
            "This proof executes typed requests through the successor local "
            "BM25 plus CUDA Qwen candidate runtime and exact reviewed-Pack "
            "reselection. It does not test natural DeepSeek planning, external "
            "network acquisition, new Evidence admission, research judgment, "
            "writing or product acceptance."
        ),
    }
    result = {**body, "result_digest": canonical_digest(body)}
    _write_json(args.output, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "request_count": len(requests),
                "selected_candidate_count": result["runtime"][
                    "selected_candidate_count"
                ],
                "accepted_reviewed_evidence_count": result["runtime"][
                    "accepted_reviewed_evidence_count"
                ],
                "checks": checks,
                "result_digest": result["result_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
