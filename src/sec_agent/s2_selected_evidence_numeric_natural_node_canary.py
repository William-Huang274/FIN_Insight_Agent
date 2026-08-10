from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence

from sec_agent.s2_dell_changed_input_model_comparison import (
    compile_changed_input_case,
    load_changed_input_comparison_contract,
)
from sec_agent.s2_selected_evidence_numeric_cocompilation import (
    canonical_digest,
    compile_selected_evidence_numeric_cocompilation,
    evaluate_delivery_numeric_authority,
    load_numeric_cocompilation_policy,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "policy_v1_0"
)
CONTRACT_REF = (
    "fin_0_1_3.S2.selected_evidence_numeric_natural_node_canary:v1"
)
INPUT_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "input_v1_0"
)
REQUEST_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "request_v1_0"
)
ADMISSION_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "admission_v1_0"
)
CAPTURE_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "capture_v1_0"
)
TERMINAL_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "terminal_result_v1_0"
)
ZERO_CALL_SCOPE = (
    "FIN_0_1_3_S2_SELECTED_EVIDENCE_NUMERIC_NATURAL_NODE_CANARY_ZERO_CALL"
)
ProviderCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]

_MATERIAL_FINANCIAL_SURFACE = re.compile(
    r"(?:US\$|USD|EUR|\$|€)\s*\d|\d[\d,.]*\s*%|"
    r"(?:customer\s+count|customers?|systems?|servers?|units?|shipments?)"
    r"[^.\n]{0,32}\d|\d[\d,.]*\s+"
    r"(?:customers?|systems?|servers?|units?|shipments?)\b",
    re.IGNORECASE,
)


