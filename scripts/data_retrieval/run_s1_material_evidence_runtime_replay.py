from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.contracts import (  # noqa: E402
    EvidenceRequest,
    EvidenceRequestPeriod,
    load_financial_research_kernel,
)
from retrieval.evidence_set_coverage import (  # noqa: E402
    canonical_digest,
    select_request_bound_review,
)
from retrieval.financial_evidence_shortlist import (  # noqa: E402
    candidate_shortlist_features as candidate_shortlist_features_v1,
    rank_financial_evidence_shortlist,
)
from retrieval.financial_evidence_shortlist_v2 import (  # noqa: E402
    candidate_shortlist_features as candidate_shortlist_features_v2,
)
from retrieval.material_evidence_runtime import (  # noqa: E402
    adapt_material_candidate_from_feature_views,
    compile_material_requirement_plan_from_runtime_input,
)
from retrieval.object_retrieval_comparison import load_compiled_objects  # noqa: E402
from retrieval.query_atom_shadow import (  # noqa: E402
    compile_atom_lane,
    load_query_atoms,
)
from retrieval.query_plan import OwnerQuery, QueryLane  # noqa: E402
from retrieval.retrieval_need import compile_retrieval_needs  # noqa: E402


RECORDED_AT = "2026-08-18"
RESULT_SCHEMA = "fin_ia_s1_material_evidence_runtime_replay_v1_1"
PUBLIC_SCHEMA = "fin_ia_s1_material_evidence_runtime_replay_summary_v1_1"

