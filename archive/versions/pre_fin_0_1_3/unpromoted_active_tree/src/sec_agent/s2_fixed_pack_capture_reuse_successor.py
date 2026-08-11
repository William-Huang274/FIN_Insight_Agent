from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.s1_six_case_local_evidence_pack import canonical_digest, file_sha256
from sec_agent.s2_fixed_pack_research import validate_case_model_input
from sec_agent.s2_fixed_pack_research_runtime import NODE_ORDER


CONTRACT_SCHEMA = (
    "fin_ia_0_1_3_s2_fixed_pack_capture_reuse_successor_contract_v1_0"
)
SUCCESSOR_INPUT_SCHEMA = (
    "fin_ia_0_1_3_s2_fixed_pack_capture_reuse_model_visible_input_v1_0"
)
NUMERIC_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s2_numeric_presentation_and_formula_authority_v1_0"
)
REPAIRED_SUCCESSOR_INPUT_SCHEMA = (
    "fin_ia_0_1_3_s2_fixed_pack_capture_reuse_model_visible_input_v1_1"
)
REPAIRED_NUMERIC_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s2_numeric_presentation_and_formula_authority_v1_1"
)
REPAIR_POLICY_SCHEMA = (
    "fin_ia_0_1_3_s2_numeric_presentation_compact_verifier_repair_policy_v1_0"
)
PREDECESSOR_IMPORT_SCHEMA = (
    "fin_ia_0_1_3_s2_fixed_pack_predecessor_import_bundle_v1_0"
)
USABLE_PREDECESSOR_NODES = tuple(NODE_ORDER[:5])
SUCCESSOR_NODE_ORDER = tuple(NODE_ORDER[5:])


