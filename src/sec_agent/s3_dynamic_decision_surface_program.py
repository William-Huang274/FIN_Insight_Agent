from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.cell_composition import (
    CellArchetype,
    CellCompositionEngine,
    CellCompositionPolicy,
    CellSlotTemplate,
)
from sec_agent.canonical_runtime.planning_service import (
    CompilerInputContract,
    CompilerInputValidationPolicy,
    DecisionSurfacePlanningService,
    PackSelectionDecision,
)
from sec_agent.retrieval_evidence_usefulness_program import canonical_digest


POLICY_SCHEMA = "fin_ia_0_1_3_s3_dynamic_decision_surface_policy_v1_0"
PROGRAM_SCHEMA = "fin_ia_0_1_3_s3_dynamic_decision_surface_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S3.dynamic_decision_surface:v1"
S1_CONTRACT_REF = "fin_0_1_3.S1.retrieval_evidence_usefulness_and_closeout:v1"
S2_CONTRACT_REF = "fin_0_1_3.S2.research_question_method_and_judgment_choice:v1"
CASES = ("DELL", "MU", "NVDA")
REQUIRED_FAMILIES = (
    "accelerator_demand_value_capture_concentration",
    "server_oem_revenue_margin_cash_conversion",
    "foundry_advanced_packaging_capacity_bottleneck_rent",
    "hbm_demand_supply_pricing_concentration",
    "semicap_capex_readthrough_cycle_export_policy",
    "cross_chain_counterthesis_price_in_what_would_change",
)
MANDATORY_PROTECTIONS = (
    "material_numeric_sanity",
    "risk_counterevidence",
    "writer_boundary",
)


class S3DynamicSurfaceError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_s3_dynamic_surface_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or policy.get("s1_contract_ref") != S1_CONTRACT_REF
        or policy.get("s2_contract_ref") != S2_CONTRACT_REF
        or tuple(policy.get("required_families") or ()) != REQUIRED_FAMILIES
        or tuple(policy.get("mandatory_protections") or ())
        != MANDATORY_PROTECTIONS
    ):
        raise S3DynamicSurfaceError("s3_dynamic_surface_policy_identity_invalid")
    minimum = int(policy.get("minimum_cells", 0))
    target_minimum = int(policy.get("target_minimum_cells", 0))
    target_maximum = int(policy.get("target_maximum_cells", 0))
    maximum = int(policy.get("maximum_cells", 0))
    if not 10 <= minimum <= target_minimum <= target_maximum <= maximum <= 20:
        raise S3DynamicSurfaceError("s3_dynamic_surface_cell_range_invalid")
    archetypes = policy.get("base_archetypes")
    if not isinstance(archetypes, list) or not 12 <= len(archetypes) <= 16:
        raise S3DynamicSurfaceError("s3_dynamic_surface_archetype_count_invalid")
    keys = [str(row.get("archetype_id") or "") for row in archetypes]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise S3DynamicSurfaceError("s3_dynamic_surface_archetype_identity_invalid")
    covered: set[str] = set()
    protected: set[str] = set()
    for row in archetypes:
        families = tuple(row.get("family_ids") or ())
        if not families or set(families) - set(REQUIRED_FAMILIES):
            raise S3DynamicSurfaceError("s3_dynamic_surface_family_invalid")
        covered.update(families)
        protected.update(row.get("protection_tags") or ())
        if (
            not row.get("question_template")
            or not row.get("owner_role")
            or not row.get("stop_rule")
            or not row.get("what_would_change")
            or not row.get("slots")
        ):
            raise S3DynamicSurfaceError("s3_dynamic_surface_archetype_incomplete")
    if covered != set(REQUIRED_FAMILIES):
        raise S3DynamicSurfaceError("s3_dynamic_surface_required_family_missing")
    if not set(MANDATORY_PROTECTIONS).issubset(protected):
        raise S3DynamicSurfaceError("s3_dynamic_surface_protection_missing")
    return policy