DEFAULT_POLICY = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_material_evidence_runtime_policy_v1_0.json"
)
DEFAULT_ONTOLOGY = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_intent_ontology_v1_2.json"
)
DEFAULT_KERNEL = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_3.json"
)
DEFAULT_NEED_POLICY = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_vs5_retrieval_need_compiler_policy_v1_2.json"
)
DEFAULT_DELL_ATOMS = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_vs4_dell_supplement_query_atoms_v1_1.json"
)
DEFAULT_DELL_FULL = (
    "data/workbench_private/"
    "fin_0_1_3_s1_vs4_dell_supplement_candidate_ranking/v1_3/"
    "full_result_e315e8460282130604d7cec5511b094d340afe67b2abc163a177149c5539d9a9.json"
)
DEFAULT_MU_NVDA_ATOMS = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_vs4_mu_nvda_supplement_query_atoms_v1_1.json"
)
DEFAULT_MU_NVDA_FULL = (
    "data/workbench_private/"
    "fin_0_1_3_s1_vs4_mu_nvda_supplement_candidate_ranking/v1_7/"
    "full_result_8b48b41306f68cd70ccc5ae4d1dbf6e359b854f9720c9127fd37f10f01935ff7.json"
)
DEFAULT_VS4_OBJECTS = (
    "data/workbench_private/"
    "fin_0_1_3_s1c_compiled_financial_object_views/v4/objects.jsonl"
)
DEFAULT_COST_INPUTS = (
    "eval_sets/fin_0_1_3_s1/inputs/valid_temporal/"
    "vs5_qualification_inputs_v1_1.jsonl"
)
DEFAULT_COST_RAW = (
    "data/workbench_private/"
    "fin_0_1_3_s1_vs5_qualification_candidates/valid-temporal-r2/raw.json"
)
DEFAULT_COST_OBJECTS = (
    "data/workbench_private/"
    "fin_0_1_3_s1_vs5_qualification_compiled_objects/live-r1/objects.jsonl"
)
DEFAULT_PRIVATE_OUTPUT = (
    "data/workbench_private/"
    "fin_0_1_3_s1_material_evidence_runtime_replay/v1_1/full_result.json"
)
DEFAULT_PUBLIC_OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_material_evidence_runtime_replay_result_v1_1.json"
)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"material_replay_json_object_required:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            _require(
                isinstance(value, dict),
                f"material_replay_jsonl_object_required:{path.name}:{line_number}",
            )
            rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _objects(path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = list(load_compiled_objects(_read_jsonl(path)))
    return rows, {str(row["compiled_object_id"]): row for row in rows}


def _cross_rank_maps(raw: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for route_id, values in raw.items():
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            continue
        output[str(route_id)] = {
            str(object_id): rank for rank, object_id in enumerate(values, 1)
        }
    return output


def _candidate_row(feature: Mapping[str, Any], *, rank: int) -> dict[str, Any]:
    return {
        "compiled_object_id": str(feature["compiled_object_id"]),
        "rank": rank,
        "score": float(1.0 / rank),
    }


def _bound_evidence_request(payload: Mapping[str, Any]) -> EvidenceRequest:
    """Deserialize an already-validated public runtime request without a hidden case catalog."""

    period = payload.get("period") or {}
    _require(isinstance(period, Mapping), "material_replay_bound_period_invalid")
    def parsed_date(value: Any) -> date | None:
        return date.fromisoformat(str(value)) if value not in (None, "") else None

    return EvidenceRequest(
        schema_version=str(payload["schema_version"]),
        request_id=str(payload["request_id"]),
        cell_id=str(payload["cell_id"]),
        requester_role=str(payload["requester_role"]),
        evidence_domain=str(payload["evidence_domain"]),
        case_key=str(payload["case_key"]),
        subject_ticker=str(payload["subject_ticker"]),
        research_as_of=date.fromisoformat(str(payload["research_as_of"])),
        target_entities=tuple(str(value) for value in payload["target_entities"]),
        requested_facet_ids=tuple(
            str(value) for value in payload["requested_facet_ids"]
        ),
        metric_intents=tuple(str(value) for value in payload["metric_intents"]),
        product_intents=tuple(str(value) for value in payload["product_intents"]),
        period=EvidenceRequestPeriod(
            start_date=parsed_date(period.get("start_date")),
            end_date=parsed_date(period.get("end_date")),
            fiscal_years=tuple(int(value) for value in period["fiscal_years"]),
        ),
        granularity=str(payload["granularity"]),
        unit=str(payload["unit"]),
        acceptable_sources=tuple(
            str(value) for value in payload["acceptable_sources"]
        ),
        acceptable_proxy=bool(payload["acceptable_proxy"]),
        forbidden_proxy=tuple(str(value) for value in payload["forbidden_proxy"]),
        stop_condition=str(payload["stop_condition"]),
        clarification_policy=str(payload["clarification_policy"]),
    )


def _bound_query_lane(payload: Mapping[str, Any]) -> QueryLane:
    """Deserialize a frozen valid-temporal lane; no case/reference catalog is read."""

    return QueryLane(
        lane_id=str(payload["lane_id"]),
        slot_id=str(payload["slot_id"]),
        facet_id=str(payload["facet_id"]),
        business_question_zh=str(payload["business_question_zh"]),
        execution_mode=str(payload["execution_mode"]),
        subject_ticker=str(payload["subject_ticker"]),
        evidence_owner_tickers=tuple(
            str(value) for value in payload["evidence_owner_tickers"]
        ),
        relationship_constraints=tuple(
            str(value) for value in payload["relationship_constraints"]
        ),
        publication_date_lte=str(payload["publication_date_lte"]),
        source_types=tuple(str(value) for value in payload["source_types"]),
        required_source_roles=tuple(
            str(value) for value in payload["required_source_roles"]
        ),
        exact_queries=tuple(str(value) for value in payload["exact_queries"]),
        lexical_query=str(payload["lexical_query"]),
        lexical_tokens=tuple(str(value) for value in payload["lexical_tokens"]),
        owner_queries=tuple(
            OwnerQuery(
                evidence_owner_ticker=str(row["evidence_owner_ticker"]),
                relationship_direction=str(row["relationship_direction"]),
                lexical_query=str(row["lexical_query"]),
                lexical_tokens=tuple(str(value) for value in row["lexical_tokens"]),
                anchor_token_groups=tuple(
                    tuple(str(token) for token in group)
                    for group in row["anchor_token_groups"]
                ),
            )
            for row in payload["owner_queries"]
        ),
        semantic_query=str(payload["semantic_query"]),
        graph_constraints=tuple(
            str(value) for value in payload["graph_constraints"]
        ),
        forbidden_expansions=tuple(
            str(value) for value in payload["forbidden_expansions"]
        ),
        candidate_budget=int(payload["candidate_budget"]),
    )


def _request_outcomes(
    *, plan: Mapping[str, Any], selection: Mapping[str, Any]
) -> list[dict[str, Any]]:
    receipt_by_id = {
        str(row["requirement_id"]): row
        for row in selection.get("requirement_receipts") or ()
    }
    output: list[dict[str, Any]] = []
    for group in plan.get("requirement_groups") or ():
        receipt = receipt_by_id[str(group["requirement_id"])]
        output.append(
            {
                "requirement_id": group["requirement_id"],
                "facet_id": group["facet_id"],
                "material_role": group["role"],
                "metric_ids": list(group["metric_ids"]),
                "product_ids": list(group["product_ids"]),
                "period_mode": group["period_mode"],
                "fiscal_years": list(group["fiscal_years"]),
                "complete": bool(receipt["complete"]),
                "selected_candidate_ids": list(
                    receipt["selected_candidate_ids"]
                ),
            }
        )
    return output


def _materialize_request(
    *,
    request_key: str,
    runtime_input: Mapping[str, Any],
    candidate_features: Sequence[tuple[Mapping[str, Any], Sequence[Mapping[str, Any]]]],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
    ontology: Mapping[str, Any],
) -> dict[str, Any]:
    plan, compiler_receipt = compile_material_requirement_plan_from_runtime_input(
        runtime_input=runtime_input,
        policy=policy,
        ontology=ontology,
    )
    request = runtime_input["evidence_request"]
    case_key = str(request["case_key"])
    candidates: list[dict[str, Any]] = []
    for candidate_row, views in candidate_features:
        object_id = str(candidate_row["compiled_object_id"])
        object_row = objects_by_id.get(object_id)
        _require(object_row is not None, f"material_replay_object_missing:{object_id}")
        candidates.append(
            adapt_material_candidate_from_feature_views(
                case_key=case_key,
                candidate_row=candidate_row,
                object_row=object_row,
                feature_views=views,
                evidence_request=request,
                accounting_basis="issuer_reported_candidate_surface",
                policy=policy,
                ontology=ontology,
            )
        )
    selection = select_request_bound_review(candidates=candidates, plan=plan)
    permuted = select_request_bound_review(
        candidates=tuple(reversed(candidates)), plan=plan
    )
    _require(
        permuted["selection_digest"] == selection["selection_digest"],
        f"material_replay_permutation_instability:{request_key}",
    )
    outcomes = _request_outcomes(plan=plan, selection=selection)
    return {
        "request_key": request_key,
        "case_key": case_key,
        "request_id": request["request_id"],
        "compiler_receipt": compiler_receipt,
        "requirement_plan": plan,
        "candidate_metadata": candidates,
        "selection": selection,
        "requirement_outcomes": outcomes,
        "summary": {
            "requirement_count": len(outcomes),
            "met_requirement_count": sum(row["complete"] for row in outcomes),
            "unmet_requirement_count": sum(not row["complete"] for row in outcomes),
            "selected_candidate_count": len(selection["selected_candidate_ids"]),
            "hard_boundary_rejected_candidate_count": len(
                selection["hard_boundary_rejected_candidate_ids"]
            ),
            "request_alignment_excluded_candidate_count": len(
                selection["request_alignment_excluded_candidate_ids"]
            ),
            "permutation_stable": True,
            "explicit_blueprint_required_for_full_product_scope": bool(
                compiler_receipt[
                    "explicit_blueprint_required_for_full_product_scope"
                ]
            ),
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_fact_authority": False,
            "numeric_relation_authority": False,
            "generation_model_calls": 0,
            "network_calls": 0,
            "s1_qualification_claimed": False,
        },
    }


def _vs4_requests(
    *,
    atom_path: Path,
    full_path: Path,
    objects_by_id: Mapping[str, Mapping[str, Any]],
    kernel: Any,
    ontology: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    atoms = {atom.atom_id: atom for atom in load_query_atoms(_read_json(atom_path))}
    full = _read_json(full_path)
    output: list[dict[str, Any]] = []
    for raw in full.get("atoms") or ():
        atom_id = str(raw.get("atom_id") or "")
        atom = atoms.get(atom_id)
        _require(atom is not None, f"material_replay_query_atom_missing:{atom_id}")
        request, lane = compile_atom_lane(atom, kernel)
        needs = list((raw.get("retrieval_need_set") or {}).get("needs") or ())
        _require(needs, f"material_replay_retrieval_needs_missing:{atom_id}")
        candidate_ids = [str(value) for value in raw.get("candidate_union_ids") or ()]
        _require(candidate_ids, f"material_replay_candidate_union_missing:{atom_id}")
        rank_maps = _cross_rank_maps(raw.get("reranker_ranked_ids") or {})
        shortlist = rank_financial_evidence_shortlist(
            union_object_ids=candidate_ids,
            objects_by_id=objects_by_id,
            lane=lane,
            route_membership=raw.get("route_membership") or {},
            cross_encoder_ranks_by_id={
                object_id: {
                    route_id: ranks.get(object_id)
                    for route_id, ranks in rank_maps.items()
                }
                for object_id in candidate_ids
            },
            request=atom.request_payload,
            intent_ontology=ontology,
            retrieval_needs=needs,
        )
        # Material-set reservation must run before the review window is cut.
        # Otherwise a scarce counterexample at rank 21+ can never displace
        # redundant direct-result rows already occupying the top-k.
        top_rows = list(shortlist)
        features = []
        membership = raw.get("route_membership") or {}
        for rank, best_feature in enumerate(top_rows, 1):
            object_id = str(best_feature["compiled_object_id"])
            object_row = objects_by_id[object_id]
            route_rows = list(membership.get(object_id) or ())
            views: list[dict[str, Any]] = []
            for need in needs:
                need_id = str(need.get("need_id") or "")
                need_routes = [
                    row
                    for row in route_rows
                    if str(row.get("need_id") or "") == need_id
                ]
                if not need_routes:
                    continue
                feature = candidate_shortlist_features_v1(
                    object_row,
                    lane=lane,
                    route_rows=need_routes,
                    union_rank=rank,
                    cross_encoder_ranks={
                        route_id: ranks.get(object_id)
                        for route_id, ranks in rank_maps.items()
                    },
                    request=atom.request_payload,
                    intent_ontology=ontology,
                    retrieval_needs=(need,),
                )
                views.append({"facet_id": lane.facet_id, "feature": feature})
            if not views:
                views.append({"facet_id": lane.facet_id, "feature": best_feature})
            features.append((_candidate_row(best_feature, rank=rank), views))
        runtime_input = {
            "evidence_request": request.as_dict(),
            "retrieval_execution_plan": {
                "narrative_requests": [
                    {
                        "facet_ids": [lane.facet_id],
                        "metric_context_ids": list(request.metric_intents),
                        "product_intents": list(request.product_intents),
                    }
                ]
            },
        }
        output.append(
            _materialize_request(
                request_key=atom_id,
                runtime_input=runtime_input,
                candidate_features=features,
                objects_by_id=objects_by_id,
                policy=policy,
                ontology=ontology,
            )
        )
    return output


def _cost_requests(
    *,
    inputs_path: Path,
    raw_path: Path,
    objects_by_id: Mapping[str, Mapping[str, Any]],
    ontology: Mapping[str, Any],
    need_policy: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    inputs = {str(row["example_id"]): row for row in _read_jsonl(inputs_path)}
    raw = _read_json(raw_path)
    output: list[dict[str, Any]] = []
    for proposition in raw.get("propositions") or ():
        example_id = str(proposition.get("example_id") or "")
        example = inputs.get(example_id)
        _require(example is not None, f"material_replay_cost_input_missing:{example_id}")
        runtime_input = example["runtime_input"]
        request = _bound_evidence_request(runtime_input["evidence_request"])
        query_plan = runtime_input.get("query_facet_plan") or {}
        _require(
            isinstance(query_plan, Mapping) and query_plan.get("lanes"),
            f"material_replay_cost_query_plan_missing:{example_id}",
        )
        needs_by_id: dict[str, tuple[Any, Any]] = {}
        for lane_payload in query_plan["lanes"]:
            lane = _bound_query_lane(lane_payload)
            lane_request_payload = request.as_dict()
            lane_request_payload["requested_facet_ids"] = [lane.facet_id]
            lane_request = _bound_evidence_request(lane_request_payload)
            need_set = compile_retrieval_needs(
                request=lane_request,
                lane=lane,
                policy=need_policy,
                intent_ontology=ontology,
            )
            for need in need_set.needs:
                needs_by_id[need.need_id] = (lane, need)
        role_by_id = {
            str(row["compiled_object_id"]): row
            for row in proposition.get("role_evaluations") or ()
        }
        feature_inputs = []
        for candidate_row in proposition.get("final_shortlist") or ():
            object_id = str(candidate_row.get("compiled_object_id") or "")
            object_row = objects_by_id.get(object_id)
            role_row = role_by_id.get(object_id)
            _require(
                object_row is not None and role_row is not None,
                f"material_replay_cost_candidate_join_missing:{example_id}:{object_id}",
            )
            views: list[dict[str, Any]] = []
            for evaluation in role_row.get("evaluations") or ():
                need_id = str(evaluation.get("need_id") or "")
                joined = needs_by_id.get(need_id)
                if joined is None:
                    continue
                lane, need = joined
                feature = candidate_shortlist_features_v2(
                    object_row,
                    lane=lane,
                    route_rows=(
                        {
                            "need_id": need_id,
                            "route_id": "qwen3_reranker_0_6b",
                            "rank": int(candidate_row["rank"]),
                        },
                    ),
                    union_rank=int(candidate_row["rank"]),
                    cross_encoder_ranks={
                        "qwen3_reranker_0_6b": int(candidate_row["rank"])
                    },
                    request=request.as_dict(),
                    intent_ontology=ontology,
                    retrieval_needs=(need.as_dict(),),
                )
                views.append({"facet_id": lane.facet_id, "feature": feature})
            feature_inputs.append((candidate_row, views))
        output.append(
            _materialize_request(
                request_key=example_id,
                runtime_input=runtime_input,
                candidate_features=feature_inputs,
                objects_by_id=objects_by_id,
                policy=policy,
                ontology=ontology,
            )
        )
    return output


def _case_summary(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for case_key in sorted({str(row["case_key"]) for row in rows}):
        case_rows = [row for row in rows if row["case_key"] == case_key]
        scope_blocked = [
            {
                "request_key": row["request_key"],
                "unclassified_product_intents": row["compiler_receipt"][
                    "unclassified_product_intents_excluded_from_hard_material_scope"
                ],
            }
            for row in case_rows
            if row["summary"][
                "explicit_blueprint_required_for_full_product_scope"
            ]
        ]
        unmet = [
            {
                "request_key": row["request_key"],
                **outcome,
            }
            for row in case_rows
            for outcome in row["requirement_outcomes"]
            if not outcome["complete"]
        ]
        output.append(
            {
                "case_key": case_key,
                "request_count": len(case_rows),
                "requirement_count": sum(
                    row["summary"]["requirement_count"] for row in case_rows
                ),
                "met_requirement_count": sum(
                    row["summary"]["met_requirement_count"] for row in case_rows
                ),
                "unmet_requirement_count": len(unmet),
                "unmet_requirements": unmet,
                "material_set_complete_request_count": sum(
                    row["summary"]["unmet_requirement_count"] == 0
                    for row in case_rows
                ),
                "explicit_blueprint_required_request_count": len(scope_blocked),
                "scope_blocked_requests": scope_blocked,
                "runtime_scope_ready_request_count": sum(
                    row["summary"]["unmet_requirement_count"] == 0
                    and not row["summary"][
                        "explicit_blueprint_required_for_full_product_scope"
                    ]
                    for row in case_rows
                ),
                "all_requests_permutation_stable": all(
                    row["summary"]["permutation_stable"] for row in case_rows
                ),
            }
        )
    return output


def _run(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = {
        key: _resolve(value)
        for key, value in {
            "policy": args.policy,
            "ontology": args.ontology,
            "kernel": args.kernel,
            "need_policy": args.need_policy,
            "dell_atoms": args.dell_atoms,
            "dell_full": args.dell_full,
            "mu_nvda_atoms": args.mu_nvda_atoms,
            "mu_nvda_full": args.mu_nvda_full,
            "vs4_objects": args.vs4_objects,
            "cost_inputs": args.cost_inputs,
            "cost_raw": args.cost_raw,
            "cost_objects": args.cost_objects,
        }.items()
    }
    for key, path in paths.items():
        _require(path.is_file(), f"material_replay_bound_input_missing:{key}")
    policy = _read_json(paths["policy"])
    ontology = _read_json(paths["ontology"])
    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    need_policy = _read_json(paths["need_policy"])
    _, vs4_objects_by_id = _objects(paths["vs4_objects"])
    _, cost_objects_by_id = _objects(paths["cost_objects"])
    requests = [
        *_vs4_requests(
            atom_path=paths["dell_atoms"],
            full_path=paths["dell_full"],
            objects_by_id=vs4_objects_by_id,
            kernel=kernel,
            ontology=ontology,
            policy=policy,
        ),
        *_vs4_requests(
            atom_path=paths["mu_nvda_atoms"],
            full_path=paths["mu_nvda_full"],
            objects_by_id=vs4_objects_by_id,
            kernel=kernel,
            ontology=ontology,
            policy=policy,
        ),
        *_cost_requests(
            inputs_path=paths["cost_inputs"],
            raw_path=paths["cost_raw"],
            objects_by_id=cost_objects_by_id,
            ontology=ontology,
            need_policy=need_policy,
            policy=policy,
        ),
    ]
    bound_inputs = {
        key: {"ref": _relative(path), "sha256": _sha256(path)}
        for key, path in sorted(paths.items())
    }
    full: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA,
        "status": "four_case_zero_call_runtime_replay_complete",
        "recorded_at": RECORDED_AT,
        "bound_inputs": bound_inputs,
        "requests": requests,
        "case_summaries": _case_summary(requests),
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_fact_authority": False,
            "numeric_relation_authority": False,
            "generation_model_calls": 0,
            "network_calls": 0,
            "qrel_or_reference_inputs_read": False,
            "s1_qualification_claimed": False,
            "hidden_or_holdout_inputs_read": False,
        },
    }
    full["result_digest"] = canonical_digest(full)
    public: dict[str, Any] = {
        "schema_version": PUBLIC_SCHEMA,
        "status": "four_case_zero_call_runtime_replay_complete_not_s1_qualification",
        "recorded_at": RECORDED_AT,
        "result_digest": full["result_digest"],
        "case_summaries": full["case_summaries"],
        "authority": full["authority"],
        "interpretation_zh": (
            "本结果仅证明当前真实请求、已保存候选和金融对象能够通过同一材料集合合同回放；"
            "未读取 qrels/标准答案，未晋升 Evidence，未授予 NumericFact，也不代表 S1 通过。"
        ),
    }
    return full, public


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay request-bound material evidence selection without network, vectors or models."
    )
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--ontology", default=DEFAULT_ONTOLOGY)
    parser.add_argument("--kernel", default=DEFAULT_KERNEL)
    parser.add_argument("--need-policy", default=DEFAULT_NEED_POLICY)
    parser.add_argument("--dell-atoms", default=DEFAULT_DELL_ATOMS)
    parser.add_argument("--dell-full", default=DEFAULT_DELL_FULL)
    parser.add_argument("--mu-nvda-atoms", default=DEFAULT_MU_NVDA_ATOMS)
    parser.add_argument("--mu-nvda-full", default=DEFAULT_MU_NVDA_FULL)
    parser.add_argument("--vs4-objects", default=DEFAULT_VS4_OBJECTS)
    parser.add_argument("--cost-inputs", default=DEFAULT_COST_INPUTS)
    parser.add_argument("--cost-raw", default=DEFAULT_COST_RAW)
    parser.add_argument("--cost-objects", default=DEFAULT_COST_OBJECTS)
    parser.add_argument("--private-output", default=DEFAULT_PRIVATE_OUTPUT)
    parser.add_argument("--public-output", default=DEFAULT_PUBLIC_OUTPUT)
    args = parser.parse_args()
    full, public = _run(args)
    private_path = _resolve(args.private_output)
    public_path = _resolve(args.public_output)
    _write_json(private_path, full)
    public["storage"] = {
        "full_result_ref": _relative(private_path),
        "full_result_sha256": _sha256(private_path),
    }
    public["summary_digest"] = canonical_digest(public)
    _write_json(public_path, public)
    print(
        json.dumps(
            {
                "status": public["status"],
                "result_digest": full["result_digest"],
                "private_output": _relative(private_path),
                "public_output": _relative(public_path),
                "case_summaries": full["case_summaries"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
