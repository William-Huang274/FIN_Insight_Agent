from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s3_dell_value_profit_repair_canary import (
    compile_repair_canary_material,
    load_repair_canary_policy,
)
from sec_agent.s3_dynamic_research_successor import (
    apply_repair_observation,
    record_affected_cell_readjudication,
    validate_s3_dynamic_research_successor_program,
)


POLICY_SCHEMA = "fin_ia_0_1_3_s3_small_judgment_atom_projection_policy_v1_0"
CONTRACT_REF = "fin_0_1_3.S3.small_judgment_atom_deterministic_cell_projection:v1"
INPUT_SCHEMA = "fin_ia_0_1_3_s3_small_judgment_atom_input_v1_0"
REQUEST_SCHEMA = "fin_ia_0_1_3_s3_small_judgment_atom_request_v1_0"

_ALIAS_TOKEN = re.compile(r"(?<![A-Z0-9_])(?:E\d{3,}|NUM:[A-Z0-9:_-]+)(?![A-Z0-9_])")
_FINANCIAL_NUMERIC_SURFACE = re.compile(
    r"\d|%|[$€£¥]|\b(?:mid|low|high)[-\s]+single[-\s]+digit\b|"
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?:percent|percentage\s+points?|billion|million|thousand)\b",
    re.IGNORECASE,
)


class S3SmallJudgmentAtomProjectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S3SmallJudgmentAtomProjectionError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S3SmallJudgmentAtomProjectionError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _normalized_text_sha256(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise S3SmallJudgmentAtomProjectionError(
            "s3_small_atom_bound_text_unreadable"
        ) from exc
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve(root: Path, ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def load_small_judgment_projection_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path).resolve(), "s3_small_atom_policy_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("owner_stage") == "S3",
        "s3_small_atom_policy_identity_invalid",
    )
    bindings = dict(policy.get("immutable_bindings") or {})
    _require(
        set(bindings) == {"predecessor_canary_policy", "failed_live_audit"},
        "s3_small_atom_policy_bindings_invalid",
    )
    for name, binding in bindings.items():
        bound = _resolve(root, str(binding.get("ref") or ""))
        _require(bound.is_file(), f"s3_small_atom_{name}_missing")
        _require(
            _normalized_text_sha256(bound) == str(binding.get("sha256") or ""),
            f"s3_small_atom_{name}_sha256_drift",
        )
    audit = _read_json(
        _resolve(root, str(bindings["failed_live_audit"]["ref"])),
        "s3_small_atom_failed_audit_invalid",
    )
    audit_body = {key: value for key, value in audit.items() if key != "result_digest"}
    _require(
        audit.get("result_digest")
        == bindings["failed_live_audit"].get("expected_result_digest")
        == canonical_digest(audit_body)
        and audit.get("formal_terminal", {}).get("status") == "failed",
        "s3_small_atom_failed_audit_binding_invalid",
    )
    hard = dict(policy.get("hard_boundaries") or {})
    budget = dict(policy.get("request_budget") or {})
    _require(
        hard.get("provider_neutral_core") is True
        and hard.get("deepseek_specific_runtime_branch") is False
        and hard.get("model_owns_research_semantics") is True
        and hard.get("model_owns_internal_cell_state") is False
        and hard.get("local_runtime_owns_state_refs_wwc_numeric_and_writer_control")
        is True
        and hard.get("failed_capture_posthoc_promotion") is False
        and hard.get("second_model_call_authorized") is False
        and hard.get("complete_report_authorized") is False
        and all(
            int(budget.get(key, -1)) == 0
            for key in (
                "model_calls",
                "provider_calls",
                "network_calls",
                "source_calls",
                "retries",
            )
        ),
        "s3_small_atom_policy_boundary_invalid",
    )
    return policy