class SelectedEvidenceNumericNaturalNodeCanaryError(RuntimeError):
    """Typed fail-closed error for the bounded natural-node canary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SelectedEvidenceNumericNaturalNodeCanaryError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectedEvidenceNumericNaturalNodeCanaryError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve(root: Path, ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _load_bound_json(
    *, root: Path, binding: Mapping[str, Any], code: str
) -> tuple[Path, dict[str, Any]]:
    path = _resolve(root, str(binding.get("ref") or ""))
    _require(path.is_file(), f"{code}_missing")
    _require(
        _file_sha256(path) == str(binding.get("sha256") or ""),
        f"{code}_sha256_drift",
    )
    return path, _read_json(path, f"{code}_json_invalid")


def load_canary_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path).resolve(), "natural_node_canary_policy_invalid")
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("owner_stage") == "S2"
        and policy.get("zero_call_run_scope") == ZERO_CALL_SCOPE,
        "natural_node_canary_policy_identity_invalid",
    )
    bindings = dict(policy.get("immutable_bindings") or {})
    _require(
        set(bindings)
        == {
            "authority_decision",
            "cocompilation_clean_proof",
            "cocompilation_policy",
            "dell_changed_input_contract",
            "provider_profile",
        },
        "natural_node_canary_policy_bindings_invalid",
    )
    decision_path, decision = _load_bound_json(
        root=root,
        binding=dict(bindings["authority_decision"]),
        code="natural_node_canary_decision_binding",
    )
    _decision_body = {
        key: value for key, value in decision.items() if key != "decision_digest"
    }
    _require(
        decision.get("decision_digest")
        == bindings["authority_decision"].get("expected_decision_digest")
        == canonical_digest(_decision_body)
        and decision.get("status")
        == "decision_complete_authorize_zero_call_canary_implementation_and_clean_proof_only",
        "natural_node_canary_decision_invalid",
    )
    _proof_path, proof = _load_bound_json(
        root=root,
        binding=dict(bindings["cocompilation_clean_proof"]),
        code="natural_node_canary_clean_proof_binding",
    )
    _require(
        proof.get("result_digest")
        == bindings["cocompilation_clean_proof"].get("expected_result_digest")
        and dict(proof.get("stage_acceptance") or {}).get(
            "clean_independent_proof"
        )
        is True,
        "natural_node_canary_clean_proof_invalid",
    )
    hard = dict(policy.get("hard_boundaries") or {})
    budget = dict(policy.get("request_budget") or {})
    _require(
        hard.get("capture_before_parse_or_validation") is True
        and hard.get("exact_once_admission") is True
        and hard.get("raw_source_text_in_model_input") is False
        and hard.get("business_artifact_promotion") is False
        and hard.get("live_authority_issued_by_this_policy") is False
        and hard.get("automatic_rerun") is False
        and all(
            int(budget.get(key, -1)) == 0
            for key in ("source_calls", "network_tool_calls", "retries", "fallbacks")
        ),
        "natural_node_canary_policy_boundary_invalid",
    )
    policy["_resolved_decision_ref"] = decision_path.relative_to(root).as_posix()
    return policy


def _compile_request(
    *, compiled_input: Mapping[str, Any], profile: Mapping[str, Any], policy: Mapping[str, Any]
) -> dict[str, Any]:
    output_contract = dict(compiled_input["output_contract"])
    system = (
        "You are a bounded financial-research analyst. Return exactly one JSON "
        "object matching output_contract. Use only supplied Evidence and exact "
        "allowed numeric presentations. E018 is competitor read-through, not "
        "direct Dell proof. E023 is a pull-forward boundary, not quantified proof. "
        "Do not write a report, recommendation, valuation or free arithmetic."
    )
    user = json.dumps(compiled_input, ensure_ascii=False, separators=(",", ":"))
    body = {
        "schema_version": REQUEST_SCHEMA,
        "node_key": str(compiled_input["node_id"]),
        "node_type": "research_lead",
        "case_key": str(compiled_input["case_key"]),
        "compiled_input_digest": str(compiled_input["compiled_input_digest"]),
        "model": str(profile["model"]),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "stream": False,
        "enable_thinking": False,
        "max_tokens": int(policy["request_budget"]["maximum_output_tokens"]),
        "response_format": {"type": "json_object"},
        "output_schema_version": str(output_contract["schema_version"]),
    }
    request = {**body, "request_digest": canonical_digest(body)}
    _require(
        len(json.dumps(request, ensure_ascii=False, separators=(",", ":")))
        <= int(policy["request_budget"]["maximum_compiled_request_characters"]),
        "natural_node_canary_request_capacity_exceeded",
    )
    return request


def compile_canary_material(
    *, policy: Mapping[str, Any], repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    bindings = dict(policy.get("immutable_bindings") or {})
    decision_path, decision = _load_bound_json(
        root=root,
        binding=dict(bindings["authority_decision"]),
        code="natural_node_canary_decision_binding",
    )
    cocomp_policy_path, _ = _load_bound_json(
        root=root,
        binding=dict(bindings["cocompilation_policy"]),
        code="natural_node_canary_cocompilation_policy_binding",
    )
    comparison_path, _ = _load_bound_json(
        root=root,
        binding=dict(bindings["dell_changed_input_contract"]),
        code="natural_node_canary_changed_input_contract_binding",
    )
    profile_path, profile = _load_bound_json(
        root=root,
        binding=dict(bindings["provider_profile"]),
        code="natural_node_canary_provider_profile_binding",
    )
    cocomp_policy = load_numeric_cocompilation_policy(cocomp_policy_path)
    comparison = load_changed_input_comparison_contract(
        comparison_path, repo_root=root
    )
    changed = compile_changed_input_case(contract=comparison, repo_root=root)
    result = compile_selected_evidence_numeric_cocompilation(
        pack=changed["pack"], policy=cocomp_policy
    )
    expected = dict(policy.get("expected_cocompilation_bindings") or {})
    _require(
        result.get("result_digest") == expected.get("result_digest")
        and result.get("co_compilation_transaction_digest")
        == expected.get("transaction_digest")
        and result["candidate_inventory"].get("inventory_digest")
        == expected.get("candidate_inventory_digest")
        and result["presentation_program"].get("presentation_program_digest")
        == expected.get("presentation_program_digest")
        and result["node_views"].get("node_views_digest")
        == expected.get("node_views_digest"),
        "natural_node_canary_cocompilation_binding_drift",
    )
    canary = dict(policy["canary"])
    research = dict(result["node_views"]["research_view"])
    evidence_by_alias = {
        str(row.get("evidence_alias") or ""): dict(row)
        for row in research.get("evidence") or ()
    }
    facts_by_ref = {
        str(row.get("numeric_ref") or ""): dict(row)
        for row in research.get("numeric_facts") or ()
    }
    aliases = list(canary["evidence_aliases"])
    allowed_refs = list(canary["required_numeric_refs"]) + list(
        canary["required_one_of_numeric_refs"]
    )
    _require(
        set(aliases) <= set(evidence_by_alias)
        and set(allowed_refs) <= set(facts_by_ref),
        "natural_node_canary_selected_input_missing",
    )
    _require(
        all(
            evidence_by_alias[alias].get("evidence_role")
            == canary["evidence_roles"][alias]
            for alias in aliases
        ),
        "natural_node_canary_evidence_role_drift",
    )
    selected_evidence = []
    for alias in aliases:
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
    numeric_facts = [deepcopy(facts_by_ref[ref]) for ref in allowed_refs]
    input_body = {
        "schema_version": INPUT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "case_key": str(canary["case_key"]),
        "node_id": str(canary["node_id"]),
        "research_question_zh": str(canary["research_question_zh"]),
        "evidence": selected_evidence,
        "numeric_facts": numeric_facts,
        "output_contract": deepcopy(dict(policy["output_contract"])),
        "rules": {
            "support_atom_direct_evidence": "E022",
            "counterevidence_requires_one_of": ["E018", "E023"],
            "readthrough_never_direct_dell_proof": "E018",
            "pull_forward_boundary_never_quantified_proof": "E023",
            "numeric_refs_require_exact_allowed_presentation": True,
            "used_numeric_refs_equals_atom_union": True,
            "free_arithmetic": False,
            "valuation_or_recommendation": False,
        },
        "cocompilation_bindings": deepcopy(expected),
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
        "natural_node_canary_raw_source_text_leak",
    )
    request = _compile_request(
        compiled_input=compiled_input, profile=profile, policy=policy
    )
    return {
        "policy": deepcopy(dict(policy)),
        "decision": decision,
        "decision_ref": decision_path.relative_to(root).as_posix(),
        "profile": profile,
        "profile_ref": profile_path.relative_to(root).as_posix(),
        "cocompilation_result": result,
        "compiled_input": compiled_input,
        "provider_request": request,
    }


def _list_of_unique_strings(value: Any, code: str) -> list[str]:
    _require(isinstance(value, list), code)
    rows = [str(row) for row in value]
    _require(
        all(isinstance(row, str) and row.strip() for row in value)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def validate_canary_output(
    *, output: Mapping[str, Any], material: Mapping[str, Any]
) -> dict[str, Any]:
    policy = dict(material["policy"])
    contract = dict(policy["output_contract"])
    canary = dict(policy["canary"])
    exact_top = set(contract["top_level_fields"])
    _require(
        isinstance(output, Mapping) and set(output) == exact_top,
        "natural_node_canary_output_fields_invalid",
    )
    _require(
        output.get("schema_version") == contract.get("schema_version")
        and output.get("case_key") == canary.get("case_key")
        and output.get("node_id") == canary.get("node_id")
        and output.get("judgment") in contract.get("judgment_enum", []),
        "natural_node_canary_output_identity_invalid",
    )
    serialized = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
    _require(
        len(serialized) <= int(contract["maximum_total_output_characters"]),
        "natural_node_canary_output_capacity_exceeded",
    )
    aliases = set(canary["evidence_aliases"])
    allowed_refs = set(canary["required_numeric_refs"]) | set(
        canary["required_one_of_numeric_refs"]
    )
    atoms: dict[str, dict[str, Any]] = {}
    for key in ("support_atom", "counterevidence_atom", "boundary_atom"):
        value = output.get(key)
        _require(
            isinstance(value, Mapping)
            and set(value) == set(contract["atom_fields"]),
            f"natural_node_canary_{key}_fields_invalid",
        )
        atom = dict(value)
        text = atom.get("text")
        _require(
            isinstance(text, str)
            and bool(text.strip())
            and len(text) <= int(contract["maximum_atom_text_characters"])
            and atom.get("epistemic_state")
            in contract.get("epistemic_state_enum", []),
            f"natural_node_canary_{key}_content_invalid",
        )
        evidence_refs = _list_of_unique_strings(
            atom.get("evidence_refs"),
            f"natural_node_canary_{key}_evidence_refs_invalid",
        )
        numeric_refs = _list_of_unique_strings(
            atom.get("numeric_refs"),
            f"natural_node_canary_{key}_numeric_refs_invalid",
        )
        _require(
            set(evidence_refs) <= aliases and set(numeric_refs) <= allowed_refs,
            f"natural_node_canary_{key}_unknown_ref",
        )
        atom["evidence_refs"] = evidence_refs
        atom["numeric_refs"] = numeric_refs
        atoms[key] = atom
    _require(
        atoms["support_atom"]["evidence_refs"] == ["E022"],
        "natural_node_canary_support_role_invalid",
    )
    _require(
        bool(
            {"E018", "E023"}
            & set(atoms["counterevidence_atom"]["evidence_refs"])
        )
        and not atoms["counterevidence_atom"]["numeric_refs"],
        "natural_node_canary_counterevidence_role_invalid",
    )
    _require(
        atoms["boundary_atom"]["epistemic_state"]
        in {"bounded_inference", "cannot_infer"}
        and not atoms["boundary_atom"]["numeric_refs"],
        "natural_node_canary_boundary_atom_invalid",
    )
    union_refs = set().union(*(set(row["numeric_refs"]) for row in atoms.values()))
    used_refs = _list_of_unique_strings(
        output.get("used_numeric_refs"),
        "natural_node_canary_used_numeric_refs_invalid",
    )
    _require(
        set(used_refs) == union_refs
        and set(canary["required_numeric_refs"]) <= union_refs
        and bool(set(canary["required_one_of_numeric_refs"]) & union_refs),
        "natural_node_canary_numeric_ref_requirements_failed",
    )
    delivery_text = "\n".join(str(row["text"]) for row in atoms.values())
    normalized_text = delivery_text.casefold()
    _require(
        all(
            presentation.casefold() in normalized_text
            for presentation in canary["required_presentations"]
        )
        and any(
            presentation.casefold() in normalized_text
            for presentation in canary["required_one_of_presentations"]
        ),
        "natural_node_canary_required_presentations_missing",
    )
    forbidden = (
        "target price",
        "recommendation",
        "buy rating",
        "sell rating",
        "目标价",
        "投资建议",
        "买入评级",
        "卖出评级",
    )
    _require(
        not any(token in normalized_text for token in forbidden),
        "natural_node_canary_report_or_recommendation_forbidden",
    )
    boundary_text = str(atoms["boundary_atom"]["text"]).casefold()
    insufficiency = [
        str(row).casefold() for row in contract.get("insufficiency_markers") or ()
    ]
    groups = dict(contract.get("boundary_topic_groups") or {})
    matched_groups = sorted(
        key
        for key, terms in groups.items()
        if any(str(term).casefold() in boundary_text for term in terms)
    )
    _require(
        any(marker in boundary_text for marker in insufficiency)
        and len(matched_groups)
        >= int(contract["boundary_required_topic_groups_minimum"]),
        "natural_node_canary_boundary_semantics_missing",
    )
    co_result = dict(material["cocompilation_result"])
    # The shared inventory also contains non-material parser candidates such as
    # bare fiscal-year and table-index digits.  Literal substring matching those
    # against prose would make "FY2027" collide with a context-only "2027", or
    # almost any sentence collide with "3".  Keep the financial guard strict by
    # scoping its candidate-literal branch to selected Evidence and genuinely
    # material money, percent or count surfaces.  The guard's independent money,
    # percent and count scanners remain active for every returned atom.
    selected_aliases = set(canary["evidence_aliases"])
    scoped_inventory = deepcopy(dict(co_result["candidate_inventory"]))
    scoped_inventory["candidates"] = [
        deepcopy(dict(row))
        for row in scoped_inventory.get("candidates") or ()
        if str(row.get("evidence_alias") or "") in selected_aliases
        and _MATERIAL_FINANCIAL_SURFACE.search(str(row.get("source_surface") or ""))
    ]
    numeric_guard = evaluate_delivery_numeric_authority(
        delivery_text=delivery_text,
        used_numeric_refs=used_refs,
        used_formula_refs=[],
        inventory=scoped_inventory,
        presentation_program=dict(co_result["presentation_program"]),
        semantic_verifier_pass=True,
    )
    _require(
        numeric_guard.get("status") == "pass"
        and numeric_guard.get("local_numeric_gate_pass") is True,
        "natural_node_canary_local_numeric_gate_failed",
    )
    body = {
        "status": "pass",
        "case_key": str(output["case_key"]),
        "node_id": str(output["node_id"]),
        "output_digest": canonical_digest(output),
        "used_numeric_refs": sorted(used_refs),
        "used_evidence_refs": sorted(
            set().union(*(set(row["evidence_refs"]) for row in atoms.values()))
        ),
        "boundary_topic_groups": matched_groups,
        "numeric_guard_digest": numeric_guard["guard_result_digest"],
        "business_artifact_promotion": False,
    }
    return {**body, "validation_digest": canonical_digest(body)}


def issue_fixture_admission(
    *,
    material: Mapping[str, Any],
    run_id: str,
    attempt_id: str,
    observed_at: str,
) -> dict[str, Any]:
    _require(run_id.strip() and attempt_id.strip(), "natural_node_canary_run_identity_invalid")
    policy = dict(material["policy"])
    request = dict(material["provider_request"])
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "admission_id": f"fixture::{run_id}::{attempt_id}",
        "authority_kind": "zero_call_test_fixture_only",
        "execution_mode": "fixture",
        "run_scope": ZERO_CALL_SCOPE,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "case_key": policy["canary"]["case_key"],
        "node_id": policy["canary"]["node_id"],
        "compiled_input_digest": material["compiled_input"]["compiled_input_digest"],
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


def validate_canary_admission(
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
        "natural_node_canary_admission_identity_invalid",
    )
    request = dict(material["provider_request"])
    compiled = dict(material["compiled_input"])
    _require(
        admission.get("case_key") == compiled.get("case_key")
        and admission.get("node_id") == compiled.get("node_id")
        and admission.get("compiled_input_digest")
        == compiled.get("compiled_input_digest")
        and admission.get("request_digest") == request.get("request_digest")
        and admission.get("profile_ref") == material["profile"].get("profile_ref")
        and admission.get("provider_calls_maximum") == 1
        and admission.get("model_calls_maximum") == 1
        and all(
            int(admission.get(key, -1)) == 0
            for key in ("source_calls", "network_tool_calls", "retries", "fallbacks")
        ),
        "natural_node_canary_admission_binding_invalid",
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
) -> dict[str, Any]:
    body = {
        "schema_version": TERMINAL_SCHEMA,
        "run_scope": ZERO_CALL_SCOPE,
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "case_key": admission["case_key"],
        "node_id": admission["node_id"],
        "status": status,
        "terminal_phase": phase,
        "terminal_code": code,
        "observed_counts": {
            "provider_calls": 1,
            "model_calls": 1,
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
            "validated/atom_output.json" if output is not None else None
        ),
        "output_digest": canonical_digest(output) if output is not None else None,
        "validation_digest": (
            validation.get("validation_digest") if validation is not None else None
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


def execute_canary(
    *,
    admission: Mapping[str, Any],
    material: Mapping[str, Any],
    provider_call: ProviderCall,
    runtime_root: str | Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    observed_at: str,
) -> dict[str, Any]:
    validate_canary_admission(admission, material=material)
    root = Path(runtime_root).resolve()
    _require(not root.exists(), "natural_node_canary_attempt_root_exists")
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
    except Exception as exc:  # Raw failure is captured; retry is forbidden.
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
    status = str(response.get("status") or "")
    content = str(response.get("content") or "")
    if status != "ok":
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="provider_transport",
            code=f"natural_node_canary_provider_failure:{status or 'unknown'}",
            observed_at=observed_at,
            output=None,
            validation=None,
        )
    finish_reason = str(response.get("finish_reason") or "").casefold()
    if finish_reason != "stop":
        code = (
            "natural_node_canary_incomplete_finish_reason_length"
            if finish_reason == "length"
            else "natural_node_canary_finish_reason_invalid"
        )
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="provider_output",
            code=code,
            observed_at=observed_at,
            output=None,
            validation=None,
        )
    if not content.strip():
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="provider_output",
            code="natural_node_canary_empty_output",
            observed_at=observed_at,
            output=None,
            validation=None,
        )
    try:
        output = json.loads(content)
    except json.JSONDecodeError:
        output = None
    if not isinstance(output, dict):
        return _terminalize(
            admission=admission,
            request=request,
            capture=capture,
            runtime_root=root,
            shared_ledger=shared_ledger,
            status="failed",
            phase="contract_validation",
            code="natural_node_canary_output_json_invalid",
            observed_at=observed_at,
            output=None,
            validation=None,
        )
    try:
        validation = validate_canary_output(output=output, material=material)
    except SelectedEvidenceNumericNaturalNodeCanaryError as exc:
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
            output=None,
            validation=None,
        )
    _atomic_json(root / "validated/atom_output.json", output)
    _atomic_json(root / "validated/validation_receipt.json", validation)
    return _terminalize(
        admission=admission,
        request=request,
        capture=capture,
        runtime_root=root,
        shared_ledger=shared_ledger,
        status="completed",
        phase="terminal",
        code="natural_node_canary_completed_no_promotion",
        observed_at=observed_at,
        output=output,
        validation=validation,
    )


__all__ = [
    "ADMISSION_SCHEMA",
    "CAPTURE_SCHEMA",
    "CONTRACT_REF",
    "INPUT_SCHEMA",
    "POLICY_SCHEMA",
    "REQUEST_SCHEMA",
    "TERMINAL_SCHEMA",
    "ZERO_CALL_SCOPE",
    "SelectedEvidenceNumericNaturalNodeCanaryError",
    "compile_canary_material",
    "execute_canary",
    "issue_fixture_admission",
    "load_canary_policy",
    "validate_canary_admission",
    "validate_canary_output",
]