def compile_s3_dynamic_surface_program(
    *,
    policy: Mapping[str, Any],
    s1_decision: Mapping[str, Any],
    s2_policy: Mapping[str, Any],
    s2_decision: Mapping[str, Any],
) -> dict[str, Any]:
    _assert_upstream(policy, s1_decision, s2_policy, s2_decision)
    surfaces = [
        _compile_case_surface(
            case_key=case_key,
            policy=policy,
            s1_decision=s1_decision,
            s2_policy=s2_policy,
        )
        for case_key in CASES
    ]
    review_proofs = [_compile_review_proof(surface, policy=policy) for surface in surfaces]
    observed = {
        "case_count": len(surfaces),
        "cell_counts": {row["case_key"]: len(row["cells"]) for row in surfaces},
        "family_coverage": {
            row["case_key"]: len(
                {family for cell in row["cells"] for family in cell["family_ids"]}
            )
            for row in surfaces
        },
        "upstream_evidence_alias_count": sum(
            len(cell["evidence_binding"]["evidence_aliases"])
            for row in surfaces
            for cell in row["cells"]
        ),
        "upstream_typed_gap_alias_count": sum(
            len(cell["evidence_binding"]["gap_aliases"])
            for row in surfaces
            for cell in row["cells"]
        ),
        "review_proof_count": len(review_proofs),
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
        "s1_record_digest": s1_decision["record_digest"],
        "s2_record_digest": s2_decision["record_digest"],
        "surfaces": surfaces,
        "review_proofs": review_proofs,
        "observed_counts": observed,
        "stage_boundary": {
            "S3_01": "engineering_pass_dynamic_plan_fixture_proven",
            "current_authority": "zero_call_current_governed_pack_compilation",
            "historical_ten_cell_shadow_promoted": False,
            "S3_02_semantic_judgment_quality": "not_started",
            "lead_writer_verifier_full_chain": False,
            "product_acceptance": False,
            "release": False,
        },
    }
    program = {**body, "program_digest": canonical_digest(body)}
    validate_s3_dynamic_surface_program(
        program,
        policy=policy,
        s1_decision=s1_decision,
        s2_policy=s2_policy,
        s2_decision=s2_decision,
    )
    return program


def validate_s3_dynamic_surface_program(
    program: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    s1_decision: Mapping[str, Any],
    s2_policy: Mapping[str, Any],
    s2_decision: Mapping[str, Any],
) -> None:
    _assert_upstream(policy, s1_decision, s2_policy, s2_decision)
    if (
        program.get("schema_version") != PROGRAM_SCHEMA
        or program.get("contract_ref") != CONTRACT_REF
        or program.get("policy_digest") != canonical_digest(policy)
        or program.get("s1_record_digest") != s1_decision["record_digest"]
        or program.get("s2_record_digest") != s2_decision["record_digest"]
    ):
        raise S3DynamicSurfaceError("s3_dynamic_surface_program_binding_invalid")
    body = {key: deepcopy(value) for key, value in program.items() if key != "program_digest"}
    if program.get("program_digest") != canonical_digest(body):
        raise S3DynamicSurfaceError("s3_dynamic_surface_program_digest_invalid")
    surfaces = program.get("surfaces") or []
    if [row.get("case_key") for row in surfaces] != list(CASES):
        raise S3DynamicSurfaceError("s3_dynamic_surface_case_scope_invalid")
    for surface in surfaces:
        validate_dynamic_surface(surface, policy=policy)
    proofs = program.get("review_proofs") or []
    if len(proofs) != 3 or any(row.get("status") != "pass" for row in proofs):
        raise S3DynamicSurfaceError("s3_dynamic_surface_review_proof_invalid")
    observed = program.get("observed_counts") or {}
    if (
        observed.get("cell_counts") != {"DELL": 13, "MU": 12, "NVDA": 13}
        or set(observed.get("family_coverage") or {}) != set(CASES)
        or any(value != 6 for value in observed["family_coverage"].values())
        or observed.get("upstream_evidence_alias_count") != 26
        or observed.get("upstream_typed_gap_alias_count") != 2
        or any(observed.get(key) != 0 for key in ("model_calls", "provider_calls", "network_calls", "source_calls", "business_runs"))
    ):
        raise S3DynamicSurfaceError("s3_dynamic_surface_observed_counts_invalid")