def _unique_strings(value: Any, code: str) -> list[str]:
    _require(isinstance(value, list), code)
    rows = [str(item) for item in value]
    _require(
        all(isinstance(item, str) and item.strip() for item in value)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def normalize_model_atom(text: Any, *, maximum_characters: int) -> dict[str, Any]:
    _require(
        isinstance(text, str) and bool(text.strip()) and len(text) <= maximum_characters,
        "s3_small_atom_text_invalid",
    )
    aliases = _ALIAS_TOKEN.findall(text)

    def neutral_alias(match: re.Match[str]) -> str:
        return (
            "the cited Evidence"
            if match.group(0).startswith("E")
            else "the bound Numeric fact"
        )

    normalized = _ALIAS_TOKEN.sub(neutral_alias, text)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s+([,.;:])", r"\1", normalized).strip(" ,;:")
    normalized = normalized[:1].upper() + normalized[1:]
    _require(bool(normalized), "s3_small_atom_text_empty_after_alias_normalization")
    _require(
        _FINANCIAL_NUMERIC_SURFACE.search(normalized) is None,
        "s3_small_atom_financial_numeric_surface_forbidden",
    )
    return {
        "normalized_text": normalized,
        "removed_alias_tokens": aliases,
        "normalization_changed_text": normalized != text.strip(),
    }


def _semantic_evidence_view(predecessor_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in predecessor_input.get("current_pack_evidence") or ():
        slot_semantics = []
        for slot in item.get("slot_bindings") or ():
            slot_semantics.append(
                {
                    "slot_id": slot.get("slot_id"),
                    "business_meaning_zh": slot.get("business_meaning_zh"),
                    "claim_boundary_zh": slot.get("claim_boundary_zh"),
                    "facet_ids": deepcopy(list(slot.get("facet_ids") or ())),
                }
            )
        rows.append(
            {
                "evidence_alias": item.get("evidence_alias"),
                "evidence_role": item.get("evidence_role"),
                "relationship_directions": deepcopy(
                    list(item.get("relationship_directions") or ())
                ),
                "slot_semantics": slot_semantics,
                "authorized_numeric_refs": deepcopy(
                    list(item.get("authorized_numeric_refs") or ())
                ),
                "source_text_digest": item.get("source_text_digest"),
            }
        )
    return rows


def _semantic_numeric_view(predecessor_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in predecessor_input.get("numeric_facts") or ():
        rows.append(
            {
                "numeric_ref": item.get("numeric_ref"),
                "semantic_metric_key": item.get("semantic_metric_key"),
                "entity": item.get("entity"),
                "period_or_as_of": item.get("period_or_as_of"),
                "canonical_unit": item.get("canonical_unit"),
                "evidence_aliases": deepcopy(list(item.get("evidence_aliases") or ())),
                "claim_and_output_boundary": item.get("claim_and_output_boundary"),
                "numeric_value_visible_to_model": False,
                "numeric_surface_visible_to_model": False,
            }
        )
    return rows


def compile_small_judgment_material(
    *, policy: Mapping[str, Any], repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    predecessor_ref = policy["immutable_bindings"]["predecessor_canary_policy"]["ref"]
    predecessor_policy = load_repair_canary_policy(
        _resolve(root, str(predecessor_ref)), repo_root=root
    )
    predecessor = compile_repair_canary_material(
        policy=predecessor_policy, repo_root=root
    )
    predecessor_input = dict(predecessor["compiled_input"])
    expected = dict(policy["dell_expected_output"])
    contract = dict(policy["model_output_contract"])
    input_body = {
        "schema_version": INPUT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "case_key": expected["case_key"],
        "node_id": expected["node_id"],
        "repair_request_id": expected["repair_request_id"],
        "research_question_zh": predecessor_input["research_question_zh"],
        "evidence_semantic_views": _semantic_evidence_view(predecessor_input),
        "numeric_authority_views": _semantic_numeric_view(predecessor_input),
        "required_evidence_semantics": deepcopy(
            dict(contract["required_evidence_semantics"])
        ),
        "required_retained_gap_components": deepcopy(
            list(expected["retained_gap_components"])
        ),
        "output_contract": deepcopy(contract),
        "rules": {
            "model_outputs_research_semantics_not_cell_state": True,
            "model_must_not_output_affected_cells_state_changed_refs_or_wwc": True,
            "aliases_belong_in_structured_ref_fields": True,
            "numeric_values_and_presentations_are_local_only": True,
            "valuation_expectations_and_recommendation_forbidden": True,
            "complete_report": False,
        },
        "raw_source_text_in_model_input": False,
        "authoritative_numeric_values_in_model_input": False,
    }
    compiled_input = {**input_body, "compiled_input_digest": canonical_digest(input_body)}
    system = (
        "You are a bounded financial-research judgment-atom adjudicator. Return "
        "exactly one JSON object matching output_contract. Decide Evidence role, "
        "bounded profitability direction, product-versus-segment attribution, and "
        "remaining gaps. Write only one short mechanism atom and one short boundary "
        "atom. Put Evidence and Numeric aliases only in their structured arrays. Do "
        "not output cell ids, judgment states, changed flags, WWC ids, digits, "
        "percentages, numeric bands, valuation, recommendation, or a report."
    )
    request_body = {
        "schema_version": REQUEST_SCHEMA,
        "node_key": expected["node_id"],
        "node_type": "small_judgment_atom_adjudicator",
        "case_key": expected["case_key"],
        "compiled_input_digest": compiled_input["compiled_input_digest"],
        "model": predecessor["profile"]["model"],
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    compiled_input, ensure_ascii=False, separators=(",", ":")
                ),
            },
        ],
        "temperature": 0.0,
        "stream": False,
        "enable_thinking": False,
        "max_tokens": int(
            policy["request_budget"]["maximum_output_tokens_if_later_authorized"]
        ),
        "response_format": {"type": "json_object"},
        "output_schema_version": contract["schema_version"],
    }
    request = {**request_body, "request_digest": canonical_digest(request_body)}
    serialized = json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    _require(
        len(serialized)
        <= int(policy["request_budget"]["maximum_compiled_request_characters"]),
        "s3_small_atom_request_capacity_exceeded",
    )
    _require(
        "authoritative_value" not in json.dumps(compiled_input, ensure_ascii=False)
        and "allowed_presentations" not in json.dumps(compiled_input, ensure_ascii=False),
        "s3_small_atom_numeric_value_leak",
    )
    return {
        "policy": deepcopy(dict(policy)),
        "predecessor": predecessor,
        "compiled_input": compiled_input,
        "provider_request": request,
        "compiled_request_characters": len(serialized),
    }


def validate_small_judgment_output(
    output: Mapping[str, Any], *, policy: Mapping[str, Any]
) -> dict[str, Any]:
    contract = dict(policy["model_output_contract"])
    expected = dict(policy["dell_expected_output"])
    _require(
        isinstance(output, Mapping)
        and set(output) == set(contract["top_level_fields"]),
        "s3_small_atom_output_fields_invalid",
    )
    _require(
        output.get("schema_version") == contract["schema_version"]
        and output.get("case_key") == expected["case_key"]
        and output.get("node_id") == expected["node_id"]
        and output.get("repair_request_id") == expected["repair_request_id"],
        "s3_small_atom_output_identity_invalid",
    )
    _require(
        len(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
        <= int(contract["maximum_total_output_characters"]),
        "s3_small_atom_output_capacity_exceeded",
    )
    _require(
        output.get("observation_outcome") == "accepted"
        and output.get("repair_resolution") == "accepted_partial_resolution",
        "s3_small_atom_disposition_invalid",
    )
    accepted = _unique_strings(
        output.get("accepted_evidence_refs"), "s3_small_atom_accepted_refs_invalid"
    )
    boundary = _unique_strings(
        output.get("boundary_evidence_refs"), "s3_small_atom_boundary_refs_invalid"
    )
    retained = _unique_strings(
        output.get("retained_gap_components"), "s3_small_atom_retained_gaps_invalid"
    )
    numeric = _unique_strings(
        output.get("used_numeric_refs"), "s3_small_atom_numeric_refs_invalid"
    )
    _require(
        accepted == expected["accepted_evidence_refs"]
        and boundary == expected["boundary_evidence_refs"]
        and retained == expected["retained_gap_components"]
        and numeric == expected["used_numeric_refs"],
        "s3_small_atom_ref_or_gap_set_invalid",
    )
    semantics = output.get("evidence_semantics")
    _require(
        isinstance(semantics, Mapping)
        and set(semantics) == set(contract["evidence_semantics_fields"])
        and dict(semantics) == dict(contract["required_evidence_semantics"]),
        "s3_small_atom_evidence_semantics_invalid",
    )
    _require(
        output.get("profitability_direction") == expected["profitability_direction"]
        and output.get("attribution_boundary") == expected["attribution_boundary"],
        "s3_small_atom_financial_boundary_invalid",
    )
    mechanism = normalize_model_atom(
        output.get("mechanism_atom"),
        maximum_characters=int(contract["maximum_atom_text_characters"]),
    )
    boundary_atom = normalize_model_atom(
        output.get("boundary_atom"),
        maximum_characters=int(contract["maximum_atom_text_characters"]),
    )
    body = {
        "status": "pass",
        "case_key": expected["case_key"],
        "node_id": expected["node_id"],
        "output_digest": canonical_digest(output),
        "accepted_evidence_refs": accepted,
        "boundary_evidence_refs": boundary,
        "retained_gap_components": retained,
        "used_numeric_refs": numeric,
        "profitability_direction": output["profitability_direction"],
        "attribution_boundary": output["attribution_boundary"],
        "normalized_atoms": {
            "mechanism_atom": mechanism,
            "boundary_atom": boundary_atom,
        },
        "model_owned_cell_state_fields": [],
        "business_artifact_promotion": False,
    }
    return {**body, "validation_digest": canonical_digest(body)}


def _roles(
    names: list[str], *, accepted: list[str], boundary: list[str], numeric: list[str]
) -> list[str]:
    values: list[str] = []
    for name in names:
        if name == "accepted":
            values.extend(accepted)
        elif name == "boundary":
            values.extend(boundary)
        elif name == "primary_boundary":
            values.extend(boundary[:1])
        elif name == "mix_boundary":
            values.extend(boundary[1:2])
        elif name == "required":
            values.extend(numeric)
        else:
            raise S3SmallJudgmentAtomProjectionError(
                "s3_small_atom_projection_role_invalid"
            )
    return list(dict.fromkeys(values))


def compile_deterministic_cell_rows(
    *, validated: Mapping[str, Any], policy: Mapping[str, Any]
) -> list[dict[str, Any]]:
    expected = dict(policy["dell_expected_output"])
    accepted = list(validated["accepted_evidence_refs"])
    boundary = list(validated["boundary_evidence_refs"])
    numeric = list(validated["used_numeric_refs"])
    atoms = dict(validated["normalized_atoms"])
    local_text = {
        "local_price_in_boundary": (
            "Operating evidence does not establish market expectations or valuation.",
            "Price-in, valuation and recommendation remain unproven.",
        ),
        "local_writer_control": (
            "The report may use the bounded issuer profitability comparison.",
            "The report must preserve product-profit, conversion and valuation gaps.",
        ),
    }
    rows: list[dict[str, Any]] = []
    for template in policy["deterministic_cell_projection"]:
        mechanism_source = str(template["mechanism_source"])
        boundary_source = str(template["boundary_source"])
        mechanism = (
            atoms["mechanism_atom"]["normalized_text"]
            if mechanism_source == "model_mechanism_atom"
            else local_text[mechanism_source][0]
        )
        boundary_text = (
            atoms["boundary_atom"]["normalized_text"]
            if boundary_source == "model_boundary_atom"
            else local_text[boundary_source][1]
        )
        row = {
            "cell_id": template["cell_id"],
            "judgment_state": template["judgment_state"],
            "judgment_changed": template["judgment_changed"],
            "support_refs": _roles(
                list(template["support_ref_roles"]),
                accepted=accepted,
                boundary=boundary,
                numeric=numeric,
            ),
            "counterevidence_refs": _roles(
                list(template["counterevidence_ref_roles"]),
                accepted=accepted,
                boundary=boundary,
                numeric=numeric,
            ),
            "numeric_refs": _roles(
                list(template["numeric_ref_roles"]),
                accepted=accepted,
                boundary=boundary,
                numeric=numeric,
            ),
            "mechanism": mechanism,
            "boundary": boundary_text,
            "wwc_ref": (
                expected["required_wwc_ref"]
                if template["wwc_source"] == "required"
                else ""
            ),
        }
        rows.append(row)
    expected_cell_order = [
        "bottleneck_counterevidence_and_what_would_change",
        "cross_chain_price_in_and_expectations",
        "value_and_profit_capture",
        "writer_admission_boundary",
    ]
    _require(
        [row["cell_id"] for row in rows] == expected_cell_order,
        "s3_small_atom_projection_cell_order_invalid",
    )
    return rows


def project_small_judgment_output(
    *,
    output: Mapping[str, Any],
    material: Mapping[str, Any],
    capture_ref: str,
    capture_digest: str,
) -> dict[str, Any]:
    policy = dict(material["policy"])
    expected = dict(policy["dell_expected_output"])
    validated = validate_small_judgment_output(output, policy=policy)
    observed = apply_repair_observation(
        material["predecessor"]["successor_program"],
        policy=material["predecessor"]["successor_policy"],
        request_id=expected["repair_request_id"],
        observation={
            "outcome": "accepted",
            "capture_ref": capture_ref,
            "capture_digest": capture_digest,
            "evidence_gate_status": "accepted",
            "evidence_ref": expected["accepted_evidence_refs"][0],
        },
    )
    observation = next(
        row
        for row in observed["repair_observations"]
        if row["request_id"] == expected["repair_request_id"]
    )
    rows = compile_deterministic_cell_rows(validated=validated, policy=policy)
    decisions = [
        {**row, "observation_digest": observation["observation_digest"]}
        for row in rows
    ]
    successor = record_affected_cell_readjudication(
        observed,
        policy=material["predecessor"]["successor_policy"],
        request_id=expected["repair_request_id"],
        decisions=decisions,
    )
    validate_s3_dynamic_research_successor_program(
        successor, policy=material["predecessor"]["successor_policy"]
    )
    required_fact = next(
        row
        for row in material["predecessor"]["compiled_input"]["numeric_facts"]
        if row["numeric_ref"] == expected["used_numeric_refs"][0]
    )
    projection_body = {
        "status": "pass",
        "validation": validated,
        "deterministic_cell_rows": rows,
        "local_numeric_projection": {
            "numeric_ref": required_fact["numeric_ref"],
            "rendered": required_fact["allowed_presentations"][0]["rendered"],
            "authority": "local_numeric_presentation_program",
            "model_authored_surface": False,
        },
        "successor_program_digest": successor["program_digest"],
        "readjudication_receipt_digests": sorted(
            row["readjudication_digest"]
            for row in successor["readjudication_receipts"]
            if row["request_id"] == expected["repair_request_id"]
        ),
        "source_calls": 0,
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "business_artifact_promotion": False,
    }
    return {
        **projection_body,
        "projection_digest": canonical_digest(projection_body),
        "successor_program": successor,
    }


def audit_failed_legacy_output(output: Mapping[str, Any]) -> dict[str, Any]:
    rows = {
        str(row.get("cell_id") or ""): dict(row)
        for row in output.get("affected_cell_readjudications") or ()
        if isinstance(row, Mapping)
    }
    target = rows.get("value_and_profit_capture", {})
    price_in = rows.get("cross_chain_price_in_and_expectations", {})
    atoms = [
        str(row.get(field) or "")
        for row in rows.values()
        for field in ("mechanism_atom", "boundary_atom")
    ]
    body = {
        "legacy_output_digest": canonical_digest(output),
        "accepted_evidence_refs_exact": output.get("accepted_evidence_refs")
        == ["E021"],
        "required_numeric_ref_selected": (
            "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D"
            in set(output.get("used_numeric_refs") or ())
        ),
        "target_changed_flag_valid": target.get("judgment_changed") is True,
        "price_in_boundary_valid": (
            price_in.get("judgment_state") == "cannot_infer"
            and price_in.get("judgment_changed") is False
        ),
        "atom_alias_token_count": sum(len(_ALIAS_TOKEN.findall(text)) for text in atoms),
        "failed_output_promotable": False,
    }
    return {**body, "audit_digest": canonical_digest(body)}


def compile_portfolio_shape_receipts(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for fixture in policy["portfolio_shape_fixtures"]:
        body = {
            "case_key": fixture["case_key"],
            "accepted_ref": fixture["accepted_ref"],
            "boundary_refs": list(fixture["boundary_refs"]),
            "numeric_ref": fixture["numeric_ref"],
            "model_owned_fields": [
                "evidence_disposition",
                "profitability_direction",
                "attribution_boundary",
                "retained_gap_enums",
                "mechanism_atom",
                "boundary_atom",
            ],
            "local_owned_fields": [
                "cell_id",
                "judgment_state",
                "judgment_changed",
                "evidence_numeric_wwc_refs",
                "numeric_rendering",
                "writer_admission",
            ],
        }
        receipts.append({**body, "shape_digest": canonical_digest(body)})
    _require(
        [row["case_key"] for row in receipts] == ["DELL", "MU", "NVDA"],
        "s3_small_atom_portfolio_shape_invalid",
    )
    return receipts


__all__ = [
    "S3SmallJudgmentAtomProjectionError",
    "audit_failed_legacy_output",
    "compile_deterministic_cell_rows",
    "compile_portfolio_shape_receipts",
    "compile_small_judgment_material",
    "load_small_judgment_projection_policy",
    "normalize_model_atom",
    "project_small_judgment_output",
    "validate_small_judgment_output",
]
