from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.s1_six_case_local_evidence_pack import (
    canonical_digest,
    file_sha256,
    validate_local_evidence_pack,
)
from sec_agent.s2_fixed_pack_capture_reuse_successor import (
    compile_numeric_authority,
    load_numeric_verifier_repair_policy,
)
from sec_agent.s2_fixed_pack_research import (
    compile_case_model_input,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    validate_case_model_input,
)
from sec_agent.s2_fixed_pack_research_runtime import (
    NODE_ORDER,
    validate_case_admission,
)


CONTRACT_SCHEMA = (
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_contract_v1_0"
)
PROOF_SCHEMA = (
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_clean_proof_v1_0"
)
AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_authority_v1_0"
)
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_result_v1_0"
)
NUMERIC_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s2_dell_changed_input_numeric_authority_v1_0"
)
RUN_SCOPE = "FIN_0_1_3_S2_DELL_FIXED_PACK_MODEL_COMPARISON"
REQUIRED_SUPPLEMENT_TARGETS = {
    "SUPPLEMENT::DELL::ISSUER::Q1FY27::AI_SERVER_PROFITABILITY",
    "SUPPLEMENT::DELL::ISSUER::Q1FY27::DEMAND_BACKLOG_SUPPLY",
    "SUPPLEMENT::DELL::ISSUER::Q1FY27::PROACTIVE_SUPPLY_SECURING",
    "SUPPLEMENT::DELL::SUPPLIER::MU::HBM_PACKAGING_H1_2027",
    "SUPPLEMENT::DELL::SUPPLIER::MU::SUPPLY_TIGHT_BEYOND_2027",
}


