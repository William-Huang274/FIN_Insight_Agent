from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from apps.workbench.backend.application.bounded_agent_executor import (
    S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF,
    S3ThreeCellBoundedAgentInputPack,
    build_s4_source_grounded_bounded_agent_input,
)
from apps.workbench.backend.application.bounded_agent_contract_policies import (
    FIN_0_1_2_S4_T05_DELL_CURRENT_EVIDENCE_PROFILE_REF,
    FIN_0_1_2_S4_T05_MU_CURRENT_EVIDENCE_PROFILE_REF,
    bounded_research_profile_contract_payload,
    research_profile_for_ref,
)
from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (
    load_current_fin_0_1_2_s4_t01_case_entry,
)
from apps.workbench.backend.application.fin_0_1_2_s4_retrieval_evidence_readiness import (
    load_current_fin_0_1_2_s4_t02_readiness,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    CASE_SEARCH_PROFILES,
    CASE_QUERY_TEXT,
    TRANSFER_PROFILE_RELATIVE_PATH,
    compile_current_case_executable_requests,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t04_current_evidence_research import (
    validate_current_case_evidence_pack,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import (
    S4_RUNTIME_CONSUMER_IDS,
    apply_s4_case_runtime_research_profile_overlay,
    consume_s4_case_runtime_binding,
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)


CONTRACT_REF = "fin_0_1_2.S4.T05.three_case_current_evidence_transfer:v1"
EXPECTED_CASES = ("DELL", "MU", "NVDA")
ZERO_CALL_OBSERVED_COUNTS = {
    "model_calls": 0,
    "provider_calls": 0,
    "network_calls": 0,
    "source_network_calls": 0,
    "external_tool_calls": 0,
    "business_artifacts": 0,
}


class Fin012S4T05TransferError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "configs").is_dir() and (parent / "src").is_dir():
            return parent
    raise Fin012S4T05TransferError("s4_t05_repository_root_not_found")


def load_transfer_profile_contract(
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve() if repository_root else _repository_root()
    path = root / TRANSFER_PROFILE_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Fin012S4T05TransferError("s4_t05_profile_contract_unreadable") from exc
    digest_payload = dict(payload)
    observed_digest = str(digest_payload.pop("profiles_digest", ""))
    rows = payload.get("cases")
    if (
        payload.get("contract_ref") != CONTRACT_REF
        or observed_digest != canonical_digest(digest_payload)
        or not isinstance(rows, list)
        or tuple(str(row.get("case_key") or "") for row in rows) != EXPECTED_CASES
    ):
        raise Fin012S4T05TransferError("s4_t05_profile_contract_invalid")
    return payload


def _case_profile(contract: Mapping[str, Any], case_key: str) -> Mapping[str, Any]:
    if case_key not in EXPECTED_CASES:
        raise Fin012S4T05TransferError("s4_t05_case_unsupported")
    rows = [row for row in contract["cases"] if row.get("case_key") == case_key]
    if len(rows) != 1:
        raise Fin012S4T05TransferError("s4_t05_case_profile_cardinality_invalid")
    return rows[0]


def compile_case_transfer_surface(
    case_key: str,
    *,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    """Bind T01/T02, executable search and one immutable regression oracle.

    This compiler performs no retrieval, source access, model call or write.  The
    oracle proves compatibility only and is never promoted as current evidence.
    """

    root = Path(repository_root).resolve() if repository_root else _repository_root()
    contract = load_transfer_profile_contract(root)
    profile = _case_profile(contract, case_key)
    t01 = load_current_fin_0_1_2_s4_t01_case_entry(case_key)
    t02 = load_current_fin_0_1_2_s4_t02_readiness(case_key)
    requests = compile_current_case_executable_requests(case_key)
    code_profile = CASE_SEARCH_PROFILES[case_key]
    if (
        t01.request.as_of != str(profile["as_of"])
        or t02.receipt.case_key != case_key
        or tuple(row.program_cell_id for row in requests)
        != tuple(row.program_cell_id for row in t02.evidence_requests)
        or str(code_profile["cik"]) != str(profile["issuer_cik"])
        or str(code_profile["sec_submissions_url"])
        != str(profile["sec_submissions_url"])
        or str(code_profile["ir_url"]) != str(profile["ir_fallback_url"])
        or tuple(code_profile["allowed_source_hosts"])
        != tuple(profile["allowed_source_hosts"])
        or dict(CASE_QUERY_TEXT[case_key]) != dict(profile["query_text_by_cell"])
    ):
        raise Fin012S4T05TransferError("s4_t05_compiled_profile_drift")
    oracle_path = root / str(profile["regression_oracle_ref"])
    try:
        oracle_sha = hashlib.sha256(oracle_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise Fin012S4T05TransferError("s4_t05_regression_oracle_missing") from exc
    if oracle_sha != str(profile["regression_oracle_sha256"]):
        raise Fin012S4T05TransferError("s4_t05_regression_oracle_digest_mismatch")
    request_rows = [row.as_dict() for row in requests]
    body = {
        "contract_ref": CONTRACT_REF,
        "case_key": case_key,
        "legal_name": str(profile["legal_name"]),
        "as_of": t01.request.as_of,
        "t01_entry_digest": t01.receipt.entry_digest,
        "t02_readiness_digest": t02.receipt.readiness_digest,
        "executable_requests": request_rows,
        "executable_request_digests": [row.request_digest for row in requests],
        "official_source_profile": {
            "issuer_cik": str(profile["issuer_cik"]),
            "sec_submissions_url": str(profile["sec_submissions_url"]),
            "ir_fallback_url": str(profile["ir_fallback_url"]),
            "allowed_source_hosts": list(profile["allowed_source_hosts"]),
        },
        "regression_oracle": {
            "ref": str(profile["regression_oracle_ref"]),
            "sha256": oracle_sha,
            "current_product_proof": False,
            "declared_current_product_proof": bool(
                profile["regression_oracle_is_current_product_proof"]
            ),
        },
        "search_and_gate_budget": {
            key: value
            for key, value in contract["shared_transfer_contract"].items()
            if key
            in {
                "candidate_ceiling_per_cell",
                "source_network_call_ceiling",
                "local_invocation_ceiling",
                "same_target_retry_ceiling",
                "fallback_ceiling",
                "model_calls_in_search_and_gate",
                "provider_calls_in_search_and_gate",
            }
        },
        "nonpromotion_boundary": {
            "live_source_calls_authorized": False,
            "model_calls_authorized": False,
            "provider_calls_authorized": False,
            "regression_oracle_promoted": False,
            "product_acceptance_changed": False,
        },
        "observed_counts": dict(ZERO_CALL_OBSERVED_COUNTS),
    }
    return {**body, "transfer_surface_digest": canonical_digest(body)}


def compile_legacy_oracle_agent_input(
    case_key: str,
    *,
    repository_root: str | Path | None = None,
) -> S3ThreeCellBoundedAgentInputPack:
    """Compile DELL/MU legacy facts only as a shared-runtime regression oracle."""

    if case_key not in {"DELL", "MU"}:
        raise Fin012S4T05TransferError("s4_t05_legacy_oracle_case_unsupported")
    root = Path(repository_root).resolve() if repository_root else _repository_root()
    entry = load_current_fin_0_1_2_s4_t01_case_entry(case_key)
    built = build_s4_source_grounded_bounded_agent_input(
        load_s4_case_runtime_binding(root, case_key),
        load_s4_source_grounded_input_pack(root, case_key),
        case_id=f"fin012-s4-t05-{case_key.lower()}-regression-oracle",
        case_version=1,
        decision_surface_contract_ref=(
            "fin_0_1_2.S4.T05.legacy_oracle_shared_runtime_regression:v1"
        ),
        query=entry.request.objective,
    )
    if built.company != case_key or built.as_of != entry.request.as_of:
        raise Fin012S4T05TransferError("s4_t05_legacy_oracle_identity_mismatch")
    return built


def validate_transfer_evidence_pack(
    pack: Mapping[str, Any], *, case_key: str
) -> dict[str, Any]:
    return validate_current_case_evidence_pack(pack, case_key=case_key)


def _current_numeric_input(
    rows: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    *,
    case_key: str,
) -> dict[str, Any]:
    if (
        len(rows) != 3
        or {str(row.get("metric_family") or "") for row in rows}
        != {"revenue", "gross_profit", "operating_income"}
    ):
        raise Fin012S4T05TransferError("s4_t05_current_numeric_topology_invalid")
    selected: list[dict[str, Any]] = []
    by_family: dict[str, dict[str, Any]] = {}
    for current in sorted(rows, key=lambda row: str(row["metric_family"])):
        if current.get("entity_ref") != case_key:
            raise Fin012S4T05TransferError("s4_t05_current_numeric_identity_invalid")
        body = {
            "entity_ref": case_key,
            "segment_ref": "__company_total__",
            "program_cell_ids": ["value_and_profit_capture"],
            "metric_family": str(current["metric_family"]),
            "value": str(current["value"]),
            "comparison_operator": "reported_exact",
            "currency": str(current["unit"]),
            "unit": str(current["unit"]),
            "scale_multiplier": 1,
            "period": str(current["period"]),
            "source_ref": str(current["numeric_ref"]),
            "source_url": str(current["source_url"]),
            "source_coordinate": str(current["source_coordinate"]),
            "parser_lineage": {
                "source_snapshot_ref": str(current["source_snapshot_ref"]),
                "source_snapshot_digest": str(current["source_snapshot_digest"]),
                "adapter": str(current["parser_adapter"]),
                "parser_digest": str(current["parser_digest"]),
            },
            "exact_value_authority": True,
            "cannot_support": [
                "segment_or_product_attribution",
                "forward_estimate",
            ],
            "numeric_ref": str(current["numeric_ref"]),
        }
        selected.append(body)
        by_family[body["metric_family"]] = body
    revenue = Decimal(by_family["revenue"]["value"])
    if revenue == 0:
        raise Fin012S4T05TransferError("s4_t05_current_revenue_zero")
    derived: list[dict[str, Any]] = []
    for metric, numerator in (
        ("gross_margin_percent", "gross_profit"),
        ("operating_margin_percent", "operating_income"),
    ):
        value = (Decimal(by_family[numerator]["value"]) / revenue * 100).quantize(
            Decimal("0.0001")
        )
        body = {
            "metric": metric,
            "value": format(value, "f"),
            "unit": "percent",
            "formula": f"{numerator} / revenue * 100",
            "input_numeric_refs": [
                by_family[numerator]["numeric_ref"],
                by_family["revenue"]["numeric_ref"],
            ],
            "program_cell_ids": ["value_and_profit_capture"],
            "scope": "consolidated_company_total_only",
            "cannot_support": ["segment_or_product_margin"],
        }
        derived.append(
            {
                **body,
                "derived_metric_ref": (
                    f"s4_t05_current_derived_{canonical_digest(body)[:24]}"
                ),
            }
        )
    return {
        "fundamental_decision_cell": {
            "program_cell_id": "value_and_profit_capture",
            "availability": "current_exact_company_total_numeric_with_typed_gap",
            "typed_cannot_infer": [str(row["gap_code"]) for row in gaps],
            "support_boundary": (
                "Current exact company totals do not establish segment, product, "
                "causal or forward-looking profit attribution."
            ),
            "specialist_input_eligible": True,
            "narrative_fill_authorized": False,
        },
        "selected_financial_rows": selected,
        "derived_metrics": derived,
    }


def compile_current_case_agent_input(
    baseline: S3ThreeCellBoundedAgentInputPack,
    pack: Mapping[str, Any],
    *,
    case_key: str,
) -> S3ThreeCellBoundedAgentInputPack:
    """Replace every legacy factual surface with one current T03/T04 pack."""

    current = validate_transfer_evidence_pack(pack, case_key=case_key)
    entry = load_current_fin_0_1_2_s4_t01_case_entry(case_key)
    if baseline.company != case_key or entry.request.case_key != case_key:
        raise Fin012S4T05TransferError("s4_t05_agent_input_case_mismatch")
    cells: list[dict[str, Any]] = []
    for base in baseline.cell_inputs:
        cell_id = str(base["program_cell_id"])
        evidence = [
            deepcopy(dict(row))
            for row in current["evidence_rows"]
            if cell_id in row.get("program_cell_ids", ())
        ]
        numeric = [
            deepcopy(dict(row))
            for row in current["numeric_rows"]
            if cell_id in row.get("program_cell_ids", ())
        ]
        gaps = [
            deepcopy(dict(row))
            for row in current["typed_gaps"]
            if cell_id in row.get("program_cell_ids", ())
        ]
        evidence_refs = sorted(str(row["evidence_ref"]) for row in evidence)
        numeric_refs = sorted(str(row["numeric_ref"]) for row in numeric)
        cell = deepcopy(dict(base))
        cell["runtime_branch"]["branch_state"] = (
            "current_source_grounded_exact_input_ready"
        )
        cell["runtime_branch"]["observation"] = {
            "accepted_evidence_count": len(evidence),
            "exact_numeric_count": len(numeric),
            "typed_gap_count": len(gaps),
        }
        cell["role_contexts"] = [
            {
                "target_node": "domain_specialist",
                "authority": {
                    "case_ticker": case_key,
                    "current_evidence_pack_digest": current["evidence_pack_digest"],
                    "source_or_numeric_rows_admitted": len(evidence) + len(numeric),
                },
            },
            {
                "target_node": "evidence_operator",
                "authority": {
                    "T03_terminal_digest": current["t03_terminal_digest"],
                    "network_execution_authorized": False,
                },
            },
        ]
        cell["evidence_input"] = {
            "program_cell_id": cell_id,
            "route_outcome": "T03_current_rows_promoted_by_T05_gate",
            "candidate_bundle": {
                "status": "current_source_grounded_rows_approved",
                "candidates": evidence,
                "candidate_count": len(evidence),
            },
            "promotion_assessment": {
                "decision": "accept_current_issuer_bound_rows_only",
                "accepted_evidence_refs": evidence_refs,
                "numeric_refs": numeric_refs,
                "typed_gap_codes": [str(row["gap_code"]) for row in gaps],
                "runtime_promotion_authorized": True,
                "writer_citable": True,
                "judgment_eligible": True,
                "persistence_authorized": False,
            },
            "sourcehunter_boundary": {
                "status": "already_executed_in_bound_T03_terminal",
                "terminal_digest": current["t03_terminal_digest"],
                "exact_network_admission_required": False,
                "network_execution_authorized": False,
                "external_tool_execution_authorized": False,
            },
        }
        cell["numeric_input"] = (
            _current_numeric_input(numeric, gaps, case_key=case_key)
            if cell_id == "value_and_profit_capture"
            else {
                "fundamental_decision_cell": {
                    "program_cell_id": cell_id,
                    "availability": "typed_cannot_infer",
                    "typed_cannot_infer": [str(row["gap_code"]) for row in gaps],
                    "support_boundary": "No exact numeric row is authorized for this Cell.",
                    "specialist_input_eligible": True,
                    "narrative_fill_authorized": False,
                },
                "selected_financial_rows": [],
                "derived_metrics": [],
            }
        )
        cell["graph_context_input"] = {
            "decision_cell": {
                "program_cell_id": cell_id,
                "typed_gaps": [str(row["gap_code"]) for row in gaps],
            },
            "product_industry_inputs": [],
            "skill_contracts": [],
            "graph_edges": [],
            "market_price_in_contexts": [],
            "risk_contexts": [
                row
                for row in evidence
                if row.get("evidence_role") == "issuer_counterevidence"
            ],
        }
        cell["authority_refs"] = {
            "accepted_evidence_refs": evidence_refs,
            "numeric_refs": numeric_refs,
            "candidate_refs_not_evidence": [],
            "graph_context_refs_not_evidence": [],
        }
        cell.pop("s4_case_method", None)
        cells.append(cell)
    if sorted(str(row["program_cell_id"]) for row in cells) != sorted(
        row["program_cell_id"] for row in entry.request.program_cells
    ):
        raise Fin012S4T05TransferError("s4_t05_agent_input_cell_topology_invalid")
    runtime_payload: dict[str, Any] | None = None
    if case_key in {"DELL", "MU"}:
        root = _repository_root()
        base_binding = load_s4_case_runtime_binding(root, case_key)
        profile = research_profile_for_ref(
            {
                "DELL": FIN_0_1_2_S4_T05_DELL_CURRENT_EVIDENCE_PROFILE_REF,
                "MU": FIN_0_1_2_S4_T05_MU_CURRENT_EVIDENCE_PROFILE_REF,
            }[case_key]
        )
        binding, overlay = apply_s4_case_runtime_research_profile_overlay(
            base_binding,
            research_profile_ref=profile.profile_ref,
            research_profile_contract_payload=(
                bounded_research_profile_contract_payload(profile)
            ),
        )
        source_payload = deepcopy(dict(current))
        source_payload["source_pack_digest"] = str(
            current["evidence_pack_digest"]
        )
        runtime_payload = {
            "binding": binding.model_dump(mode="json"),
            "source_grounded_input": source_payload,
            "consumer_injections": {
                consumer_id: consume_s4_case_runtime_binding(
                    binding, consumer_id
                ).model_dump(mode="json")
                for consumer_id in S4_RUNTIME_CONSUMER_IDS
            },
            "research_profile_overlay": overlay.model_dump(mode="json"),
            "paid_execution_authorized": False,
        }
        lineage = {
            "S4_T02_case_pack": {
                "version_ref": binding.case_profile_ref,
                "digest": binding.case_pack_sha256,
            },
            "S4_T02_method_contract": {
                "version_ref": binding.method_contract_ref,
                "digest": binding.method_contract_sha256,
            },
            "S4_T03_runtime_binding": {
                "version_ref": binding.contract_ref,
                "digest": binding.runtime_binding_digest,
            },
            "S4_T04_source_grounded_input": {
                "version_ref": str(current["contract_ref"]),
                "digest": str(current["evidence_pack_digest"]),
            },
            "S4_research_profile_overlay": {
                "version_ref": overlay.contract_ref,
                "digest": overlay.overlay_digest,
            },
        }
    else:
        lineage = deepcopy(baseline.lineage)
        lineage["T02_runtime_plan"] = {
            "version_ref": entry.runtime_binding.contract_ref,
            "digest": entry.receipt.entry_digest,
        }
        lineage["T03_evidence_route_plan"] = {
            "version_ref": "fin_0_1_2.S4.T03.live_current_search_terminal:v1",
            "digest": str(current["t03_terminal_digest"]),
        }
        lineage["T04_financial_pack"] = {
            "version_ref": CONTRACT_REF,
            "digest": str(current["evidence_pack_digest"]),
        }
        lineage["T05_graph_pack"] = {
            "version_ref": "fin_0_1_2.S4.T05.context_only_empty_graph:v1",
            "digest": canonical_digest(
                (current["evidence_pack_digest"], "no_graph_promotion")
            ),
        }
    input_head_digest = canonical_digest(
        (entry.receipt.entry_digest, current["evidence_pack_digest"], baseline.case_id)
    )
    verifier = deepcopy(baseline.verifier_contract)
    verifier.update(
        {
            "input_contract_ref": (
                S4_T04_CURRENT_EVIDENCE_VERIFIER_MODEL_VIEW_CONTRACT_REF
            ),
            "request_capacity_contract_ref": (
                "fin_0_1_2.S4.T05.per_case_node_capacity:v1"
            ),
            "full_local_payload_remains_validation_authority": True,
            "model_view_omits_repeated_runtime_projections_only": True,
        }
    )
    paired = deepcopy(baseline.paired_baseline_contract)
    paired["shared_input_head_digest"] = input_head_digest
    draft = baseline.model_copy(
        update={
            "query": entry.request.objective,
            "as_of": entry.request.as_of,
            "decision_surface_contract_ref": CONTRACT_REF,
            "input_head_digest": input_head_digest,
            "lineage": lineage,
            "cell_inputs": tuple(cells),
            "verifier_contract": verifier,
            "paired_baseline_contract": paired,
            "s4_case_runtime": runtime_payload,
        }
    )
    return draft.model_copy(
        update={
            "input_digest": canonical_digest(
                draft.model_dump(mode="json", exclude={"input_digest"})
            )
        }
    )


__all__ = [
    "CONTRACT_REF",
    "EXPECTED_CASES",
    "Fin012S4T05TransferError",
    "compile_case_transfer_surface",
    "compile_current_case_agent_input",
    "compile_legacy_oracle_agent_input",
    "load_transfer_profile_contract",
    "validate_transfer_evidence_pack",
]