def validate_dynamic_surface(surface: Mapping[str, Any], *, policy: Mapping[str, Any]) -> None:
    case_key = str(surface.get("case_key") or "")
    if case_key not in CASES or str(surface.get("case_id") or "") != f"FIN013-{case_key}":
        raise S3DynamicSurfaceError("s3_dynamic_surface_case_identity_invalid")
    cells = surface.get("cells") or []
    count = len(cells)
    if not int(policy["minimum_cells"]) <= count <= int(policy["maximum_cells"]):
        raise S3DynamicSurfaceError("s3_dynamic_surface_count_out_of_range")
    keys = [str(cell.get("cell_key") or "") for cell in cells]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise S3DynamicSurfaceError("s3_dynamic_surface_cell_identity_invalid")
    families: set[str] = set()
    protections: set[str] = set()
    company_anchor = str(surface["company_name"]).split()[0]
    for cell in cells:
        if (
            not cell.get("decision_question")
            or not cell.get("owner_role")
            or not cell.get("evidence_slots")
            or not cell.get("stop_rule")
            or not cell.get("what_would_change")
        ):
            raise S3DynamicSurfaceError("s3_dynamic_surface_cell_incomplete")
        if company_anchor.lower() not in str(cell["decision_question"]).lower():
            raise S3DynamicSurfaceError("s3_dynamic_surface_question_not_case_bound")
        families.update(cell.get("family_ids") or ())
        protections.update(cell.get("protection_tags") or ())
        if set(cell.get("dependency_cell_keys") or ()) - set(keys):
            raise S3DynamicSurfaceError("s3_dynamic_surface_dependency_missing")
        binding = cell.get("evidence_binding") or {}
        if binding.get("case_key") != case_key:
            raise S3DynamicSurfaceError("s3_dynamic_surface_cross_case_binding")
    if families != set(REQUIRED_FAMILIES):
        raise S3DynamicSurfaceError("s3_dynamic_surface_family_coverage_invalid")
    if not set(MANDATORY_PROTECTIONS).issubset(protections):
        raise S3DynamicSurfaceError("s3_dynamic_surface_mandatory_protection_invalid")
    digest_body = {key: deepcopy(value) for key, value in surface.items() if key != "surface_digest"}
    if surface.get("surface_digest") != canonical_digest(digest_body):
        raise S3DynamicSurfaceError("s3_dynamic_surface_digest_invalid")