class S2FixedPackSuccessorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S2FixedPackSuccessorError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S2FixedPackSuccessorError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _resolve(root: Path, ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _decimal(value: Any, code: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise S2FixedPackSuccessorError(code) from exc


def _plain(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _grouped(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    if absolute != absolute.to_integral_value():
        return sign + _plain(absolute)
    return sign + f"{int(absolute):,}"


def load_successor_contract(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    contract = _read_json(Path(path), "fixed_pack_successor_contract_json_invalid")
    predecessor = dict(contract.get("predecessor") or {})
    boundary = dict(contract.get("execution_boundary") or {})
    _require(
        contract.get("schema_version") == CONTRACT_SCHEMA
        and contract.get("case_key") == "DELL"
        and tuple(predecessor.get("usable_node_order") or ())
        == USABLE_PREDECESSOR_NODES
        and tuple(contract.get("successor_node_order") or ())
        == SUCCESSOR_NODE_ORDER,
        "fixed_pack_successor_contract_identity_invalid",
    )
    _require(
        predecessor.get("failed_node") == SUCCESSOR_NODE_ORDER[0]
        and predecessor.get("expected_provider_attempts") == 6
        and predecessor.get("expected_usable_nodes") == 5
        and boundary.get("imported_usable_nodes") == 5
        and boundary.get("predecessor_provider_attempts") == 6
        and boundary.get("successor_provider_calls") == 8
        and boundary.get("combined_provider_attempt_ceiling") == 14
        and boundary.get("logical_node_count") == len(NODE_ORDER)
        and boundary.get("retry_count") == 0
        and boundary.get("fallback_count") == 0
        and boundary.get("semantic_retry") is False
        and boundary.get("business_artifact_promotion") is False
        and boundary.get("paired_baseline_same_input_proven") is False
        and boundary.get("paired_baseline_required_later") is True,
        "fixed_pack_successor_contract_execution_boundary_invalid",
    )
    for name in ("public_result", "private_terminal"):
        binding = dict(predecessor.get(name) or {})
        bound_path = _resolve(root, str(binding.get("ref") or ""))
        _require(
            bound_path.is_file()
            and file_sha256(bound_path) == str(binding.get("sha256") or ""),
            f"fixed_pack_successor_predecessor_{name}_drift",
        )
    return contract


def load_numeric_verifier_repair_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path), "fixed_pack_repair_policy_json_invalid")
    binding = dict(policy.get("base_successor_contract") or {})
    bound_path = _resolve(root, str(binding.get("ref") or ""))
    projection = dict(policy.get("verifier_projection") or {})
    presentation = dict(policy.get("numeric_presentation_rules") or {})
    terminalization = dict(policy.get("terminalization") or {})
    _require(
        policy.get("schema_version") == REPAIR_POLICY_SCHEMA
        and policy.get("owner_stage") == "S2"
        and bound_path.is_file()
        and file_sha256(bound_path) == str(binding.get("sha256") or "")
        and presentation.get("model_selects") == ["NUM", "FORM"]
        and presentation.get("presentation_refs_optional") is True
        and presentation.get("num_ref_authorizes_linked_deterministic_surfaces")
        is True
        and projection.get("claim_id_exact_coverage_required") is True
        and projection.get("claim_text_echo_forbidden") is True
        and terminalization.get("finish_reason_length")
        == "verification_incomplete_hard_failure"
        and terminalization.get("promotion_authority") is False,
        "fixed_pack_repair_policy_identity_or_boundary_invalid",
    )
    _require(
        bool(policy.get("numeric_authority_additions"))
        and bool(policy.get("numeric_surface_additions")),
        "fixed_pack_repair_policy_numeric_addition_missing",
    )
    return policy


def _source_display_surfaces(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    numeric_ref = str(row["numeric_ref"])
    value = _decimal(row["exact_value"], "fixed_pack_numeric_exact_value_invalid")
    unit = str(row["unit"])
    surfaces: list[dict[str, Any]] = []

    def add(
        suffix: str,
        *,
        numeric_token: str,
        rendered: str,
        operation: str,
        operand: str,
    ) -> None:
        surfaces.append(
            {
                "presentation_ref": f"PRES:{numeric_ref[4:]}:{suffix}",
                "numeric_token": numeric_token,
                "rendered": rendered,
                "operation": operation,
                "operand": operand,
            }
        )

    if unit == "USD_million":
        source = _grouped(value)
        billion = value / Decimal("1000")
        yi = value / Decimal("100")
        add(
            "USD_MILLION_SOURCE",
            numeric_token=source,
            rendered=f"USD {source} million",
            operation="identity",
            operand="1",
        )
        add(
            "USD_BILLION",
            numeric_token=_plain(billion),
            rendered=f"USD {_plain(billion)} billion",
            operation="divide",
            operand="1000",
        )
        add(
            "ZH_YI_USD",
            numeric_token=_plain(yi),
            rendered=f"{_plain(yi)} 亿美元",
            operation="divide",
            operand="100",
        )
    elif unit == "USD_billion":
        source = _plain(value)
        yi = value * Decimal("10")
        add(
            "USD_BILLION_SOURCE",
            numeric_token=source,
            rendered=f"USD {source} billion",
            operation="identity",
            operand="1",
        )
        add(
            "ZH_YI_USD",
            numeric_token=_plain(yi),
            rendered=f"{_plain(yi)} 亿美元",
            operation="multiply",
            operand="10",
        )
    elif unit == "percent":
        source = _plain(value)
        add(
            "PERCENT_SOURCE",
            numeric_token=source + "%",
            rendered=source + "%",
            operation="identity",
            operand="1",
        )
    else:
        raise S2FixedPackSuccessorError(
            "fixed_pack_numeric_presentation_unit_unsupported"
        )
    return surfaces


def compile_numeric_authority(
    *,
    base_case_input: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    _require(
        base_case_input.get("case_key") == contract.get("case_key") == "DELL",
        "fixed_pack_numeric_authority_case_mismatch",
    )
    evidence = {
        str(row["evidence_alias"]): dict(row)
        for row in base_case_input.get("evidence_items") or ()
    }
    materials = {
        str(row["source_material_alias"]): dict(row)
        for row in base_case_input.get("source_materials") or ()
    }
    declarations = dict(contract.get("numeric_authority") or {})
    facts: list[dict[str, Any]] = []
    for declaration in declarations.get("source_numeric_facts") or ():
        row = deepcopy(dict(declaration))
        numeric_ref = str(row.get("numeric_ref") or "")
        aliases = [str(value) for value in row.get("evidence_aliases") or ()]
        material_alias = str(row.get("source_material_alias") or "")
        source_token = str(row.get("source_token") or "")
        _require(
            numeric_ref.startswith("NUM:DELL:")
            and aliases
            and all(alias in evidence for alias in aliases)
            and material_alias in materials
            and source_token
            and source_token in str(materials[material_alias].get("source_text") or ""),
            "fixed_pack_numeric_source_binding_invalid",
        )
        _require(
            any(
                str(evidence[alias].get("source_material_alias") or "")
                == material_alias
                for alias in aliases
            ),
            "fixed_pack_numeric_evidence_material_binding_invalid",
        )
        exact_value = _decimal(
            row.get("exact_value"), "fixed_pack_numeric_exact_value_invalid"
        )
        normalized_source = source_token.replace("$", "").replace(
            "billion", ""
        ).strip()
        if normalized_source.startswith("(") and normalized_source.endswith(")"):
            normalized_source = "-" + normalized_source[1:-1]
        normalized_source = normalized_source.replace(",", "").strip()
        _require(
            _decimal(
                normalized_source, "fixed_pack_numeric_source_token_invalid"
            )
            == exact_value,
            "fixed_pack_numeric_source_value_mismatch",
        )
        fact = {
            "numeric_ref": numeric_ref,
            "semantic_name_zh": str(row.get("semantic_name_zh") or ""),
            "exact_value": _plain(exact_value),
            "unit": str(row.get("unit") or ""),
            "period_id": str(row.get("period_id") or ""),
            "evidence_aliases": aliases,
            "source_material_alias": material_alias,
            "source_token": source_token,
            "authority": "source_bound_numeric_fact",
            "display_surfaces": _source_display_surfaces(row),
        }
        facts.append(fact)
    fact_index = {str(row["numeric_ref"]): row for row in facts}
    _require(
        len(fact_index) == len(facts) and facts,
        "fixed_pack_numeric_ref_collision_or_empty",
    )
    formulas: list[dict[str, Any]] = []
    for declaration in declarations.get("formula_programs") or ():
        row = deepcopy(dict(declaration))
        formula_ref = str(row.get("formula_ref") or "")
        inputs = [str(value) for value in row.get("input_numeric_refs") or ()]
        _require(
            formula_ref.startswith("FORM:DELL:")
            and row.get("operation") == "ratio_percent"
            and len(inputs) == 2
            and all(value in fact_index for value in inputs),
            "fixed_pack_formula_contract_invalid",
        )
        numerator = fact_index[inputs[0]]
        denominator = fact_index[inputs[1]]
        _require(
            numerator["unit"] == denominator["unit"]
            and (
                row.get("required_same_period") is not True
                or numerator["period_id"] == denominator["period_id"]
            ),
            "fixed_pack_formula_unit_or_period_mismatch",
        )
        denominator_value = _decimal(
            denominator["exact_value"], "fixed_pack_formula_denominator_invalid"
        )
        _require(denominator_value != 0, "fixed_pack_formula_denominator_zero")
        exact_result = (
            _decimal(numerator["exact_value"], "fixed_pack_formula_input_invalid")
            / denominator_value
            * Decimal("100")
        )
        decimals = int(row.get("display_decimals") or 0)
        quantum = Decimal("1").scaleb(-decimals)
        display_value = exact_result.quantize(quantum, rounding=ROUND_HALF_UP)
        _require(
            _plain(display_value) == str(row.get("expected_display_value") or ""),
            "fixed_pack_formula_expected_value_mismatch",
        )
        evidence_aliases = sorted(
            set(numerator["evidence_aliases"]) | set(denominator["evidence_aliases"])
        )
        formulas.append(
            {
                "formula_ref": formula_ref,
                "semantic_name_zh": str(row.get("semantic_name_zh") or ""),
                "operation": "ratio_percent",
                "input_numeric_refs": inputs,
                "input_values": [
                    numerator["exact_value"],
                    denominator["exact_value"],
                ],
                "period_id": numerator["period_id"],
                "evidence_aliases": evidence_aliases,
                "exact_result": _plain(exact_result.quantize(Decimal("0.000001"))),
                "rounding": {
                    "mode": "ROUND_HALF_UP",
                    "display_decimals": decimals,
                },
                "display_surfaces": [
                    {
                        "presentation_ref": formula_ref,
                        "numeric_token": _plain(display_value) + "%",
                        "rendered": _plain(display_value) + "%",
                        "operation": "ratio_percent",
                    }
                ],
                "authority": "deterministic_formula_program",
            }
        )
    _require(
        len({str(row["formula_ref"]) for row in formulas}) == len(formulas),
        "fixed_pack_formula_ref_collision",
    )
    body = {
        "schema_version": NUMERIC_AUTHORITY_SCHEMA,
        "case_key": "DELL",
        "source_numeric_facts": facts,
        "formula_traces": formulas,
        "rules": {
            "source_exact_surface_requires_numeric_ref": True,
            "transformed_surface_requires_presentation_ref": True,
            "derived_surface_requires_formula_ref": True,
            "free_arithmetic": "forbidden_fail_closed",
            "presentation_aliases_are_case_local": True,
        },
    }
    return {**body, "numeric_authority_digest": canonical_digest(body)}


def compile_successor_case_input(
    *,
    base_case_input: Mapping[str, Any],
    contract: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    validate_case_model_input(base_case_input, profile=profile)
    _require(
        base_case_input.get("case_key") == "DELL"
        and base_case_input.get("model_visible_digest")
        == (contract.get("predecessor") or {}).get("case_input_digest")
        and base_case_input.get("source_pack_digest")
        == (contract.get("predecessor") or {}).get("source_pack_digest"),
        "fixed_pack_successor_base_input_binding_invalid",
    )
    body = deepcopy(dict(base_case_input))
    base_digest = str(body.pop("model_visible_digest"))
    body["schema_version"] = SUCCESSOR_INPUT_SCHEMA
    body["successor_contract_ref"] = str(contract.get("contract_ref") or "")
    body["base_model_visible_digest"] = base_digest
    body["numeric_authority"] = compile_numeric_authority(
        base_case_input=base_case_input,
        contract=contract,
    )
    body["successor_boundary"] = {
        "predecessor_usable_nodes": list(USABLE_PREDECESSOR_NODES),
        "successor_node_order": list(SUCCESSOR_NODE_ORDER),
        "predecessor_outputs_are_raw_context_not_current_numeric_authority": True,
        "copying_predecessor_numeric_surface_without_current_ref": "forbidden",
        "same_evidence_pack": True,
        "same_input_paired_baseline": False,
    }
    body["model_rules"] = {
        **deepcopy(dict(body.get("model_rules") or {})),
        "material_number_requires_numeric_ref": True,
        "transformed_number_requires_presentation_ref": True,
        "derived_number_requires_formula_ref": True,
        "predecessor_numeric_surface_requires_current_rebinding": True,
    }
    value = {**body, "model_visible_digest": canonical_digest(body)}
    validate_successor_case_input(value, profile=profile)
    return value


def compile_repaired_successor_case_input(
    *,
    successor_case_input: Mapping[str, Any],
    repair_policy: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the S2 repair without mutating the historical v1.0 input or run."""

    validate_successor_case_input(successor_case_input, profile=profile)
    _require(
        successor_case_input.get("schema_version") == SUCCESSOR_INPUT_SCHEMA
        and repair_policy.get("schema_version") == REPAIR_POLICY_SCHEMA,
        "fixed_pack_repair_input_generation_invalid",
    )
    body = deepcopy(dict(successor_case_input))
    pre_repair_digest = str(body.pop("model_visible_digest"))
    numeric = deepcopy(dict(body.get("numeric_authority") or {}))
    numeric.pop("numeric_authority_digest", None)
    evidence = {
        str(row.get("evidence_alias") or ""): dict(row)
        for row in body.get("evidence_items") or ()
    }
    materials = {
        str(row.get("source_material_alias") or ""): dict(row)
        for row in body.get("source_materials") or ()
    }
    existing_refs = {
        str(row.get("numeric_ref") or "")
        for row in numeric.get("source_numeric_facts") or ()
    }
    additions: list[dict[str, Any]] = []
    for declaration in repair_policy.get("numeric_authority_additions") or ():
        row = deepcopy(dict(declaration))
        numeric_ref = str(row.get("numeric_ref") or "")
        aliases = [str(value) for value in row.get("evidence_aliases") or ()]
        material_alias = str(row.get("source_material_alias") or "")
        source_token = str(row.get("source_token") or "")
        _require(
            numeric_ref.startswith("NUM:DELL:")
            and numeric_ref not in existing_refs
            and aliases
            and all(alias in evidence for alias in aliases)
            and material_alias in materials
            and source_token
            and source_token in str(materials[material_alias].get("source_text") or ""),
            "fixed_pack_repair_numeric_source_binding_invalid",
        )
        _require(
            any(
                str(evidence[alias].get("source_material_alias") or "")
                == material_alias
                for alias in aliases
            ),
            "fixed_pack_repair_numeric_evidence_material_binding_invalid",
        )
        exact_value = _decimal(
            row.get("exact_value"), "fixed_pack_repair_numeric_exact_value_invalid"
        )
        normalized_source = source_token.replace("%", "").replace(",", "").strip()
        _require(
            _decimal(
                normalized_source,
                "fixed_pack_repair_numeric_source_token_invalid",
            )
            == exact_value,
            "fixed_pack_repair_numeric_source_value_mismatch",
        )
        additions.append(
            {
                "numeric_ref": numeric_ref,
                "semantic_name_zh": str(row.get("semantic_name_zh") or ""),
                "exact_value": _plain(exact_value),
                "unit": str(row.get("unit") or ""),
                "period_id": str(row.get("period_id") or ""),
                "evidence_aliases": aliases,
                "source_material_alias": material_alias,
                "source_token": source_token,
                "relationship_boundary": str(row.get("relationship_boundary") or ""),
                "authority": "source_bound_numeric_fact",
                "display_surfaces": _source_display_surfaces(row),
            }
        )
        existing_refs.add(numeric_ref)
    numeric["schema_version"] = REPAIRED_NUMERIC_AUTHORITY_SCHEMA
    numeric["source_numeric_facts"] = list(
        numeric.get("source_numeric_facts") or ()
    ) + additions
    fact_index = {
        str(row.get("numeric_ref") or ""): row
        for row in numeric["source_numeric_facts"]
    }
    for declaration in repair_policy.get("numeric_surface_additions") or ():
        row = deepcopy(dict(declaration))
        numeric_ref = str(row.get("numeric_ref") or "")
        fact = fact_index.get(numeric_ref)
        value = _decimal(
            (fact or {}).get("exact_value"),
            "fixed_pack_repair_surface_exact_value_invalid",
        )
        expected = _plain(abs(value) / Decimal(str(row.get("operand") or "0")))
        suffix = str(row.get("presentation_suffix") or "")
        presentation_ref = f"PRES:{numeric_ref[4:]}:{suffix}"
        existing_surface_refs = {
            str(surface.get("presentation_ref") or "")
            for source_fact in fact_index.values()
            for surface in source_fact.get("display_surfaces") or ()
        }
        _require(
            fact is not None
            and value < 0
            and fact.get("unit") == "USD_million"
            and row.get("operation") == "absolute_magnitude_then_divide"
            and expected == str(row.get("expected_numeric_token") or "")
            and presentation_ref not in existing_surface_refs,
            "fixed_pack_repair_numeric_surface_addition_invalid",
        )
        fact.setdefault("display_surfaces", []).append(
            {
                "presentation_ref": presentation_ref,
                "numeric_token": expected,
                "rendered": str(row.get("rendered") or ""),
                "operation": "absolute_magnitude_then_divide",
                "operand": str(row.get("operand") or ""),
                "semantic_boundary": str(row.get("semantic_boundary") or ""),
            }
        )
    numeric["rules"] = {
        "source_or_transformed_surface_requires_numeric_ref": True,
        "presentation_ref_selection": "optional_redundant_alias",
        "derived_surface_requires_formula_ref": True,
        "num_ref_authorizes_linked_deterministic_surfaces": True,
        "free_arithmetic": "forbidden_fail_closed",
        "presentation_aliases_are_case_local": True,
    }
    body["numeric_authority"] = {
        **numeric,
        "numeric_authority_digest": canonical_digest(numeric),
    }
    body["schema_version"] = REPAIRED_SUCCESSOR_INPUT_SCHEMA
    body["pre_repair_successor_input_digest"] = pre_repair_digest
    body["repair_policy_ref"] = str(repair_policy.get("policy_ref") or "")
    body["repair_policy_digest"] = canonical_digest(repair_policy)
    model_rules = deepcopy(dict(body.get("model_rules") or {}))
    model_rules.pop("transformed_number_requires_presentation_ref", None)
    model_rules.update(
        {
            "material_number_requires_numeric_ref": True,
            "num_ref_authorizes_linked_deterministic_surfaces": True,
            "presentation_ref_selection": "optional",
            "derived_number_requires_formula_ref": True,
            "predecessor_numeric_surface_requires_current_rebinding": True,
        }
    )
    body["model_rules"] = model_rules
    value = {**body, "model_visible_digest": canonical_digest(body)}
    validate_successor_case_input(value, profile=profile)
    return value


def validate_successor_case_input(
    value: Mapping[str, Any],
    *,
    profile: Mapping[str, Any],
) -> None:
    body = deepcopy(dict(value))
    digest = str(body.pop("model_visible_digest", ""))
    repaired = body.get("schema_version") == REPAIRED_SUCCESSOR_INPUT_SCHEMA
    _require(
        body.get("schema_version")
        in {SUCCESSOR_INPUT_SCHEMA, REPAIRED_SUCCESSOR_INPUT_SCHEMA}
        and body.get("case_key") == "DELL"
        and digest == canonical_digest(body),
        "fixed_pack_successor_input_digest_or_identity_invalid",
    )
    numeric = deepcopy(dict(body.get("numeric_authority") or {}))
    numeric_digest = str(numeric.pop("numeric_authority_digest", ""))
    _require(
        numeric.get("schema_version")
        == (
            REPAIRED_NUMERIC_AUTHORITY_SCHEMA
            if repaired
            else NUMERIC_AUTHORITY_SCHEMA
        )
        and numeric.get("case_key") == "DELL"
        and numeric_digest == canonical_digest(numeric),
        "fixed_pack_numeric_authority_digest_invalid",
    )
    refs: list[str] = []
    for fact in numeric.get("source_numeric_facts") or ():
        refs.append(str(fact.get("numeric_ref") or ""))
        refs.extend(
            str(surface.get("presentation_ref") or "")
            for surface in fact.get("display_surfaces") or ()
        )
    refs.extend(
        str(row.get("formula_ref") or "")
        for row in numeric.get("formula_traces") or ()
    )
    _require(
        refs and len(refs) == len(set(refs)) and all(refs),
        "fixed_pack_numeric_authority_ref_collision",
    )
    if repaired:
        pre_repair_digest = str(body.get("pre_repair_successor_input_digest") or "")
        repair_digest = str(body.get("repair_policy_digest") or "")
        rules = dict(numeric.get("rules") or {})
        model_rules = dict(body.get("model_rules") or {})
        _require(
            len(pre_repair_digest) == 64
            and len(repair_digest) == 64
            and bool(body.get("repair_policy_ref"))
            and rules.get("num_ref_authorizes_linked_deterministic_surfaces")
            is True
            and rules.get("presentation_ref_selection")
            == "optional_redundant_alias"
            and model_rules.get(
                "num_ref_authorizes_linked_deterministic_surfaces"
            )
            is True
            and model_rules.get("presentation_ref_selection") == "optional"
            and "transformed_number_requires_presentation_ref" not in model_rules,
            "fixed_pack_repaired_numeric_or_policy_boundary_invalid",
        )
    base = deepcopy(body)
    base.pop("numeric_authority", None)
    base.pop("successor_boundary", None)
    base.pop("successor_contract_ref", None)
    base.pop("pre_repair_successor_input_digest", None)
    base.pop("repair_policy_ref", None)
    base.pop("repair_policy_digest", None)
    base_digest = str(base.pop("base_model_visible_digest", ""))
    base["schema_version"] = "fin_ia_0_1_3_s2_fixed_pack_model_visible_input_v1_0"
    base_rules = dict(base.get("model_rules") or {})
    for key in (
        "material_number_requires_numeric_ref",
        "transformed_number_requires_presentation_ref",
        "num_ref_authorizes_linked_deterministic_surfaces",
        "presentation_ref_selection",
        "derived_number_requires_formula_ref",
        "predecessor_numeric_surface_requires_current_rebinding",
    ):
        base_rules.pop(key, None)
    base["model_rules"] = base_rules
    validate_case_model_input(
        {**base, "model_visible_digest": base_digest}, profile=profile
    )
    serialized = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    _require(
        len(serialized) <= int(profile.get("maximum_input_characters_per_call") or 0),
        "fixed_pack_successor_input_capacity_exceeded",
    )


def _capture_output(capture: Mapping[str, Any]) -> Any:
    response = dict(capture.get("provider_response") or {})
    content = str(response.get("content") or "").strip()
    _require(
        response.get("status") == "ok" and content,
        "fixed_pack_predecessor_usable_capture_not_ok",
    )
    if content.startswith("```"):
        lines = content.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise S2FixedPackSuccessorError(
            "fixed_pack_predecessor_usable_capture_json_invalid"
        ) from exc
    _require(
        isinstance(value, dict), "fixed_pack_predecessor_usable_capture_not_object"
    )
    return value


def load_predecessor_import_bundle(
    *,
    contract: Mapping[str, Any],
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    predecessor = dict(contract.get("predecessor") or {})
    public_binding = dict(predecessor.get("public_result") or {})
    terminal_binding = dict(predecessor.get("private_terminal") or {})
    public_path = _resolve(root, str(public_binding.get("ref") or ""))
    terminal_path = _resolve(root, str(terminal_binding.get("ref") or ""))
    _require(
        public_path.is_file()
        and file_sha256(public_path) == str(public_binding.get("sha256") or ""),
        "fixed_pack_predecessor_public_result_drift",
    )
    _require(
        terminal_path.is_file()
        and file_sha256(terminal_path) == str(terminal_binding.get("sha256") or ""),
        "fixed_pack_predecessor_private_terminal_drift",
    )
    public = _read_json(public_path, "fixed_pack_predecessor_public_result_invalid")
    terminal = _read_json(
        terminal_path, "fixed_pack_predecessor_private_terminal_invalid"
    )
    public_body = deepcopy(public)
    public_digest = str(public_body.pop("result_digest", ""))
    terminal_body = deepcopy(terminal)
    terminal_body.pop("shared_admission_receipt", None)
    terminal_digest = str(terminal_body.pop("terminal_digest", ""))
    _require(
        public_digest == public_binding.get("result_digest")
        and public_digest == canonical_digest(public_body)
        and terminal_digest == terminal_binding.get("terminal_digest")
        and terminal_digest == canonical_digest(terminal_body),
        "fixed_pack_predecessor_result_or_terminal_digest_invalid",
    )
    _require(
        public.get("status") == terminal.get("status") == "failed"
        and terminal.get("terminal_phase") == predecessor.get("failed_node")
        and terminal.get("run_id") == predecessor.get("run_id")
        and terminal.get("attempt_id") == predecessor.get("attempt_id")
        and terminal.get("case_input_digest")
        == predecessor.get("case_input_digest")
        and terminal.get("source_pack_digest")
        == predecessor.get("source_pack_digest"),
        "fixed_pack_predecessor_terminal_identity_invalid",
    )
    receipts = [dict(row) for row in terminal.get("call_receipts") or ()]
    public_receipts = [dict(row) for row in public.get("call_receipts") or ()]
    _require(
        len(receipts) == predecessor.get("expected_provider_attempts") == 6
        and [row.get("node_key") for row in receipts]
        == list(NODE_ORDER[:6])
        and [row.get("capture_digest") for row in receipts]
        == [row.get("capture_digest") for row in public_receipts],
        "fixed_pack_predecessor_receipt_population_invalid",
    )
    imports: list[dict[str, Any]] = []
    raw_outputs = dict(terminal.get("raw_outputs") or {})
    terminal_root = terminal_path.parent.resolve()
    for receipt in receipts[:5]:
        capture_path = (terminal_root / str(receipt.get("capture_ref") or "")).resolve()
        _require(
            capture_path.is_relative_to(terminal_root) and capture_path.is_file(),
            "fixed_pack_predecessor_capture_path_invalid",
        )
        capture = _read_json(
            capture_path, "fixed_pack_predecessor_capture_json_invalid"
        )
        capture_body = deepcopy(capture)
        capture_digest = str(capture_body.pop("capture_digest", ""))
        _require(
            capture_digest == receipt.get("capture_digest")
            and capture_digest == canonical_digest(capture_body)
            and capture.get("request_digest") == receipt.get("request_digest")
            and capture.get("node_key") == receipt.get("node_key")
            and receipt.get("status") == "ok",
            "fixed_pack_predecessor_capture_digest_or_binding_invalid",
        )
        output = _capture_output(capture)
        node_key = str(receipt["node_key"])
        _require(
            node_key in raw_outputs
            and canonical_digest(output) == canonical_digest(raw_outputs[node_key]),
            "fixed_pack_predecessor_output_digest_mismatch",
        )
        imports.append(
            {
                "node_key": node_key,
                "output": output,
                "output_digest": canonical_digest(output),
                "predecessor_run_id": terminal["run_id"],
                "predecessor_attempt_id": terminal["attempt_id"],
                "predecessor_call_id": receipt["call_id"],
                "capture_ref": str(receipt["capture_ref"]),
                "capture_file_sha256": file_sha256(capture_path),
                "capture_digest": capture_digest,
                "request_digest": receipt["request_digest"],
            }
        )
    failed_receipt = receipts[5]
    failed_capture_path = (
        terminal_root / str(failed_receipt.get("capture_ref") or "")
    ).resolve()
    failed_capture = _read_json(
        failed_capture_path, "fixed_pack_predecessor_failed_capture_invalid"
    )
    failed_body = deepcopy(failed_capture)
    failed_digest = str(failed_body.pop("capture_digest", ""))
    _require(
        failed_receipt.get("node_key") == predecessor.get("failed_node")
        and failed_receipt.get("status") != "ok"
        and failed_capture.get("provider_response", {}).get("status") != "ok"
        and failed_digest == failed_receipt.get("capture_digest")
        and failed_digest == canonical_digest(failed_body)
        and len(imports) == predecessor.get("expected_usable_nodes") == 5,
        "fixed_pack_predecessor_failed_capture_promotion_boundary_invalid",
    )
    body = {
        "schema_version": PREDECESSOR_IMPORT_SCHEMA,
        "case_key": "DELL",
        "predecessor_run_id": terminal["run_id"],
        "predecessor_attempt_id": terminal["attempt_id"],
        "predecessor_terminal_digest": terminal_digest,
        "predecessor_public_result_digest": public_digest,
        "case_input_digest": terminal["case_input_digest"],
        "source_pack_digest": terminal["source_pack_digest"],
        "imported_outputs": imports,
        "failed_attempt_evidence": {
            "node_key": failed_receipt["node_key"],
            "call_id": failed_receipt["call_id"],
            "status": failed_receipt["status"],
            "capture_ref": failed_receipt["capture_ref"],
            "capture_file_sha256": file_sha256(failed_capture_path),
            "capture_digest": failed_digest,
            "promoted_as_usable_output": False,
        },
        "predecessor_usage": deepcopy(dict(terminal.get("observed_counts") or {})),
        "semantic_retry": False,
    }
    return {**body, "import_bundle_digest": canonical_digest(body)}


def imported_output_map(bundle: Mapping[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in bundle.get("imported_outputs") or ()]
    _require(
        tuple(str(row.get("node_key") or "") for row in rows)
        == USABLE_PREDECESSOR_NODES,
        "fixed_pack_predecessor_import_order_invalid",
    )
    return {str(row["node_key"]): deepcopy(row["output"]) for row in rows}


def numeric_reference_index(
    case_input: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    numeric = dict(case_input.get("numeric_authority") or {})
    index: dict[str, dict[str, Any]] = {}
    for fact in numeric.get("source_numeric_facts") or ():
        fact_row = dict(fact)
        numeric_ref = str(fact_row["numeric_ref"])
        index[numeric_ref] = {
            "ref_type": "source_numeric_fact",
            "numeric_tokens": sorted(
                {
                    str(fact_row.get("source_token") or "")
                    .replace("$", "")
                    .replace("billion", "")
                    .strip(),
                    *(
                        str(surface.get("numeric_token") or "")
                        for surface in fact_row.get("display_surfaces") or ()
                    ),
                }
                - {""}
            ),
            "evidence_aliases": list(fact_row.get("evidence_aliases") or ()),
        }
        for surface in fact_row.get("display_surfaces") or ():
            ref = str(surface.get("presentation_ref") or "")
            index[ref] = {
                "ref_type": "presentation_alias",
                "numeric_tokens": [str(surface.get("numeric_token") or "")],
                "evidence_aliases": list(
                    fact_row.get("evidence_aliases") or ()
                ),
                "numeric_ref": numeric_ref,
            }
    for formula in numeric.get("formula_traces") or ():
        row = dict(formula)
        ref = str(row["formula_ref"])
        index[ref] = {
            "ref_type": "deterministic_formula",
            "numeric_tokens": [
                str(surface.get("numeric_token") or "")
                for surface in row.get("display_surfaces") or ()
            ],
            "evidence_aliases": list(row.get("evidence_aliases") or ()),
            "input_numeric_refs": list(row.get("input_numeric_refs") or ()),
        }
    return index


__all__ = [
    "CONTRACT_SCHEMA",
    "NUMERIC_AUTHORITY_SCHEMA",
    "PREDECESSOR_IMPORT_SCHEMA",
    "REPAIRED_NUMERIC_AUTHORITY_SCHEMA",
    "REPAIRED_SUCCESSOR_INPUT_SCHEMA",
    "REPAIR_POLICY_SCHEMA",
    "SUCCESSOR_INPUT_SCHEMA",
    "SUCCESSOR_NODE_ORDER",
    "S2FixedPackSuccessorError",
    "USABLE_PREDECESSOR_NODES",
    "compile_numeric_authority",
    "compile_repaired_successor_case_input",
    "compile_successor_case_input",
    "imported_output_map",
    "load_numeric_verifier_repair_policy",
    "load_predecessor_import_bundle",
    "load_successor_contract",
    "numeric_reference_index",
    "validate_successor_case_input",
]
