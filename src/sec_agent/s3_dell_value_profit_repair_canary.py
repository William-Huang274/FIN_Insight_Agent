from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s2_selected_evidence_numeric_natural_node_canary import (
    compile_canary_material as compile_s2_current_pack_material,
    load_canary_policy as load_s2_current_pack_policy,
)
from sec_agent.s3_dynamic_research_successor import (
    apply_repair_observation,
    load_s3_dynamic_research_successor_policy,
    record_affected_cell_readjudication,
    validate_s3_dynamic_research_successor_program,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_policy_v1_0"
)
CONTRACT_REF = (
    "fin_0_1_3.S3.dell_value_profit_current_pack_repair_canary:v1"
)
INPUT_SCHEMA = (
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_input_v1_0"
)
REQUEST_SCHEMA = (
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_request_v1_0"
)
ADMISSION_SCHEMA = (
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_admission_v1_0"
)
CAPTURE_SCHEMA = (
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_capture_v1_0"
)
TERMINAL_SCHEMA = (
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_terminal_v1_0"
)
ZERO_CALL_SCOPE = (
    "FIN_0_1_3_S3_DYNAMIC_RESEARCH_PLANNER_EVIDENCE_REQUEST_"
    "AND_CONTENT_QUALITY_ZERO_CALL"
)
ProviderCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]

_MODEL_NUMERIC_SURFACE = re.compile(
    r"\d|%|\b(?:mid|low|high)[-\s]+single[-\s]+digit\b|"
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?:percent|percentage\s+points?|billion|million)\b",
    re.IGNORECASE,
)