def revise_dynamic_surface(
    surface: Mapping[str, Any],
    *,
    actions: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    validate_dynamic_surface(surface, policy=policy)
    revised = deepcopy(dict(surface))
    parent_digest = str(surface["surface_digest"])
    cells = list(revised["cells"])
    for action in actions:
        action_type = str(action.get("action") or "")
        target = str(action.get("target_cell_key") or "")
        if not str(action.get("reason") or "").strip():
            raise S3DynamicSurfaceError("s3_dynamic_surface_review_reason_missing")
        index = next((i for i, cell in enumerate(cells) if cell["cell_key"] == target), None)
        if action_type == "prune":
            if index is None:
                raise S3DynamicSurfaceError("s3_dynamic_surface_review_target_missing")
            if cells[index].get("protection_tags"):
                raise S3DynamicSurfaceError("s3_dynamic_surface_protected_cell_prune_forbidden")
            candidate = cells[:index] + cells[index + 1 :]
            if not _families_cover(candidate):
                raise S3DynamicSurfaceError("s3_dynamic_surface_family_prune_forbidden")
            cells = candidate
        elif action_type == "split":
            if index is None:
                raise S3DynamicSurfaceError("s3_dynamic_surface_review_target_missing")
            labels = tuple(action.get("split_labels") or ())
            if len(labels) != 2 or any(not str(label).strip() for label in labels):
                raise S3DynamicSurfaceError("s3_dynamic_surface_split_labels_invalid")
            original = cells[index]
            split_cells = []
            for label in labels:
                child = deepcopy(original)
                child["cell_key"] = f"{target}__{_slug(str(label))}"
                child["decision_question"] = f"{original['decision_question']} Review focus: {label}."
                child["origin_type"] = "reviewer_split"
                split_cells.append(child)
            cells[index : index + 1] = split_cells
            _rewrite_dependencies(cells, old_key=target, new_key=split_cells[-1]["cell_key"])
        elif action_type == "add":
            payload = action.get("cell")
            if not isinstance(payload, Mapping):
                raise S3DynamicSurfaceError("s3_dynamic_surface_add_payload_missing")
            cell = deepcopy(dict(payload))
            cell["origin_type"] = "reviewer_added"
            cell.setdefault("protection_tags", [])
            cell.setdefault("dependency_cell_keys", [])
            cell.setdefault("evidence_binding", {"case_key": revised["case_key"], "evidence_aliases": [], "gap_aliases": [], "binding_status": "planned_request"})
            cells.append(cell)
        elif action_type == "return":
            revised["checkpoint_status"] = "returned"
        else:
            raise S3DynamicSurfaceError("s3_dynamic_surface_review_action_invalid")
    revised["cells"] = cells
    revised["revision"] = int(surface.get("revision", 1)) + 1
    revised["parent_surface_digest"] = parent_digest
    revised["review_actions"] = [deepcopy(dict(row)) for row in actions]
    revised["cell_count"] = len(cells)
    revised.pop("surface_digest", None)
    revised["surface_digest"] = canonical_digest(revised)
    validate_dynamic_surface(revised, policy=policy)
    return revised


def _compile_case_surface(
    *, case_key: str, policy: Mapping[str, Any], s1_decision: Mapping[str, Any], s2_policy: Mapping[str, Any]
) -> dict[str, Any]:
    company = str(s2_policy["case_profiles"][case_key]["company_name"])
    query_rows = {
        str(row["cell_id"]): row
        for row in s1_decision["retrieval_usefulness_program"]["query_results"]
        if row["case_key"] == case_key
    }
    pack_refs = ("universal-core:v1", "sector-ai-infrastructure:v2", f"case-delta-{case_key.lower()}:v1")
    archetypes: list[CellArchetype] = []
    metadata: dict[str, dict[str, Any]] = {}
    for raw in policy["base_archetypes"]:
        archetype, meta = _make_archetype(raw, case_key=case_key, company=company, query_rows=query_rows, s2_policy=s2_policy)
        archetypes.append(archetype)
        metadata[archetype.merge_key] = meta
    for cell_id, query in sorted(query_rows.items()):
        for gap in query.get("typed_gaps") or []:
            raw = _gap_archetype(policy["gap_delta_template"], cell_id=cell_id, gap=gap)
            archetype, meta = _make_archetype(raw, case_key=case_key, company=company, query_rows=query_rows, s2_policy=s2_policy)
            archetypes.append(archetype)
            metadata[archetype.merge_key] = meta
    engine = CellCompositionEngine(
        CellCompositionPolicy(
            policy_ref=str(policy["compiler_policy_ref"]),
            minimum_material_cells=int(policy["minimum_cells"]),
            maximum_material_cells=int(policy["maximum_cells"]),
            allowed_owner_roles=tuple(policy["allowed_owner_roles"]),
        )
    )
    composed = engine.compose(case_id=f"FIN013-{case_key}", selected_pack_refs=pack_refs, archetypes=tuple(archetypes))
    cells = []
    for row in composed.cells:
        meta = metadata[row.cell_key]
        cells.append({
            "cell_key": row.cell_key,
            "decision_question": row.seed.decision_question,
            "origin_type": row.seed.origin_type,
            "owner_role": row.seed.owner_role,
            "materiality": row.seed.materiality,
            "family_ids": meta["family_ids"],
            "protection_tags": meta["protection_tags"],
            "dependency_cell_keys": list(row.seed.dependency_cell_keys),
            "evidence_slots": [slot.model_dump(mode="json") for slot in row.seed.evidence_slots],
            "stop_rule": row.seed.stop_rule,
            "what_would_change": list(row.what_would_change),
            "evidence_binding": meta["evidence_binding"],
            "origin_pack_refs": list(row.origin_pack_refs),
        })
    canonical_report = _canonical_validation_report(case_key=case_key, company=company, cells=composed.cells, policy=policy)
    body = {
        "case_id": f"FIN013-{case_key}",
        "case_key": case_key,
        "company_name": company,
        "revision": 1,
        "parent_surface_digest": None,
        "checkpoint_status": "awaiting_review",
        "review_actions": [],
        "selected_pack_refs": list(pack_refs),
        "cell_count": len(cells),
        "target_range": [int(policy["target_minimum_cells"]), int(policy["target_maximum_cells"])],
        "required_families": list(REQUIRED_FAMILIES),
        "cells": cells,
        "composition_digest": composed.composition_digest,
        "canonical_input_validation": canonical_report,
        "model_provider_network_calls": [0, 0, 0],
    }
    surface = {**body, "surface_digest": canonical_digest(body)}
    validate_dynamic_surface(surface, policy=policy)
    return surface


def _make_archetype(
    raw: Mapping[str, Any], *, case_key: str, company: str, query_rows: Mapping[str, Any], s2_policy: Mapping[str, Any]
) -> tuple[CellArchetype, dict[str, Any]]:
    cell_ref = str(raw.get("s2_cell_ref") or "")
    question = str(raw["question_template"]).format(company_name=company, case_key=case_key)
    wwc = tuple(str(value).format(company_name=company, case_key=case_key) for value in raw["what_would_change"])
    binding = {"case_key": case_key, "evidence_aliases": [], "gap_aliases": [], "binding_status": "planned_request"}
    if cell_ref:
        question = str(s2_policy["case_profiles"][case_key]["cells"][cell_ref]["decision_question"])
        wwc = tuple(s2_policy["case_profiles"][case_key]["cells"][cell_ref]["what_would_change_aliases"].values())
        query = query_rows[cell_ref]
        binding = {
            "case_key": case_key,
            "evidence_aliases": [str(row["candidate_id"]) for row in query.get("selected_candidates") or []],
            "gap_aliases": [str(row["gap_code"]) for row in query.get("typed_gaps") or []],
            "binding_status": "current_governed_pack_bound",
        }
    slots = tuple(
        CellSlotTemplate(
            slot_key=str(slot["slot_key"]),
            evidence_role=str(slot["evidence_role"]),
            entity_scope=tuple(str(value).format(company_name=company, case_key=case_key) for value in slot["entity_scope"]),
            period_scope=str(slot["period_scope"]),
            metric_scope=tuple(slot.get("metric_scope") or ()),
            source_policy_ref=str(slot["source_policy_ref"]),
            forbidden_substitutions=tuple(slot["forbidden_substitutions"]),
            acceptance_role=str(slot["acceptance_role"]),
            fact_keys=tuple(slot["fact_keys"]),
            required=bool(slot.get("required", True)),
        )
        for slot in raw["slots"]
    )
    archetype = CellArchetype(
        archetype_id=str(raw["archetype_id"]),
        source_pack_ref=str(raw["source_pack_ref"]).format(case_key=case_key.lower()),
        merge_key=str(raw["merge_key"]),
        decision_question=question,
        owner_role=str(raw["owner_role"]),
        materiality=str(raw.get("materiality", "high")),
        stop_rule=str(raw["stop_rule"]).format(company_name=company, case_key=case_key),
        slots=slots,
        what_would_change=wwc,
        counterevidence_owner_role=str(raw["counterevidence_owner_role"]),
        dependency_merge_keys=tuple(raw.get("dependency_merge_keys") or ()),
    )
    return archetype, {
        "family_ids": list(raw["family_ids"]),
        "protection_tags": list(raw.get("protection_tags") or ()),
        "evidence_binding": binding,
    }


def _gap_archetype(template: Mapping[str, Any], *, cell_id: str, gap: Mapping[str, Any]) -> dict[str, Any]:
    family_by_cell = {
        "demand_authenticity_and_sustainability": REQUIRED_FAMILIES[0],
        "value_and_profit_capture": REQUIRED_FAMILIES[0],
        "bottleneck_counterevidence_and_what_would_change": REQUIRED_FAMILIES[5],
    }
    suffix = _slug(str(gap["slot_id"]))
    raw = deepcopy(dict(template))
    raw.update({
        "archetype_id": f"case-gap-{cell_id}-{suffix}",
        "merge_key": f"gap_resolution__{cell_id}__{suffix}",
        "family_ids": [family_by_cell[cell_id]],
        "question_template": f"What exact current evidence would resolve {cell_id.replace('_', ' ')} for {{company_name}} without promoting the existing typed gap?",
        "source_pack_ref": "case-delta-{case_key}:v1",
    })
    return raw


def _canonical_validation_report(*, case_key: str, company: str, cells: Sequence[Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    inputs = CompilerInputContract(
        tenant_id="fin013-internal",
        project_id="fin013-repair-closeout",
        case_id=f"FIN013-{case_key}",
        query=f"Compile a current AI-infrastructure decision surface for {company}.",
        as_of="2026-07-26T00:00:00Z",
        universe=(case_key,),
        language="zh-CN",
        compiler_policy_ref=str(policy["compiler_policy_ref"]),
        pack_selection=PackSelectionDecision(
            universal_pack_refs=("universal-core:v1",),
            sector_pack_refs=("sector-ai-infrastructure:v2",),
            case_delta_pack_refs=(f"case-delta-{case_key.lower()}:v1",),
        ),
        required_cells=tuple(row.seed for row in cells),
    )
    validator_policy = CompilerInputValidationPolicy(
        policy_ref=str(policy["compiler_policy_ref"]),
        minimum_material_cells=int(policy["minimum_cells"]),
        maximum_material_cells=int(policy["maximum_cells"]),
        allowed_owner_roles=tuple(policy["allowed_owner_roles"]),
        allowed_materialities=("high", "medium"),
        allowed_source_policy_refs=tuple(policy["allowed_source_policy_refs"]),
        allowed_acceptance_roles=tuple(policy["allowed_acceptance_roles"]),
        require_forbidden_substitutions=True,
    )
    report = DecisionSurfacePlanningService(store=None).validate_compiler_input_full(inputs, policy=validator_policy)  # type: ignore[arg-type]
    return report.model_dump(mode="json")


def _compile_review_proof(surface: Mapping[str, Any], *, policy: Mapping[str, Any]) -> dict[str, Any]:
    protected_key = next(cell["cell_key"] for cell in surface["cells"] if "risk_counterevidence" in cell["protection_tags"])
    prune_key = next(cell["cell_key"] for cell in surface["cells"] if not cell["protection_tags"] and cell["cell_key"] == "customer_concentration")
    split_key = next(cell["cell_key"] for cell in surface["cells"] if cell["cell_key"] == "semicap_capex_cycle")
    revised = revise_dynamic_surface(
        surface,
        actions=(
            {"action": "prune", "target_cell_key": prune_key, "reason": "Reviewer merged concentration into the case-specific demand cell."},
            {"action": "split", "target_cell_key": split_key, "split_labels": ["spending signal", "earnings conversion"], "reason": "Reviewer requires separate capex and earnings-conversion tests."},
        ),
        policy=policy,
    )
    added_cell = deepcopy(next(cell for cell in surface["cells"] if cell["cell_key"] == "customer_concentration"))
    added_cell["cell_key"] = "reviewer_added_case_specific_monitor"
    added_cell["decision_question"] = (
        f"Which additional case-specific monitor could change the {surface['company_name']} decision surface?"
    )
    added_cell["dependency_cell_keys"] = []
    added_cell["evidence_binding"] = {
        "case_key": surface["case_key"],
        "evidence_aliases": [],
        "gap_aliases": [],
        "binding_status": "planned_request",
    }
    added_and_returned = revise_dynamic_surface(
        surface,
        actions=(
            {
                "action": "add",
                "reason": "Reviewer adds one bounded case-specific monitor.",
                "cell": added_cell,
            },
            {
                "action": "return",
                "reason": "Reviewer returns the revised plan for one more planning pass.",
            },
        ),
        policy=policy,
    )
    protected_rejected = False
    try:
        revise_dynamic_surface(surface, actions=({"action": "prune", "target_cell_key": protected_key, "reason": "mutation"},), policy=policy)
    except S3DynamicSurfaceError as exc:
        protected_rejected = exc.code == "s3_dynamic_surface_protected_cell_prune_forbidden"
    return {
        "case_key": surface["case_key"],
        "status": "pass" if (
            protected_rejected
            and revised["parent_surface_digest"] == surface["surface_digest"]
            and added_and_returned["checkpoint_status"] == "returned"
            and len(added_and_returned["cells"]) == len(surface["cells"]) + 1
        ) else "fail",
        "inspectable": True,
        "prune_and_split_revision_digest": revised["surface_digest"],
        "add_and_return_revision_digest": added_and_returned["surface_digest"],
        "original_cell_count": len(surface["cells"]),
        "revised_cell_count": len(revised["cells"]),
        "protected_prune_fail_closed": protected_rejected,
        "model_provider_network_calls": [0, 0, 0],
    }


def _assert_upstream(policy: Mapping[str, Any], s1: Mapping[str, Any], s2_policy: Mapping[str, Any], s2: Mapping[str, Any]) -> None:
    if (
        policy.get("contract_ref") != CONTRACT_REF
        or s1.get("retrieval_usefulness_program", {}).get("contract_ref") != S1_CONTRACT_REF
        or s1.get("acceptance", {}).get("S1") != "pass_closed"
        or s2_policy.get("contract_ref") != S2_CONTRACT_REF
        or s2.get("research_question_method_program", {}).get("contract_ref") != S2_CONTRACT_REF
        or s2.get("acceptance", {}).get("S2_01") != "engineering_pass"
    ):
        raise S3DynamicSurfaceError("s3_dynamic_surface_upstream_authority_invalid")


def _families_cover(cells: Sequence[Mapping[str, Any]]) -> bool:
    return {family for cell in cells for family in cell.get("family_ids") or ()} == set(REQUIRED_FAMILIES)


def _rewrite_dependencies(cells: list[dict[str, Any]], *, old_key: str, new_key: str) -> None:
    for cell in cells:
        cell["dependency_cell_keys"] = [new_key if value == old_key else value for value in cell.get("dependency_cell_keys") or []]


def _slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in value).strip("_")