class S2DellChangedInputComparisonError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S2DellChangedInputComparisonError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S2DellChangedInputComparisonError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _resolve(root: Path, ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _normalized_text_sha256(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise S2DellChangedInputComparisonError(
            "changed_input_comparison_bound_text_unreadable"
        ) from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_changed_input_comparison_contract(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    contract = _read_json(
        Path(path), "changed_input_comparison_contract_json_invalid"
    )
    boundary = dict(contract.get("execution_boundary") or {})
    _require(
        contract.get("schema_version") == CONTRACT_SCHEMA
        and contract.get("run_scope") == RUN_SCOPE
        and contract.get("case_key") == "DELL"
        and boundary
        == {
            "fresh_model_nodes": 13,
            "provider_calls_maximum": 13,
            "model_calls_maximum": 13,
            "source_calls": 0,
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "old_model_node_reuse": False,
            "business_artifact_promotion": False,
        },
        "changed_input_comparison_contract_identity_or_boundary_invalid",
    )
    bindings = dict(contract.get("immutable_bindings") or {})
    _require(
        set(bindings)
        == {
            "fixed_pack_contract",
            "provider_profile",
            "historical_numeric_contract",
            "numeric_verifier_repair_policy",
            "corrected_pack_result",
            "prior_model_result",
        },
        "changed_input_comparison_contract_binding_set_invalid",
    )
    for name, binding_value in bindings.items():
        binding = dict(binding_value or {})
        bound_path = _resolve(root, str(binding.get("ref") or ""))
        _require(
            bound_path.is_file()
            and _normalized_text_sha256(bound_path)
            == str(binding.get("sha256") or ""),
            f"changed_input_comparison_binding_drift:{name}",
        )
        expected_result = str(binding.get("expected_result_digest") or "")
        if expected_result:
            payload = _read_json(
                bound_path,
                f"changed_input_comparison_bound_json_invalid:{name}",
            )
            _require(
                payload.get("result_digest") == expected_result,
                f"changed_input_comparison_result_digest_drift:{name}",
            )
    return contract


def load_corrected_dell_pack(
    *,
    contract: Mapping[str, Any],
    repo_root: str | Path,
    artifact_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(repo_root).resolve()
    binding = dict(
        (contract.get("immutable_bindings") or {}).get("corrected_pack_result")
        or {}
    )
    result = _read_json(
        _resolve(root, str(binding.get("ref") or "")),
        "changed_input_corrected_pack_result_invalid",
    )
    gates = dict(result.get("gate_status") or {})
    _require(
        result.get("result_digest") == binding.get("expected_result_digest")
        and gates.get("core_research_ready") is True
        and gates.get("successor_pack_ready_for_model_input") is True,
        "changed_input_corrected_pack_gate_or_digest_invalid",
    )
    artifact = dict(result.get("corrected_pack_artifact") or {})
    if artifact_path is None:
        private_root = _resolve(
            root, str(contract.get("corrected_pack_private_root") or "")
        )
        path = private_root / str(artifact.get("object_key") or "")
    else:
        path = Path(artifact_path).resolve()
    _require(
        path.is_file()
        and file_sha256(path) == str(artifact.get("digest") or ""),
        "changed_input_corrected_pack_artifact_drift",
    )
    pack = _read_json(path, "changed_input_corrected_pack_json_invalid")
    validate_local_evidence_pack(pack)
    _require(
        pack.get("case_key") == "DELL"
        and pack.get("pack_payload_digest")
        == result.get("corrected_pack_payload_digest"),
        "changed_input_corrected_pack_payload_binding_invalid",
    )
    return result, pack


def load_historical_dell_case_input(
    *,
    fixed_contract: Mapping[str, Any],
    profile: Mapping[str, Any],
    repo_root: str | Path,
    artifact_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    binding = dict(
        (fixed_contract.get("immutable_inputs") or {}).get(
            "local_evidence_pack_result"
        )
        or {}
    )
    result = _read_json(
        _resolve(root, str(binding.get("ref") or "")),
        "changed_input_historical_pack_result_invalid",
    )
    reference = dict((result.get("pack_artifacts") or {}).get("DELL") or {})
    if artifact_path is None:
        path = _resolve(root, str(fixed_contract.get("private_pack_root") or "")) / str(
            reference.get("object_key") or ""
        )
    else:
        path = Path(artifact_path).resolve()
    _require(
        path.is_file() and file_sha256(path) == str(reference.get("digest") or ""),
        "changed_input_historical_dell_pack_artifact_drift",
    )
    pack = _read_json(path, "changed_input_historical_dell_pack_invalid")
    validate_local_evidence_pack(pack)
    _require(
        pack.get("case_key") == "DELL"
        and pack.get("pack_payload_digest")
        == (result.get("pack_payload_digests") or {}).get("DELL"),
        "changed_input_historical_dell_pack_binding_invalid",
    )
    return compile_case_model_input(
        contract=fixed_contract,
        profile=profile,
        pack=pack,
    )


def _alias_indexes(case_input: Mapping[str, Any]) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, str],
    dict[str, str],
]:
    evidence_by_alias = {
        str(row.get("evidence_alias") or ""): dict(row)
        for row in case_input.get("evidence_items") or ()
    }
    material_by_alias = {
        str(row.get("source_material_alias") or ""): dict(row)
        for row in case_input.get("source_materials") or ()
    }
    alias_by_target: dict[str, str] = {}
    for alias, row in evidence_by_alias.items():
        target_id = str(row.get("target_id") or "")
        _require(
            target_id and target_id not in alias_by_target,
            "changed_input_evidence_target_identity_collision",
        )
        alias_by_target[target_id] = alias
    alias_by_source_record: dict[str, str] = {}
    for alias, row in material_by_alias.items():
        source_record_id = str(row.get("source_record_id") or "")
        _require(
            source_record_id and source_record_id not in alias_by_source_record,
            "changed_input_source_record_identity_collision",
        )
        alias_by_source_record[source_record_id] = alias
    return (
        evidence_by_alias,
        material_by_alias,
        alias_by_target,
        alias_by_source_record,
    )


def rebind_numeric_declaration(
    declaration: Mapping[str, Any],
    *,
    historical_case_input: Mapping[str, Any],
    current_case_input: Mapping[str, Any],
) -> dict[str, Any]:
    old_evidence, old_materials, _, _ = _alias_indexes(historical_case_input)
    _, _, current_evidence, current_materials = _alias_indexes(current_case_input)
    old_evidence_aliases = [
        str(value) for value in declaration.get("evidence_aliases") or ()
    ]
    old_material_alias = str(declaration.get("source_material_alias") or "")
    _require(
        old_evidence_aliases
        and all(alias in old_evidence for alias in old_evidence_aliases)
        and old_material_alias in old_materials,
        "changed_input_historical_numeric_alias_missing",
    )
    target_ids = [
        str(old_evidence[alias].get("target_id") or "")
        for alias in old_evidence_aliases
    ]
    source_record_id = str(
        old_materials[old_material_alias].get("source_record_id") or ""
    )
    _require(
        all(target_id in current_evidence for target_id in target_ids)
        and source_record_id in current_materials,
        "changed_input_stable_numeric_identity_missing",
    )
    row = deepcopy(dict(declaration))
    row["evidence_aliases"] = [
        current_evidence[target_id] for target_id in target_ids
    ]
    row["source_material_alias"] = current_materials[source_record_id]
    row["stable_binding"] = {
        "target_ids": target_ids,
        "source_record_id": source_record_id,
    }
    return row


def _append_market_numeric_fact(
    numeric: dict[str, Any],
    *,
    pack: Mapping[str, Any],
    case_input: Mapping[str, Any],
) -> None:
    market_rows = [
        dict(row)
        for row in pack.get("numeric_facts") or ()
        if row.get("fact_type") == "market_point_in_time_close"
        and row.get("case_key") == "DELL"
        and row.get("promotion_status") == "accepted_exact_date_market_input"
    ]
    _require(
        len(market_rows) == 1,
        "changed_input_market_numeric_fact_population_invalid",
    )
    row = market_rows[0]
    observation_date = str(row.get("observation_date") or "")
    value = str(row.get("normalized_value") or "")
    target_id = f"MARKET::DELL::RAW_CLOSE::{observation_date}"
    evidence_by_alias, materials_by_alias, aliases, _ = _alias_indexes(case_input)
    evidence_alias = aliases.get(target_id, "")
    _require(
        evidence_alias in evidence_by_alias,
        "changed_input_market_evidence_target_missing",
    )
    material_alias = str(
        evidence_by_alias[evidence_alias].get("source_material_alias") or ""
    )
    source_text = str((materials_by_alias.get(material_alias) or {}).get("source_text") or "")
    try:
        exact_value = Decimal(value)
    except Exception as exc:  # pragma: no cover - defensive typed boundary
        raise S2DellChangedInputComparisonError(
            "changed_input_market_numeric_value_invalid"
        ) from exc
    _require(
        exact_value > 0 and value in source_text,
        "changed_input_market_numeric_source_binding_invalid",
    )
    numeric_ref = f"NUM:DELL:MARKET:{observation_date}:RAW_CLOSE"
    numeric.setdefault("source_numeric_facts", []).append(
        {
            "numeric_ref": numeric_ref,
            "semantic_name_zh": f"Dell {observation_date} 未复权收盘价",
            "exact_value": value,
            "unit": "USD_per_share",
            "period_id": observation_date,
            "evidence_aliases": [evidence_alias],
            "source_material_alias": material_alias,
            "source_token": value,
            "authority": "source_bound_market_point_in_time_numeric_fact",
            "authority_boundary": str(row.get("authority_boundary") or ""),
            "numeric_fact_id": str(row.get("numeric_fact_id") or ""),
            "display_surfaces": [
                {
                    "presentation_ref": f"PRES:DELL:MARKET:{observation_date}:USD_PER_SHARE",
                    "numeric_token": value,
                    "rendered": f"USD {value} per share",
                    "operation": "identity",
                    "operand": "1",
                },
                {
                    "presentation_ref": f"PRES:DELL:MARKET:{observation_date}:ZH_USD_PER_SHARE",
                    "numeric_token": value,
                    "rendered": f"每股 {value} 美元",
                    "operation": "identity",
                    "operand": "1",
                },
            ],
        }
    )


def compile_changed_input_numeric_authority(
    *,
    contract: Mapping[str, Any],
    historical_case_input: Mapping[str, Any],
    current_case_input: Mapping[str, Any],
    pack: Mapping[str, Any],
    historical_numeric_contract: Mapping[str, Any],
    repair_policy: Mapping[str, Any],
) -> dict[str, Any]:
    declarations = dict(historical_numeric_contract.get("numeric_authority") or {})
    rebound_facts = [
        rebind_numeric_declaration(
            row,
            historical_case_input=historical_case_input,
            current_case_input=current_case_input,
        )
        for row in declarations.get("source_numeric_facts") or ()
    ]
    rebound_additions = [
        rebind_numeric_declaration(
            row,
            historical_case_input=historical_case_input,
            current_case_input=current_case_input,
        )
        for row in repair_policy.get("numeric_authority_additions") or ()
    ]
    rebound_contract = {
        "case_key": "DELL",
        "numeric_authority": {
            "source_numeric_facts": rebound_facts,
            "formula_programs": deepcopy(
                list(declarations.get("formula_programs") or ())
            ),
        },
    }
    compiled = compile_numeric_authority(
        base_case_input=current_case_input,
        contract=rebound_contract,
    )
    numeric = deepcopy(dict(compiled))
    numeric.pop("numeric_authority_digest", None)
    stable_bindings = {
        str(row.get("numeric_ref") or ""): deepcopy(
            dict(row.get("stable_binding") or {})
        )
        for row in rebound_facts
    }
    for fact in numeric.get("source_numeric_facts") or ():
        fact["stable_binding"] = stable_bindings[str(fact["numeric_ref"])]
    current_evidence, current_materials, _, _ = _alias_indexes(current_case_input)
    for addition in rebound_additions:
        aliases = [str(value) for value in addition.get("evidence_aliases") or ()]
        material_alias = str(addition.get("source_material_alias") or "")
        source_token = str(addition.get("source_token") or "")
        exact_value = Decimal(str(addition.get("exact_value") or ""))
        normalized_source = source_token.replace("%", "").replace(",", "").strip()
        _require(
            addition.get("unit") == "percent"
            and aliases
            and all(alias in current_evidence for alias in aliases)
            and material_alias in current_materials
            and source_token in str(current_materials[material_alias].get("source_text") or "")
            and Decimal(normalized_source) == exact_value,
            "changed_input_repair_numeric_source_binding_invalid",
        )
        numeric.setdefault("source_numeric_facts", []).append(
            {
                "numeric_ref": str(addition.get("numeric_ref") or ""),
                "semantic_name_zh": str(addition.get("semantic_name_zh") or ""),
                "exact_value": format(exact_value, "f"),
                "unit": "percent",
                "period_id": str(addition.get("period_id") or ""),
                "evidence_aliases": aliases,
                "source_material_alias": material_alias,
                "source_token": source_token,
                "relationship_boundary": str(
                    addition.get("relationship_boundary") or ""
                ),
                "authority": "source_bound_numeric_fact",
                "stable_binding": deepcopy(
                    dict(addition.get("stable_binding") or {})
                ),
                "display_surfaces": [
                    {
                        "presentation_ref": (
                            f"PRES:{str(addition['numeric_ref'])[4:]}:PERCENT_SOURCE"
                        ),
                        "numeric_token": format(exact_value, "f") + "%",
                        "rendered": format(exact_value, "f") + "%",
                        "operation": "identity",
                        "operand": "1",
                    }
                ],
            }
        )
    for addition in repair_policy.get("numeric_surface_additions") or ():
        numeric_ref = str(addition.get("numeric_ref") or "")
        fact = next(
            (
                row
                for row in numeric.get("source_numeric_facts") or ()
                if row.get("numeric_ref") == numeric_ref
            ),
            None,
        )
        _require(
            fact is not None
            and addition.get("operation") == "absolute_magnitude_then_divide",
            "changed_input_numeric_surface_target_invalid",
        )
        presentation_ref = (
            f"PRES:{numeric_ref[4:]}:{addition['presentation_suffix']}"
        )
        fact.setdefault("display_surfaces", []).append(
            {
                "presentation_ref": presentation_ref,
                "numeric_token": str(addition.get("expected_numeric_token") or ""),
                "rendered": str(addition.get("rendered") or ""),
                "operation": str(addition.get("operation") or ""),
                "operand": str(addition.get("operand") or ""),
                "semantic_boundary": str(
                    addition.get("semantic_boundary") or ""
                ),
            }
        )
    _append_market_numeric_fact(numeric, pack=pack, case_input=current_case_input)
    numeric["schema_version"] = NUMERIC_AUTHORITY_SCHEMA
    numeric["rules"] = {
        "stable_identity_rebinding": "target_id_and_source_record_id",
        "source_or_transformed_surface_requires_numeric_ref": True,
        "presentation_ref_selection": "optional_redundant_alias",
        "derived_surface_requires_formula_ref": True,
        "num_ref_authorizes_linked_deterministic_surfaces": True,
        "free_arithmetic": "forbidden_fail_closed",
        "presentation_aliases_are_case_local": True,
        "market_close_does_not_authorize_valuation_multiple_or_target_price": True,
    }
    numeric["comparison_contract_ref"] = str(contract.get("contract_ref") or "")
    return {**numeric, "numeric_authority_digest": canonical_digest(numeric)}


def compile_changed_input_case(
    *,
    contract: Mapping[str, Any],
    repo_root: str | Path,
    artifact_path: str | Path | None = None,
    historical_artifact_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    bindings = dict(contract.get("immutable_bindings") or {})
    fixed_contract_path = _resolve(
        root, str(bindings["fixed_pack_contract"]["ref"])
    )
    profile_path = _resolve(root, str(bindings["provider_profile"]["ref"]))
    fixed_contract = load_fixed_pack_contract(fixed_contract_path, repo_root=root)
    profile = load_fixed_pack_profile(profile_path)
    corrected_result, pack = load_corrected_dell_pack(
        contract=contract,
        repo_root=root,
        artifact_path=artifact_path,
    )
    base_input = compile_case_model_input(
        contract=fixed_contract,
        profile=profile,
        pack=pack,
    )
    historical_case_input = load_historical_dell_case_input(
        fixed_contract=fixed_contract,
        profile=profile,
        repo_root=root,
        artifact_path=historical_artifact_path,
    )
    historical_numeric_contract = _read_json(
        _resolve(root, str(bindings["historical_numeric_contract"]["ref"])),
        "changed_input_historical_numeric_contract_invalid",
    )
    _require(
        historical_numeric_contract.get("case_key") == "DELL"
        and bool(historical_numeric_contract.get("numeric_authority")),
        "changed_input_historical_numeric_contract_identity_invalid",
    )
    repair_policy = load_numeric_verifier_repair_policy(
        _resolve(root, str(bindings["numeric_verifier_repair_policy"]["ref"])),
        repo_root=root,
    )
    body = deepcopy(dict(base_input))
    body.pop("model_visible_digest", None)
    body["numeric_authority"] = compile_changed_input_numeric_authority(
        contract=contract,
        historical_case_input=historical_case_input,
        current_case_input=base_input,
        pack=pack,
        historical_numeric_contract=historical_numeric_contract,
        repair_policy=repair_policy,
    )
    body["model_rules"] = {
        **deepcopy(dict(body.get("model_rules") or {})),
        "material_number_requires_numeric_ref": True,
        "num_ref_authorizes_linked_deterministic_surfaces": True,
        "presentation_ref_selection": "optional",
        "derived_number_requires_formula_ref": True,
        "valuation_requires_more_than_market_close": True,
    }
    value = {**body, "model_visible_digest": canonical_digest(body)}
    validate_case_model_input(value, profile=profile)
    validate_changed_input_case(
        value,
        contract=contract,
        corrected_result=corrected_result,
        profile=profile,
    )
    return {
        "contract": deepcopy(dict(contract)),
        "profile": profile,
        "corrected_pack_result": corrected_result,
        "pack": pack,
        "case_input": value,
        "historical_case_input_digest": historical_case_input[
            "model_visible_digest"
        ],
    }


def validate_changed_input_case(
    value: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
    corrected_result: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> None:
    validate_case_model_input(value, profile=profile)
    numeric = deepcopy(dict(value.get("numeric_authority") or {}))
    digest = str(numeric.pop("numeric_authority_digest", ""))
    facts = [dict(row) for row in numeric.get("source_numeric_facts") or ()]
    formulas = [dict(row) for row in numeric.get("formula_traces") or ()]
    targets = {
        str(row.get("target_id") or "")
        for row in value.get("evidence_items") or ()
    }
    refs = [str(row.get("numeric_ref") or "") for row in facts]
    _require(
        value.get("case_key") == "DELL"
        and value.get("source_pack_digest")
        == corrected_result.get("corrected_pack_payload_digest")
        and len(value.get("evidence_items") or ()) == 27
        and len(value.get("source_materials") or ()) == 27
        and len(value.get("residual_gaps") or ()) == 14
        and REQUIRED_SUPPLEMENT_TARGETS <= targets,
        "changed_input_case_population_or_pack_binding_invalid",
    )
    _require(
        numeric.get("schema_version") == NUMERIC_AUTHORITY_SCHEMA
        and numeric.get("case_key") == "DELL"
        and digest == canonical_digest(numeric)
        and len(facts) == 15
        and len(formulas) == 4
        and len(refs) == len(set(refs))
        and "NUM:DELL:MARKET:2026-08-06:RAW_CLOSE" in refs
        and all(dict(row.get("stable_binding") or {}) for row in facts[:-1]),
        "changed_input_numeric_authority_population_or_digest_invalid",
    )
    _require(
        value.get("model_rules", {}).get("valuation_requires_more_than_market_close")
        is True
        and "successor_boundary" not in value
        and "predecessor_outputs" not in value,
        "changed_input_fresh_model_boundary_invalid",
    )


def validate_changed_input_clean_proof(proof: Mapping[str, Any]) -> None:
    body = deepcopy(dict(proof))
    digest = str(body.pop("proof_digest", ""))
    counts = dict(proof.get("observed_counts") or {})
    mutations = dict(proof.get("mutations") or {})
    _require(
        proof.get("schema_version") == PROOF_SCHEMA
        and proof.get("run_scope") == RUN_SCOPE
        and proof.get("status")
        == "clean_independent_changed_input_thirteen_node_proof_passed"
        and digest == canonical_digest(body)
        and proof.get("fresh_worker_count") == 2
        and proof.get("workers_byte_equivalent") is True,
        "changed_input_clean_proof_identity_or_digest_invalid",
    )
    _require(
        counts.get("fixture_provider_calls_per_worker") == 13
        and counts.get("request_captures_per_worker") == 13
        and counts.get("response_captures_per_worker") == 13
        and counts.get("real_provider_calls") == 0
        and counts.get("model_calls") == 0
        and counts.get("network_calls") == 0
        and counts.get("retries") == 0
        and counts.get("fallbacks") == 0
        and mutations
        and all(value is True for value in mutations.values()),
        "changed_input_clean_proof_population_or_mutation_invalid",
    )


def issue_changed_input_model_authority(
    *,
    admission: Mapping[str, Any],
    clean_proof: Mapping[str, Any],
    implementation_commit: str,
    implementation_bindings: Sequence[Mapping[str, Any]],
    project_os_preflight: Mapping[str, Any],
    user_authority: str,
    recorded_at: str,
) -> dict[str, Any]:
    validate_changed_input_clean_proof(clean_proof)
    _require(
        admission.get("case_key") == "DELL"
        and admission.get("execution_mode") == "live"
        and admission.get("credential_present") is True
        and admission.get("promotion_authority") is False
        and admission.get("node_order") == list(NODE_ORDER)
        and admission.get("case_input_digest")
        == clean_proof.get("case_input_digest")
        and admission.get("source_pack_digest")
        == clean_proof.get("source_pack_digest"),
        "changed_input_authority_admission_scope_invalid",
    )
    _require(
        project_os_preflight.get("status") == "pass"
        and project_os_preflight.get("run_scope") == RUN_SCOPE
        and project_os_preflight.get("open_full_chain_blocker_count") == 0,
        "changed_input_authority_project_os_preflight_invalid",
    )
    bindings = [deepcopy(dict(row)) for row in implementation_bindings]
    _require(
        bindings
        and all(
            str(row.get("ref") or "") and str(row.get("sha256") or "")
            for row in bindings
        )
        and bool(user_authority.strip()),
        "changed_input_authority_implementation_or_user_binding_invalid",
    )
    body = {
        "schema_version": AUTHORITY_SCHEMA,
        "decision_id": "FIN-0.1.3-S2-DELL-CHANGED-INPUT-R1-AUTHORITY",
        "recorded_at": recorded_at,
        "status": "issued_unconsumed",
        "run_scope": RUN_SCOPE,
        "case_key": "DELL",
        "comparison_type": "changed_input_information_increment_not_model_ab",
        "user_authority": user_authority,
        "clean_proof_digest": clean_proof["proof_digest"],
        "implementation_commit": implementation_commit,
        "implementation_bindings": bindings,
        "project_os_preflight": {
            "status": project_os_preflight["status"],
            "run_scope": project_os_preflight["run_scope"],
            "open_full_chain_blocker_count": project_os_preflight[
                "open_full_chain_blocker_count"
            ],
        },
        "admission": deepcopy(dict(admission)),
        "execution_ceiling": {
            "cases": 1,
            "fresh_model_nodes": len(NODE_ORDER),
            "provider_calls": len(NODE_ORDER),
            "model_calls": len(NODE_ORDER),
            "source_calls": 0,
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "old_model_nodes_reused": 0,
            "business_promotions": 0,
        },
        "maximum_executions": 1,
        "automatic_replacement": False,
        "same_input_internal_direct_baseline": True,
        "same_input_with_prior_report": False,
        "known_boundary": (
            "This authority permits one fresh thirteen-node Dell DeepSeek Pro run on "
            "the corrected Pack. It authorizes no source call, old-node reuse, retry, "
            "automatic replacement, business promotion or release."
        ),
    }
    return {**body, "authority_digest": canonical_digest(body)}


def validate_changed_input_model_authority(
    authority: Mapping[str, Any],
    *,
    clean_proof: Mapping[str, Any],
    case_input: Mapping[str, Any],
    profile: Mapping[str, Any],
    repo_root: str | Path,
    observed_at: str,
) -> None:
    validate_changed_input_clean_proof(clean_proof)
    body = deepcopy(dict(authority))
    digest = str(body.pop("authority_digest", ""))
    _require(
        authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("status") == "issued_unconsumed"
        and authority.get("run_scope") == RUN_SCOPE
        and authority.get("case_key") == "DELL"
        and authority.get("comparison_type")
        == "changed_input_information_increment_not_model_ab"
        and digest == canonical_digest(body)
        and authority.get("clean_proof_digest") == clean_proof.get("proof_digest")
        and authority.get("automatic_replacement") is False
        and authority.get("same_input_with_prior_report") is False,
        "changed_input_authority_identity_or_digest_invalid",
    )
    _require(
        authority.get("execution_ceiling")
        == {
            "cases": 1,
            "fresh_model_nodes": 13,
            "provider_calls": 13,
            "model_calls": 13,
            "source_calls": 0,
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "old_model_nodes_reused": 0,
            "business_promotions": 0,
        }
        and authority.get("maximum_executions") == 1,
        "changed_input_authority_execution_ceiling_invalid",
    )
    root = Path(repo_root).resolve()
    for binding in authority.get("implementation_bindings") or ():
        path = _resolve(root, str(binding.get("ref") or ""))
        _require(
            path.is_file() and file_sha256(path) == str(binding.get("sha256") or ""),
            "changed_input_authority_implementation_binding_drift",
        )
    admission = dict(authority.get("admission") or {})
    validate_case_admission(
        admission,
        case_input=case_input,
        profile=profile,
        execution_git_commit=str(authority.get("implementation_commit") or ""),
        runner_sha256=str(admission.get("runner_sha256") or ""),
        contract_sha256=str(admission.get("contract_sha256") or ""),
        profile_sha256=str(admission.get("profile_sha256") or ""),
        observed_at=observed_at,
    )


def build_changed_input_public_result(
    *,
    authority: Mapping[str, Any],
    terminal: Mapping[str, Any],
    private_terminal_path: str | Path,
    comparison_contract: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    private_path = Path(private_terminal_path).resolve()
    _require(
        private_path.is_file(),
        "changed_input_result_private_terminal_missing",
    )
    findings = [dict(row) for row in terminal.get("findings") or ()]
    receipts = [dict(row) for row in terminal.get("call_receipts") or ()]
    prior = dict(
        (comparison_contract.get("immutable_bindings") or {}).get(
            "prior_model_result"
        )
        or {}
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "recorded_at": recorded_at,
        "run_scope": RUN_SCOPE,
        "comparison_type": authority["comparison_type"],
        "authority_digest": authority["authority_digest"],
        "admission_digest": authority["admission"]["admission_digest"],
        "run_id": terminal["run_id"],
        "attempt_id": terminal["attempt_id"],
        "case_key": terminal["case_key"],
        "case_input_digest": terminal["case_input_digest"],
        "source_pack_digest": terminal["source_pack_digest"],
        "prior_model_result_digest": prior["expected_result_digest"],
        "status": terminal["status"],
        "terminal_phase": terminal["terminal_phase"],
        "terminal_code": terminal["terminal_code"],
        "observed_counts": deepcopy(dict(terminal["observed_counts"])),
        "usage": {
            "input_tokens": sum(int(row.get("input_tokens") or 0) for row in receipts),
            "output_tokens": sum(int(row.get("output_tokens") or 0) for row in receipts),
            "total_tokens": sum(int(row.get("total_tokens") or 0) for row in receipts),
            "estimated_usd": terminal["observed_counts"].get("estimated_usd"),
        },
        "call_receipts": [
            {
                "call_id": row.get("call_id"),
                "node_key": row.get("node_key"),
                "capture_digest": row.get("capture_digest"),
                "request_digest": row.get("request_digest"),
                "status": row.get("status"),
                "finish_reason": row.get("finish_reason"),
            }
            for row in receipts
        ],
        "finding_summary": {
            "L1": sum(row.get("level") == "L1" for row in findings),
            "L2": sum(row.get("level") == "L2" for row in findings),
            "L3": sum(row.get("level") == "L3" for row in findings),
            "L4": sum(row.get("level") == "L4" for row in findings),
            "codes": sorted({str(row.get("code") or "") for row in findings}),
        },
        "fresh_model_nodes": len(receipts),
        "old_model_nodes_reused": 0,
        "internal_direct_and_agent_same_input": terminal["same_input_pair_proven"],
        "prior_report_same_input": False,
        "business_artifact_promoted": terminal["business_artifact_promoted"],
        "raw_model_output_public": False,
        "raw_model_output_stored_private": True,
        "private_terminal": {
            "ref": private_path.relative_to(Path.cwd().resolve()).as_posix()
            if private_path.is_relative_to(Path.cwd().resolve())
            else private_path.as_posix(),
            "sha256": file_sha256(private_path),
            "terminal_digest": terminal["terminal_digest"],
        },
        "assessment_status": "pending_post_terminal_business_content_comparison",
        "known_boundary": (
            "This result preserves a raw changed-input candidate. A separate business "
            "content audit must determine whether source increment improved judgment; "
            "no delivery, Owner acceptance or release is authorized."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "AUTHORITY_SCHEMA",
    "CONTRACT_SCHEMA",
    "NUMERIC_AUTHORITY_SCHEMA",
    "PROOF_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "S2DellChangedInputComparisonError",
    "build_changed_input_public_result",
    "compile_changed_input_case",
    "compile_changed_input_numeric_authority",
    "issue_changed_input_model_authority",
    "load_changed_input_comparison_contract",
    "load_corrected_dell_pack",
    "load_historical_dell_case_input",
    "rebind_numeric_declaration",
    "validate_changed_input_case",
    "validate_changed_input_clean_proof",
    "validate_changed_input_model_authority",
]