class S3DellValueProfitRepairCanaryError(RuntimeError):
    """Typed fail-closed error for the bounded S3 repair canary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S3DellValueProfitRepairCanaryError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S3DellValueProfitRepairCanaryError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _normalized_text_sha256(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise S3DellValueProfitRepairCanaryError(
            "s3_repair_canary_bound_text_unreadable"
        ) from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve(root: Path, ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _load_bound_json(
    *, root: Path, binding: Mapping[str, Any], code: str
) -> tuple[Path, dict[str, Any]]:
    path = _resolve(root, str(binding.get("ref") or ""))
    _require(path.is_file(), f"{code}_missing")
    _require(
        _normalized_text_sha256(path) == str(binding.get("sha256") or ""),
        f"{code}_sha256_drift",
    )
    return path, _read_json(path, f"{code}_json_invalid")


def load_repair_canary_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path).resolve(), "s3_repair_canary_policy_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("owner_stage") == "S3"
        and policy.get("zero_call_run_scope") == ZERO_CALL_SCOPE,
        "s3_repair_canary_policy_identity_invalid",
    )
    bindings = dict(policy.get("immutable_bindings") or {})
    _require(
        set(bindings)
        == {
            "value_cost_risk_decision",
            "s2_current_pack_compiler_policy",
            "successor_program",
            "successor_policy",
            "provider_profile",
        },
        "s3_repair_canary_policy_bindings_invalid",
    )
    _decision_path, decision = _load_bound_json(
        root=root,
        binding=dict(bindings["value_cost_risk_decision"]),
        code="s3_repair_canary_decision_binding",
    )
    decision_body = {
        key: value for key, value in decision.items() if key != "decision_digest"
    }
    _require(
        decision.get("decision_digest")
        == bindings["value_cost_risk_decision"].get("expected_decision_digest")
        == canonical_digest(decision_body)
        and decision.get("status")
        == (
            "decision_complete_authorize_one_dell_current_pack_repair_canary_"
            "zero_call_implementation_and_clean_proof_only"
        ),
        "s3_repair_canary_decision_invalid",
    )
    hard = dict(policy.get("hard_boundaries") or {})
    budget = dict(policy.get("request_budget") or {})
    _require(
        hard.get("current_governed_pack_first") is True
        and hard.get("capture_before_parse_or_validation") is True
        and hard.get("exact_once_admission") is True
        and hard.get("raw_source_text_in_model_input") is False
        and hard.get("model_numeric_surface_authority")
        == "alias_and_ref_selection_only"
        and hard.get("local_runtime_owns_state_transition") is True
        and hard.get("business_artifact_promotion") is False
        and hard.get("live_authority_issued_by_this_policy") is False
        and hard.get("automatic_rerun") is False
        and all(
            int(budget.get(key, -1)) == 0
            for key in ("source_calls", "network_tool_calls", "retries", "fallbacks")
        ),
        "s3_repair_canary_policy_boundary_invalid",
    )
    return policy


def _list_of_unique_strings(value: Any, code: str) -> list[str]:
    _require(isinstance(value, list), code)
    rows = [str(row) for row in value]
    _require(
        all(isinstance(row, str) and row.strip() for row in value)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def _compile_request(
    *,
    compiled_input: Mapping[str, Any],
    profile: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    system = (
        "You are a bounded financial-research repair adjudicator. Return exactly "
        "one JSON object matching output_contract. Reconcile current governed "
        "Evidence before requesting any new source. E021 is issuer-direct evidence "
        "about AI-server profitability relative to a management operating-income-rate "
        "target. E002 is a segment boundary: ISG operating income is not AI-server "
        "product profit. E008 supplies directional mix context, and E023 supplies "
        "pricing-discipline context only. Select aliases and NUM refs; do not write "
        "any digits, percentages, numeric bands or calculations in mechanism_atom or "
        "boundary_atom. Preserve gross-margin, cash-conversion and audited-product-"
        "profit gaps. Review exactly the supplied affected cells. Do not write a "
        "report, recommendation, valuation or target price."
    )
    body = {
        "schema_version": REQUEST_SCHEMA,
        "node_key": str(compiled_input["node_id"]),
        "node_type": "repair_adjudicator",
        "case_key": str(compiled_input["case_key"]),
        "compiled_input_digest": str(compiled_input["compiled_input_digest"]),
        "model": str(profile["model"]),
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    compiled_input,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        "temperature": 0.0,
        "stream": False,
        "enable_thinking": False,
        "max_tokens": int(policy["request_budget"]["maximum_output_tokens"]),
        "response_format": {"type": "json_object"},
        "output_schema_version": str(
            policy["output_contract"]["schema_version"]
        ),
    }
    request = {**body, "request_digest": canonical_digest(body)}
    serialized = json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    _require(
        len(serialized)
        <= int(policy["request_budget"]["maximum_compiled_request_characters"]),
        "s3_repair_canary_request_capacity_exceeded",
    )
    return request


def compile_repair_canary_material(
    *, policy: Mapping[str, Any], repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    bindings = dict(policy["immutable_bindings"])
    decision_path, decision = _load_bound_json(
        root=root,
        binding=dict(bindings["value_cost_risk_decision"]),
        code="s3_repair_canary_decision_binding",
    )
    s2_policy_path, _s2_policy_document = _load_bound_json(
        root=root,
        binding=dict(bindings["s2_current_pack_compiler_policy"]),
        code="s3_repair_canary_s2_policy_binding",
    )
    program_path, program = _load_bound_json(
        root=root,
        binding=dict(bindings["successor_program"]),
        code="s3_repair_canary_successor_program_binding",
    )
    successor_policy_path, _successor_policy_document = _load_bound_json(
        root=root,
        binding=dict(bindings["successor_policy"]),
        code="s3_repair_canary_successor_policy_binding",
    )
    profile_path, profile = _load_bound_json(
        root=root,
        binding=dict(bindings["provider_profile"]),
        code="s3_repair_canary_provider_profile_binding",
    )

    successor_policy = load_s3_dynamic_research_successor_policy(
        successor_policy_path
    )
    validate_s3_dynamic_research_successor_program(
        program, policy=successor_policy
    )
    _require(
        program.get("program_digest")
        == bindings["successor_program"].get("expected_program_digest"),
        "s3_repair_canary_successor_program_digest_drift",
    )

    s2_policy = load_s2_current_pack_policy(s2_policy_path, repo_root=root)
    current_pack_material = compile_s2_current_pack_material(
        policy=s2_policy, repo_root=root
    )
    research_view = dict(
        current_pack_material["cocompilation_result"]["node_views"][
            "research_view"
        ]
    )
    evidence_by_alias = {
        str(row.get("evidence_alias") or ""): dict(row)
        for row in research_view.get("evidence") or ()
    }
    facts_by_ref = {
        str(row.get("numeric_ref") or ""): dict(row)
        for row in research_view.get("numeric_facts") or ()
    }
    canary = dict(policy["canary"])
    evidence_aliases = list(canary["allowed_evidence_aliases"])
    numeric_refs = list(canary["allowed_numeric_refs"])
    _require(
        set(evidence_aliases) <= set(evidence_by_alias)
        and set(numeric_refs) <= set(facts_by_ref),
        "s3_repair_canary_current_pack_selection_missing",
    )
    _require(
        evidence_by_alias["E021"].get("evidence_role")
        == "issuer_direct_source"
        and canary["required_numeric_ref"]
        in set(evidence_by_alias["E021"].get("authorized_numeric_refs") or ()),
        "s3_repair_canary_e021_authority_drift",
    )

    request = next(
        (
            row
            for row in program.get("repair_requests") or ()
            if row.get("canonical_request", {}).get("request_id")
            == canary["repair_request_id"]
        ),
        None,
    )
    _require(
        isinstance(request, Mapping)
        and request.get("case_key") == "DELL"
        and request.get("gap_id") == canary["gap_id"]
        and request.get("status") == "compiled_not_admitted",
        "s3_repair_canary_request_binding_invalid",
    )
    fixture_observed = apply_repair_observation(
        program,
        policy=successor_policy,
        request_id=str(canary["repair_request_id"]),
        observation={
            "outcome": "accepted",
            "capture_ref": "fixture://s3-repair-canary/current-pack-e021",
            "capture_digest": hashlib.sha256(
                b"s3-repair-canary-current-pack-e021"
            ).hexdigest(),
            "evidence_gate_status": "accepted",
            "evidence_ref": "E021",
        },
    )
    observed_request = next(
        row
        for row in fixture_observed["repair_requests"]
        if row["canonical_request"]["request_id"]
        == canary["repair_request_id"]
    )
    _require(
        observed_request["affected_cell_ids"]
        == canary["expected_affected_cell_ids"],
        "s3_repair_canary_affected_cell_graph_drift",
    )

    mechanism = next(
        row
        for row in program["mechanism_and_wwc"]["mechanism_chains"]
        if row["case_key"] == "DELL"
        and row["affected_decision_cells"] == ["value_and_profit_capture"]
    )
    wwc = next(
        row
        for row in program["mechanism_and_wwc"]["what_would_change"]
        if row["case_key"] == "DELL"
        and row["alias"] == canary["required_wwc_ref"]
    )
    selected_evidence = []
    for alias in evidence_aliases:
        row = evidence_by_alias[alias]
        selected_evidence.append(
            {
                "evidence_alias": alias,
                "target_id": row.get("target_id"),
                "evidence_role": row.get("evidence_role"),
                "relationship_directions": deepcopy(
                    list(row.get("relationship_directions") or ())
                ),
                "slot_bindings": deepcopy(list(row.get("slot_bindings") or ())),
                "bounded_numeric_annotated_contexts": deepcopy(
                    list(row.get("bounded_numeric_annotated_contexts") or ())
                ),
                "authorized_numeric_refs": deepcopy(
                    list(row.get("authorized_numeric_refs") or ())
                ),
                "source_text_digest": row.get("source_text_digest"),
            }
        )
    selected_facts = [deepcopy(facts_by_ref[ref]) for ref in numeric_refs]
    input_body = {
        "schema_version": INPUT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "case_key": canary["case_key"],
        "node_id": canary["node_id"],
        "research_question_zh": canary["research_question_zh"],
        "repair_request": {
            "request_id": canary["repair_request_id"],
            "gap_id": canary["gap_id"],
            "cell_id": request["cell_id"],
            "impact": request["impact"],
            "current_status": request["status"],
        },
        "current_mechanism_and_boundary": {
            "economic_transmission_hypothesis": mechanism[
                "economic_transmission_hypothesis"
            ],
            "financial_or_operating_implication": deepcopy(
                mechanism["financial_or_operating_implication"]
            ),
            "confidence_and_cannot_infer_boundary": deepcopy(
                mechanism["confidence_and_cannot_infer_boundary"]
            ),
            "what_would_change": {
                "alias": wwc["alias"],
                "decisive_variable": wwc["decisive_variable"],
                "direction": wwc["direction"],
                "time_window": wwc["time_window"],
                "next_disclosure_or_observation_route": wwc[
                    "next_disclosure_or_observation_route"
                ],
            },
        },
        "current_pack_evidence": selected_evidence,
        "numeric_facts": selected_facts,
        "authoritative_affected_cell_ids": deepcopy(
            canary["expected_affected_cell_ids"]
        ),
        "output_contract": deepcopy(dict(policy["output_contract"])),
        "rules": {
            "accepted_evidence_refs": deepcopy(
                canary["accepted_evidence_aliases"]
            ),
            "boundary_evidence_refs": deepcopy(
                canary["boundary_evidence_aliases"]
            ),
            "required_retained_gap_components": deepcopy(
                canary["required_retained_gap_components"]
            ),
            "required_wwc_ref": canary["required_wwc_ref"],
            "model_selects_aliases_and_numeric_refs_only": True,
            "local_runtime_owns_observation_and_state_transition": True,
            "complete_report_or_recommendation": False,
        },
        "raw_source_text_in_model_input": False,
    }
    compiled_input = {
        **input_body,
        "compiled_input_digest": canonical_digest(input_body),
    }
    serialized = json.dumps(compiled_input, ensure_ascii=False)
    _require(
        "source_text\"" not in serialized
        and compiled_input["raw_source_text_in_model_input"] is False,
        "s3_repair_canary_raw_source_text_leak",
    )
    provider_request = _compile_request(
        compiled_input=compiled_input,
        profile=profile,
        policy=policy,
    )
    return {
        "policy": deepcopy(dict(policy)),
        "decision": decision,
        "decision_ref": decision_path.relative_to(root).as_posix(),
        "profile": profile,
        "profile_ref": profile_path.relative_to(root).as_posix(),
        "successor_policy": successor_policy,
        "successor_policy_ref": successor_policy_path.relative_to(root).as_posix(),
        "successor_program": program,
        "successor_program_ref": program_path.relative_to(root).as_posix(),
        "current_pack_cocompilation_result": current_pack_material[
            "cocompilation_result"
        ],
        "compiled_input": compiled_input,
        "provider_request": provider_request,
    }


def _validate_readjudications(
    *, output: Mapping[str, Any], material: Mapping[str, Any]
) -> list[dict[str, Any]]:
    policy = dict(material["policy"])
    contract = dict(policy["output_contract"])
    canary = dict(policy["canary"])
    rows = output.get("affected_cell_readjudications")
    _require(isinstance(rows, list), "s3_repair_canary_readjudications_invalid")
    expected_cells = list(canary["expected_affected_cell_ids"])
    _require(
        len(rows) == len(expected_cells)
        and {str(row.get("cell_id") or "") for row in rows}
        == set(expected_cells),
        "s3_repair_canary_readjudication_coverage_invalid",
    )
    allowed_evidence = set(canary["allowed_evidence_aliases"])
    allowed_numeric = set(canary["allowed_numeric_refs"])
    normalized: list[dict[str, Any]] = []
    for value in rows:
        _require(
            isinstance(value, Mapping)
            and set(value) == set(contract["readjudication_fields"]),
            "s3_repair_canary_readjudication_fields_invalid",
        )
        row = dict(value)
        _require(
            row.get("judgment_state") in contract["judgment_state_enum"]
            and isinstance(row.get("judgment_changed"), bool),
            "s3_repair_canary_readjudication_state_invalid",
        )
        support = _list_of_unique_strings(
            row.get("support_refs"),
            "s3_repair_canary_support_refs_invalid",
        )
        counter = _list_of_unique_strings(
            row.get("counterevidence_refs"),
            "s3_repair_canary_counterevidence_refs_invalid",
        )
        numeric = _list_of_unique_strings(
            row.get("numeric_refs"),
            "s3_repair_canary_numeric_refs_invalid",
        )
        _require(
            bool(support or counter)
            and set(support) | set(counter) <= allowed_evidence
            and set(numeric) <= allowed_numeric,
            "s3_repair_canary_readjudication_unknown_or_empty_ref",
        )
        mechanism = row.get("mechanism_atom")
        boundary = row.get("boundary_atom")
        _require(
            isinstance(mechanism, str)
            and bool(mechanism.strip())
            and isinstance(boundary, str)
            and bool(boundary.strip())
            and len(mechanism) <= int(contract["maximum_atom_text_characters"])
            and len(boundary) <= int(contract["maximum_atom_text_characters"]),
            "s3_repair_canary_readjudication_atom_invalid",
        )
        _require(
            not _MODEL_NUMERIC_SURFACE.search(mechanism)
            and not _MODEL_NUMERIC_SURFACE.search(boundary),
            "s3_repair_canary_model_numeric_surface_forbidden",
        )
        if row["judgment_changed"]:
            _require(
                "E021" in set(support) | set(counter),
                "s3_repair_canary_changed_judgment_missing_new_evidence",
            )
        row["support_refs"] = support
        row["counterevidence_refs"] = counter
        row["numeric_refs"] = numeric
        normalized.append(row)

    by_cell = {str(row["cell_id"]): row for row in normalized}
    target = by_cell["value_and_profit_capture"]
    _require(
        target["judgment_state"] == "supported_with_limits"
        and target["judgment_changed"] is True
        and "E021" in target["support_refs"]
        and canary["required_numeric_ref"] in target["numeric_refs"]
        and target["wwc_ref"] == canary["required_wwc_ref"],
        "s3_repair_canary_target_readjudication_invalid",
    )
    price_in = by_cell["cross_chain_price_in_and_expectations"]
    _require(
        price_in["judgment_state"] == "cannot_infer"
        and price_in["judgment_changed"] is False,
        "s3_repair_canary_price_in_boundary_invalid",
    )
    _require(
        all(
            str(row.get("wwc_ref") or "") in {"", canary["required_wwc_ref"]}
            for row in normalized
        ),
        "s3_repair_canary_wwc_ref_invalid",
    )
    return normalized


def adjudicate_repair_canary_output(
    *,
    output: Mapping[str, Any],
    material: Mapping[str, Any],
    capture_ref: str,
    capture_digest: str,
) -> dict[str, Any]:
    policy = dict(material["policy"])
    contract = dict(policy["output_contract"])
    canary = dict(policy["canary"])
    _require(
        isinstance(output, Mapping)
        and set(output) == set(contract["top_level_fields"]),
        "s3_repair_canary_output_fields_invalid",
    )
    _require(
        output.get("schema_version") == contract["schema_version"]
        and output.get("case_key") == canary["case_key"]
        and output.get("node_id") == canary["node_id"]
        and output.get("repair_request_id") == canary["repair_request_id"],
        "s3_repair_canary_output_identity_invalid",
    )
    serialized = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
    _require(
        len(serialized) <= int(contract["maximum_total_output_characters"]),
        "s3_repair_canary_output_capacity_exceeded",
    )
    _require(
        output.get("observation_outcome") == "accepted"
        and output.get("repair_resolution") == "accepted_partial_resolution",
        "s3_repair_canary_repair_disposition_invalid",
    )
    accepted = _list_of_unique_strings(
        output.get("accepted_evidence_refs"),
        "s3_repair_canary_accepted_refs_invalid",
    )
    boundary_refs = _list_of_unique_strings(
        output.get("boundary_evidence_refs"),
        "s3_repair_canary_boundary_refs_invalid",
    )
    retained = _list_of_unique_strings(
        output.get("retained_gap_components"),
        "s3_repair_canary_retained_gaps_invalid",
    )
    _require(
        accepted == canary["accepted_evidence_aliases"]
        and boundary_refs == canary["boundary_evidence_aliases"]
        and retained == canary["required_retained_gap_components"],
        "s3_repair_canary_evidence_or_gap_set_invalid",
    )
    semantics = output.get("evidence_semantics")
    _require(
        isinstance(semantics, Mapping)
        and set(semantics) == set(contract["evidence_semantics_fields"])
        and dict(semantics) == dict(contract["required_evidence_semantics"]),
        "s3_repair_canary_evidence_semantics_invalid",
    )
    readjudications = _validate_readjudications(
        output=output, material=material
    )
    used_numeric = _list_of_unique_strings(
        output.get("used_numeric_refs"),
        "s3_repair_canary_used_numeric_refs_invalid",
    )
    union_numeric = sorted(
        {
            ref
            for row in readjudications
            for ref in row["numeric_refs"]
        }
    )
    _require(
        sorted(used_numeric) == union_numeric
        and canary["required_numeric_ref"] in used_numeric,
        "s3_repair_canary_numeric_ref_union_invalid",
    )

    observed = apply_repair_observation(
        material["successor_program"],
        policy=material["successor_policy"],
        request_id=canary["repair_request_id"],
        observation={
            "outcome": "accepted",
            "capture_ref": capture_ref,
            "capture_digest": capture_digest,
            "evidence_gate_status": "accepted",
            "evidence_ref": "E021",
        },
    )
    observation = next(
        row
        for row in observed["repair_observations"]
        if row["request_id"] == canary["repair_request_id"]
    )
    decisions = [
        {
            "cell_id": row["cell_id"],
            "judgment_state": row["judgment_state"],
            "judgment_changed": row["judgment_changed"],
            "support_refs": row["support_refs"],
            "counterevidence_refs": row["counterevidence_refs"],
            "mechanism": row["mechanism_atom"],
            "boundary": row["boundary_atom"],
            "wwc_ref": row["wwc_ref"],
            "observation_digest": observation["observation_digest"],
        }
        for row in readjudications
    ]
    successor = record_affected_cell_readjudication(
        observed,
        policy=material["successor_policy"],
        request_id=canary["repair_request_id"],
        decisions=decisions,
    )
    validate_s3_dynamic_research_successor_program(
        successor, policy=material["successor_policy"]
    )
    repaired_request = next(
        row
        for row in successor["repair_requests"]
        if row["canonical_request"]["request_id"]
        == canary["repair_request_id"]
    )
    required_fact = next(
        row
        for row in material["compiled_input"]["numeric_facts"]
        if row["numeric_ref"] == canary["required_numeric_ref"]
    )
    local_projection = {
        "numeric_ref": required_fact["numeric_ref"],
        "rendered": required_fact["allowed_presentations"][0]["rendered"],
        "authority": "local_numeric_presentation_program",
        "model_authored_surface": False,
    }
    validation_body = {
        "status": "pass",
        "case_key": canary["case_key"],
        "node_id": canary["node_id"],
        "output_digest": canonical_digest(output),
        "repair_request_status": repaired_request["status"],
        "accepted_evidence_refs": accepted,
        "boundary_evidence_refs": boundary_refs,
        "affected_cell_ids": list(repaired_request["affected_cell_ids"]),
        "retained_gap_components": retained,
        "used_numeric_refs": sorted(used_numeric),
        "local_numeric_projection": local_projection,
        "successor_program_digest": successor["program_digest"],
        "readjudication_receipt_digests": sorted(
            row["readjudication_digest"]
            for row in successor["readjudication_receipts"]
            if row["request_id"] == canary["repair_request_id"]
        ),
        "source_calls": 0,
        "network_tool_calls": 0,
        "business_artifact_promotion": False,
    }
    validation = {
        **validation_body,
        "validation_digest": canonical_digest(validation_body),
    }
    return {
        "validation": validation,
        "successor_program": successor,
    }


def issue_fixture_admission(
    *,
    material: Mapping[str, Any],
    run_id: str,
    attempt_id: str,
    observed_at: str,
) -> dict[str, Any]:
    _require(
        bool(run_id.strip()) and bool(attempt_id.strip()),
        "s3_repair_canary_run_identity_invalid",
    )
    request = dict(material["provider_request"])
    compiled = dict(material["compiled_input"])
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": f"fixture::{run_id}::{attempt_id}",
        "authority_kind": "zero_call_test_fixture_only",
        "execution_mode": "fixture",
        "run_scope": ZERO_CALL_SCOPE,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "case_key": compiled["case_key"],
        "node_id": compiled["node_id"],
        "compiled_input_digest": compiled["compiled_input_digest"],
        "request_digest": request["request_digest"],
        "profile_ref": material["profile"]["profile_ref"],
        "provider": material["profile"]["provider"],
        "model": material["profile"]["model"],
        "provider_calls_maximum": 1,
        "model_calls_maximum": 1,
        "source_calls": 0,
        "network_tool_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "observed_at": observed_at,
        "live_authority": False,
        "business_artifact_promotion": False,
    }
    return {**body, "admission_digest": canonical_digest(body)}


def validate_fixture_admission(
    admission: Mapping[str, Any], *, material: Mapping[str, Any]
) -> None:
    body = {
        key: value for key, value in admission.items() if key != "admission_digest"
    }
    _require(
        admission.get("schema_version") == ADMISSION_SCHEMA
        and admission.get("admission_digest") == canonical_digest(body)
        and admission.get("run_scope") == ZERO_CALL_SCOPE
        and admission.get("execution_mode") == "fixture"
        and admission.get("authority_kind") == "zero_call_test_fixture_only"
        and admission.get("live_authority") is False
        and admission.get("business_artifact_promotion") is False,
        "s3_repair_canary_admission_identity_invalid",
    )
    request = dict(material["provider_request"])
    compiled = dict(material["compiled_input"])
    _require(
        admission.get("case_key") == compiled["case_key"]
        and admission.get("node_id") == compiled["node_id"]
        and admission.get("compiled_input_digest")
        == compiled["compiled_input_digest"]
        and admission.get("request_digest") == request["request_digest"]
        and admission.get("profile_ref") == material["profile"]["profile_ref"]
        and admission.get("provider_calls_maximum") == 1
        and admission.get("model_calls_maximum") == 1
        and all(
            int(admission.get(key, -1)) == 0
            for key in ("source_calls", "network_tool_calls", "retries", "fallbacks")
        ),
        "s3_repair_canary_admission_binding_invalid",
    )


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _terminalize(
    *,
    admission: Mapping[str, Any],
    request: Mapping[str, Any],
    capture: Mapping[str, Any],
    runtime_root: Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    status: str,
    phase: str,
    code: str,
    observed_at: str,
    output: Mapping[str, Any] | None,
    validation: Mapping[str, Any] | None,
    successor_program: Mapping[str, Any] | None,
) -> dict[str, Any]:
    body = {
        "schema_version": TERMINAL_SCHEMA,
        "run_scope": admission["run_scope"],
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "case_key": admission["case_key"],
        "node_id": admission["node_id"],
        "status": status,
        "terminal_phase": phase,
        "terminal_code": code,
        "observed_counts": {
            "fixture_provider_callbacks": 1,
            "provider_calls": 0,
            "model_calls": 0,
            "source_calls": 0,
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "request_ref": "raw_model_only/calls/call_01/request.json",
        "request_digest": request["request_digest"],
        "capture_ref": "raw_model_only/calls/call_01/capture.json",
        "capture_digest": capture["capture_digest"],
        "validated_output_ref": (
            "validated/repair_output.json" if output is not None else None
        ),
        "output_digest": canonical_digest(output) if output is not None else None,
        "validation_digest": (
            validation.get("validation_digest") if validation is not None else None
        ),
        "successor_program_digest": (
            successor_program.get("program_digest")
            if successor_program is not None
            else None
        ),
        "business_artifact_promotion": False,
        "observed_at": observed_at,
    }
    terminal_digest = canonical_digest(body)
    terminal = {**body, "terminal_result_digest": terminal_digest}
    _atomic_json(runtime_root / "terminal.json", terminal)
    receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=status,
        terminal_phase=phase,
        terminal_code=code,
        terminal_result_digest=terminal_digest,
        finalized_at=observed_at,
    ).as_dict()
    public_body = {**terminal, "admission_consumption_receipt": receipt}
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _atomic_json(runtime_root / "terminal_with_receipt.json", public)
    return public


def execute_validated_repair_canary(
    *,
    admission: Mapping[str, Any],
    material: Mapping[str, Any],
    provider_call: ProviderCall,
    runtime_root: str | Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    observed_at: str,
) -> dict[str, Any]:
    root = Path(runtime_root).resolve()
    _require(not root.exists(), "s3_repair_canary_attempt_root_exists")
    shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["run_scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=CONTRACT_REF,
        reserved_at=observed_at,
    )
    request = deepcopy(dict(material["provider_request"]))
    call_root = root / "raw_model_only/calls/call_01"
    request_record = {
        "schema_version": REQUEST_SCHEMA,
        "observed_at": observed_at,
        "request": request,
        "request_digest": request["request_digest"],
    }
    _atomic_json(call_root / "request.json", request_record)
    try:
        response = dict(provider_call(request))
    except Exception as exc:  # Full failure is captured; retry is forbidden.
        response = {
            "status": "provider_error",
            "failure_reason": f"{type(exc).__name__}: {str(exc)[:1000]}",
            "content": "",
            "finish_reason": None,
        }
    capture_body = {
        "schema_version": CAPTURE_SCHEMA,
        "call_id": "call_01",
        "request_digest": request["request_digest"],
        "request": request,
        "provider_response": deepcopy(response),
        "observed_at": observed_at,
    }
    capture = {**capture_body, "capture_digest": canonical_digest(capture_body)}
    _atomic_json(call_root / "capture.json", capture)
    if str(response.get("status") or "") != "ok":
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="provider_transport",
            code=(
                "s3_repair_canary_provider_failure:"
                + str(response.get("status") or "unknown")
            ),
            observed_at=observed_at,
            output=None,
            validation=None,
            successor_program=None,
        )
    finish_reason = str(response.get("finish_reason") or "").casefold()
    if finish_reason != "stop":
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="provider_output",
            code=(
                "s3_repair_canary_incomplete_finish_reason_length"
                if finish_reason == "length"
                else "s3_repair_canary_finish_reason_invalid"
            ),
            observed_at=observed_at,
            output=None,
            validation=None,
            successor_program=None,
        )
    content = str(response.get("content") or "")
    if not content.strip():
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="provider_output",
            code="s3_repair_canary_empty_output",
            observed_at=observed_at,
            output=None,
            validation=None,
            successor_program=None,
        )
    try:
        output = json.loads(content)
    except json.JSONDecodeError:
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="provider_output",
            code="s3_repair_canary_invalid_json",
            observed_at=observed_at,
            output=None,
            validation=None,
            successor_program=None,
        )
    if not isinstance(output, dict):
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="provider_output",
            code="s3_repair_canary_json_object_required",
            observed_at=observed_at,
            output=None,
            validation=None,
            successor_program=None,
        )
    try:
        adjudicated = adjudicate_repair_canary_output(
            output=output,
            material=material,
            capture_ref="raw_model_only/calls/call_01/capture.json",
            capture_digest=capture["capture_digest"],
        )
    except S3DellValueProfitRepairCanaryError as exc:
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="contract_validation",
            code=exc.code,
            observed_at=observed_at,
            output=output,
            validation=None,
            successor_program=None,
        )
    except Exception as exc:
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="successor_projection",
            code=f"s3_repair_canary_successor_projection_failed:{type(exc).__name__}",
            observed_at=observed_at,
            output=output,
            validation=None,
            successor_program=None,
        )
    validation = dict(adjudicated["validation"])
    successor = dict(adjudicated["successor_program"])
    _atomic_json(root / "validated/repair_output.json", output)
    _atomic_json(root / "validated/validation.json", validation)
    _atomic_json(root / "validated/successor_program.json", successor)
    return _terminalize(
        admission=admission,
        request=request,
        capture=capture,
        runtime_root=root,
        shared_ledger=shared_ledger,
        status="completed",
        phase="complete",
        code="s3_repair_canary_pass",
        observed_at=observed_at,
        output=output,
        validation=validation,
        successor_program=successor,
    )


def execute_fixture_repair_canary(
    *,
    admission: Mapping[str, Any],
    material: Mapping[str, Any],
    provider_call: ProviderCall,
    runtime_root: str | Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    observed_at: str,
) -> dict[str, Any]:
    validate_fixture_admission(admission, material=material)
    return execute_validated_repair_canary(
        admission=admission,
        material=material,
        provider_call=provider_call,
        runtime_root=runtime_root,
        shared_ledger=shared_ledger,
        observed_at=observed_at,
    )


__all__ = [
    "ADMISSION_SCHEMA",
    "CONTRACT_REF",
    "POLICY_SCHEMA",
    "ZERO_CALL_SCOPE",
    "S3DellValueProfitRepairCanaryError",
    "adjudicate_repair_canary_output",
    "compile_repair_canary_material",
    "execute_fixture_repair_canary",
    "execute_validated_repair_canary",
    "issue_fixture_admission",
    "load_repair_canary_policy",
    "validate_fixture_admission",
]
