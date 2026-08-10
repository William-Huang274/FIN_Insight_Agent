from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.s1_six_case_local_evidence_pack import (
    CASES,
    canonical_digest,
    file_sha256,
    validate_local_evidence_pack,
)


CONTRACT_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0"
PROFILE_SCHEMA = "fin_ia_0_1_3_s2_model_capability_profile_v1_0"
INPUT_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_model_visible_input_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_input_compilation_result_v1_0"


class S2FixedPackResearchError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S2FixedPackResearchError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S2FixedPackResearchError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _resolve(root: Path, ref: str) -> Path:
    path = Path(ref)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def load_fixed_pack_contract(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    contract = _read_json(Path(path), "fixed_pack_contract_json_invalid")
    _require(
        contract.get("schema_version") == CONTRACT_SCHEMA
        and tuple(contract.get("case_order") or ()) == CASES
        and set(contract.get("cases") or {}) == set(CASES),
        "fixed_pack_contract_identity_invalid",
    )
    boundary = dict(contract.get("authority_boundary") or {})
    _require(
        boundary.get("tools_and_network") == "forbidden"
        and boundary.get("rejected_pack_items_visible") is False
        and boundary.get("all_residual_gaps_visible") is True
        and boundary.get("model_may_read_exact_source_numbers") is True
        and boundary.get("model_may_change_authoritative_fact") is False
        and boundary.get("business_artifact_promotion") is False,
        "fixed_pack_contract_authority_boundary_invalid",
    )
    for binding in (contract.get("immutable_inputs") or {}).values():
        ref = str(binding.get("ref") or "")
        path_obj = _resolve(root, ref)
        _require(
            path_obj.is_file()
            and file_sha256(path_obj) == str(binding.get("sha256") or ""),
            "fixed_pack_contract_immutable_input_drift",
        )
        expected_result = str(binding.get("expected_result_digest") or "")
        if expected_result:
            payload = _read_json(path_obj, "fixed_pack_contract_bound_json_invalid")
            _require(
                str(payload.get("result_digest") or "") == expected_result,
                "fixed_pack_contract_semantic_digest_drift",
            )
    return contract


def load_fixed_pack_profile(path: str | Path) -> dict[str, Any]:
    profile = _read_json(Path(path), "fixed_pack_profile_json_invalid")
    capacity = dict(profile.get("capacity") or {})
    _require(
        profile.get("schema_version") == PROFILE_SCHEMA
        and profile.get("provider") == "deepseek"
        and profile.get("model") == "deepseek-v4-pro"
        and profile.get("model_tier") == "pro_not_flash"
        and profile.get("max_transport_attempts") == 1
        and capacity.get("retry_count") == 0
        and capacity.get("fallback_count") == 0,
        "fixed_pack_profile_identity_or_capacity_invalid",
    )
    return profile


def load_frozen_local_packs(
    *,
    contract: Mapping[str, Any],
    repo_root: str | Path,
) -> dict[str, dict[str, Any]]:
    root = Path(repo_root).resolve()
    result_binding = dict(
        (contract.get("immutable_inputs") or {}).get("local_evidence_pack_result") or {}
    )
    result_path = _resolve(root, str(result_binding.get("ref") or ""))
    result = _read_json(result_path, "fixed_pack_result_json_invalid")
    _require(
        str(result.get("result_digest") or "")
        == str(result_binding.get("expected_result_digest") or ""),
        "fixed_pack_result_digest_invalid",
    )
    private_root = _resolve(root, str(contract.get("private_pack_root") or ""))
    references = dict(result.get("pack_artifacts") or {})
    _require(set(references) == set(CASES), "fixed_pack_artifact_case_set_invalid")
    packs: dict[str, dict[str, Any]] = {}
    for case_key in CASES:
        reference = dict(references[case_key])
        path = private_root / str(reference.get("object_key") or "")
        _require(
            path.is_file()
            and file_sha256(path) == str(reference.get("digest") or ""),
            f"fixed_pack_private_artifact_drift:{case_key}",
        )
        pack = _read_json(path, f"fixed_pack_private_artifact_invalid:{case_key}")
        validate_local_evidence_pack(pack)
        _require(
            pack.get("case_key") == case_key
            and pack.get("pack_payload_digest")
            == (result.get("pack_payload_digests") or {}).get(case_key),
            f"fixed_pack_case_binding_invalid:{case_key}",
        )
        packs[case_key] = pack
    return packs


def _slot_binding_view(binding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "slot_id": str(binding.get("slot_id") or ""),
        "facet_ids": list(binding.get("facet_ids") or ()),
        "business_meaning_zh": str(binding.get("business_meaning_zh") or ""),
        "claim_boundary_zh": str(binding.get("claim_boundary_zh") or ""),
    }


def _evidence_view(
    row: Mapping[str, Any],
    *,
    alias: str,
    material_aliases: Mapping[str, str],
) -> dict[str, Any]:
    view: dict[str, Any] = {
        "evidence_alias": alias,
        "target_id": str(row.get("target_id") or ""),
        "object_type": str(row.get("object_type") or ""),
        "disposition": str(row.get("disposition") or ""),
        "evidence_role": str(row.get("evidence_role") or ""),
        "source_record_id": str(row.get("source_record_id") or ""),
        "source_url": str(row.get("source_url") or ""),
        "publication_date": str(row.get("publication_date") or ""),
        "source_reporting_period_end": str(
            row.get("source_reporting_period_end") or ""
        ),
        "relationship_directions": list(row.get("relationship_directions") or ()),
        "slot_bindings": [
            _slot_binding_view(binding) for binding in row.get("slot_bindings") or ()
        ],
        "numeric_use_boundary": str(row.get("numeric_use_boundary") or ""),
        "causal_attribution_authorized": bool(
            row.get("causal_attribution_authorized", False)
        ),
    }
    material_ref = str(row.get("source_material_ref") or "")
    if material_ref:
        view["source_material_alias"] = material_aliases[material_ref]
    if row.get("object_type") == "metric":
        view["structured_metric"] = deepcopy(dict(row.get("structured_metric") or {}))
    if row.get("object_type") == "claim":
        view["claim_text"] = str(row.get("claim_text") or "")
        view["claim_type"] = str(row.get("claim_type") or "")
    return view


def compile_case_model_input(
    *,
    contract: Mapping[str, Any],
    profile: Mapping[str, Any],
    pack: Mapping[str, Any],
) -> dict[str, Any]:
    case_key = str(pack.get("case_key") or "")
    _require(case_key in CASES, "fixed_pack_input_case_invalid")
    case_contract = deepcopy(dict((contract.get("cases") or {}).get(case_key) or {}))
    _require(case_contract, "fixed_pack_input_case_contract_missing")
    validate_local_evidence_pack(pack)

    materials = sorted(
        (dict(row) for row in pack.get("source_materials") or ()),
        key=lambda row: str(row.get("material_ref") or ""),
    )
    material_aliases = {
        str(row["material_ref"]): f"M{index:03d}"
        for index, row in enumerate(materials, start=1)
    }
    material_views = [
        {
            "source_material_alias": material_aliases[str(row["material_ref"])],
            "source_record_id": str(row.get("source_record_id") or ""),
            "source_text": str(row.get("source_text") or ""),
            "source_text_digest": str(row.get("source_text_digest") or ""),
            "source_url": str(row.get("source_url") or ""),
            "source_type": str(row.get("source_type") or ""),
            "source_tier": str(row.get("source_tier") or ""),
            "evidence_owner_ticker": str(row.get("evidence_owner_ticker") or ""),
            "publication_date": str(row.get("publication_date") or ""),
            "period_end": str(row.get("period_end") or ""),
        }
        for row in materials
    ]
    evidence = sorted(
        (dict(row) for row in pack.get("evidence_items") or ()),
        key=lambda row: str(row.get("target_id") or ""),
    )
    evidence_views = [
        _evidence_view(
            row,
            alias=f"E{index:03d}",
            material_aliases=material_aliases,
        )
        for index, row in enumerate(evidence, start=1)
    ]
    gaps = sorted(
        (dict(row) for row in pack.get("residual_gaps") or ()),
        key=lambda row: (str(row.get("slot_id") or ""), str(row.get("facet_id") or "")),
    )
    gap_views = [
        {
            "gap_alias": f"G{index:03d}",
            "gap_id": str(row.get("gap_id") or ""),
            "slot_id": str(row.get("slot_id") or ""),
            "facet_id": str(row.get("facet_id") or ""),
            "gap_code": str(row.get("gap_code") or ""),
            "required_for_current_research": bool(
                row.get("required_for_current_research", False)
            ),
            "business_reason_zh": str(row.get("business_reason_zh") or ""),
            "supplement_direction_zh": str(row.get("supplement_direction_zh") or ""),
        }
        for index, row in enumerate(gaps, start=1)
    ]
    density = (
        "raw_source_text_and_review_boundaries"
        if material_views
        else "reviewed_structured_metrics_and_claims_without_raw_source_text"
    )
    body = {
        "schema_version": INPUT_SCHEMA,
        "contract_ref": str(contract.get("contract_ref") or ""),
        "case_key": case_key,
        "issuer": case_contract["issuer"],
        "research_as_of": case_contract["as_of"],
        "research_objective_zh": case_contract["research_objective_zh"],
        "research_questions_zh": case_contract["research_questions_zh"],
        "mandatory_research_families": list(
            contract.get("mandatory_research_families") or ()
        ),
        "report_section_order": list(contract.get("report_section_order") or ()),
        "input_density": {
            "class": density,
            "raw_source_material_count": len(material_views),
            "accepted_evidence_count": len(evidence_views),
            "residual_gap_count": len(gap_views),
            "interpretation": (
                "Known-case input exposes reviewed raw source excerpts plus evidence boundaries."
                if material_views
                else "Held-out input exposes reviewed metrics and claims only; report depth is input-limited and must not be blamed solely on the model."
            ),
        },
        "evidence_items": evidence_views,
        "source_materials": material_views,
        "residual_gaps": gap_views,
        "model_rules": {
            "cite_only_evidence_aliases": True,
            "preserve_context_boundaries": True,
            "do_not_invent_missing_evidence": True,
            "numbers_may_be_quoted_only_from_cited_evidence_or_bound_source_material": True,
            "derived_number_requires_a_deterministic_trace": True,
            "do_not_change_identity_period_unit_currency_or_relationship_direction": True,
            "separate_fact_inference_hypothesis_and_gap": True,
            "tools_network_and_external_knowledge": "forbidden",
        },
        "source_pack_digest": str(pack.get("pack_payload_digest") or ""),
    }
    compiled = {**body, "model_visible_digest": canonical_digest(body)}
    validate_case_model_input(compiled, profile=profile)
    return compiled


def validate_case_model_input(
    value: Mapping[str, Any],
    *,
    profile: Mapping[str, Any],
) -> None:
    body = deepcopy(dict(value))
    digest = str(body.pop("model_visible_digest", ""))
    evidence = [dict(row) for row in body.get("evidence_items") or ()]
    materials = [dict(row) for row in body.get("source_materials") or ()]
    gaps = [dict(row) for row in body.get("residual_gaps") or ()]
    _require(
        body.get("schema_version") == INPUT_SCHEMA
        and body.get("case_key") in CASES
        and digest == canonical_digest(body),
        "fixed_pack_input_digest_or_identity_invalid",
    )
    _require(
        [row.get("evidence_alias") for row in evidence]
        == [f"E{index:03d}" for index in range(1, len(evidence) + 1)]
        and [row.get("gap_alias") for row in gaps]
        == [f"G{index:03d}" for index in range(1, len(gaps) + 1)]
        and len({row.get("target_id") for row in evidence}) == len(evidence)
        and evidence
        and gaps,
        "fixed_pack_input_alias_or_population_invalid",
    )
    material_aliases = {row.get("source_material_alias") for row in materials}
    _require(
        len(material_aliases) == len(materials)
        and all(str(row.get("source_text") or "") for row in materials)
        and all(
            not row.get("source_material_alias")
            or row.get("source_material_alias") in material_aliases
            for row in evidence
        ),
        "fixed_pack_input_source_material_binding_invalid",
    )
    _require(
        all(
            row.get("publication_date") <= body.get("research_as_of")
            and row.get("causal_attribution_authorized") is False
            and row.get("slot_bindings")
            for row in evidence
        ),
        "fixed_pack_input_evidence_boundary_invalid",
    )
    serialized = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    maximum = int(profile.get("maximum_input_characters_per_call") or 0)
    _require(
        maximum > 0 and len(serialized) <= maximum,
        "fixed_pack_input_capacity_exceeded",
    )
    _require(
        "rejected_items" not in body
        and body.get("model_rules", {}).get("tools_network_and_external_knowledge")
        == "forbidden",
        "fixed_pack_input_forbidden_surface_visible",
    )


def compile_six_case_model_inputs(
    *,
    contract: Mapping[str, Any],
    profile: Mapping[str, Any],
    packs: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _require(set(packs) == set(CASES), "fixed_pack_input_pack_set_invalid")
    compiled = [
        compile_case_model_input(
            contract=contract,
            profile=profile,
            pack=packs[case_key],
        )
        for case_key in CASES
    ]
    summaries = [
        {
            "case_key": row["case_key"],
            "model_visible_digest": row["model_visible_digest"],
            "source_pack_digest": row["source_pack_digest"],
            "input_density_class": row["input_density"]["class"],
            "evidence_items": len(row["evidence_items"]),
            "source_materials": len(row["source_materials"]),
            "residual_gaps": len(row["residual_gaps"]),
            "serialized_characters": len(
                json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            ),
        }
        for row in compiled
    ]
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": str(contract.get("contract_ref") or ""),
        "status": "six_case_model_visible_inputs_compiled_zero_call",
        "case_order": list(CASES),
        "case_summaries": summaries,
        "observed_counts": {
            "cases": len(compiled),
            "evidence_items": sum(row["evidence_items"] for row in summaries),
            "source_materials": sum(row["source_materials"] for row in summaries),
            "residual_gaps": sum(row["residual_gaps"] for row in summaries),
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
        },
        "known_boundary": (
            "Compilation proves immutable, case-bound, model-visible inputs only; "
            "it does not prove model output quality or dynamic research."
        ),
    }
    return compiled, {**body, "result_digest": canonical_digest(body)}


def materialize_six_case_model_inputs(
    *,
    contract: Mapping[str, Any],
    profile: Mapping[str, Any],
    repo_root: str | Path,
    artifact_root: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    packs = load_frozen_local_packs(contract=contract, repo_root=repo_root)
    compiled, result = compile_six_case_model_inputs(
        contract=contract,
        profile=profile,
        packs=packs,
    )
    root = Path(artifact_root).resolve()
    refs: dict[str, dict[str, Any]] = {}
    for row in compiled:
        case_key = str(row["case_key"])
        payload = json.dumps(
            row,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8") + b"\n"
        digest = hashlib.sha256(payload).hexdigest()
        relative = Path("fin-0.1.3") / "s2-fixed-pack-input" / case_key.lower() / "v1" / digest[:2] / digest[2:4] / f"{digest}.json"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            _require(path.read_bytes() == payload, "fixed_pack_input_object_collision")
        else:
            path.write_bytes(payload)
        refs[case_key] = {
            "object_key": relative.as_posix(),
            "digest": digest,
            "byte_size": len(payload),
            "media_type": "application/json",
            "artifact_type": "fixed_pack_model_visible_input",
        }
    public_body = deepcopy(result)
    public_body.pop("result_digest", None)
    public_body["input_artifacts"] = refs
    public_result = {
        **public_body,
        "result_digest": canonical_digest(public_body),
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(public_result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return public_result


__all__ = [
    "CASES",
    "S2FixedPackResearchError",
    "compile_case_model_input",
    "compile_six_case_model_inputs",
    "load_fixed_pack_contract",
    "load_fixed_pack_profile",
    "load_frozen_local_packs",
    "materialize_six_case_model_inputs",
    "validate_case_model_input",
]
