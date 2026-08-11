from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping


ATOMIC_FAILURE_TERMINAL_CONTRACT_REF = (
    "fin01.bounded_agent."
    "atomic_failure_terminal_core_and_registered_observation:v1"
)
REGISTERED_FAILURE_OBSERVATION_DESCRIPTOR_REF = (
    "fin01.bounded_agent.failure_observation_descriptor:v1"
)
OBSERVATION_EXTENSION_REJECTED_CODE = (
    "s3_bounded_failure_observation_extension_rejected"
)
S4_STRICT_TRUTH_KERNEL_POLICY_REF = (
    "fin01.s4.strict_truth_kernel.numeric_judgment_selection:v2"
)

_SAFE_CODE = re.compile(r"^[a-z0-9_.:-]{1,180}$")

_REGISTERED_DESCRIPTORS: dict[str, dict[str, Any]] = {
    "case_numeric_authority": {
        "contract_refs": frozenset(
            {
                (
                    "fin01.s4.case_numeric_authority_projection_and_"
                    "deterministic_rendering:v1"
                ),
                (
                    "fin01.s4.case_numeric_authority_projection_and_"
                    "deterministic_rendering:v2"
                ),
            }
        ),
        "acceptance_layer": "L1_hard_integrity",
        "failure_subtypes": frozenset(
            {
                "provider_authored_numeric_token",
                "provider_authored_material_numeric_token",
                "fact_layer_not_array",
                "fact_shape_invalid",
                "numeric_alias_unknown_or_duplicate",
                "canonical_rendering_mismatch",
            }
        ),
    },
    "case_delivery_identity": {
        "contract_refs": frozenset(
            {
                "fin01.s4.case_delivery_identity_projection:v1",
                (
                    "fin01.s4.case_delivery_identity_current_case_aware_"
                    "provider_boundary:v2"
                ),
            }
        ),
        "acceptance_layer": "L1_hard_integrity",
        "failure_subtypes": frozenset(
            {
                "provider_authored_case_entity_token",
                (
                    "provider_narrative_nonlocal_registered_case_"
                    "identity_token"
                ),
                "projection_missing",
                "projection_invalid",
                "title_mismatch",
            }
        ),
    },
    "strict_truth_kernel": {
        "contract_ref": S4_STRICT_TRUTH_KERNEL_POLICY_REF,
        "acceptance_layer": "L1_hard_integrity",
        "failure_subtypes": frozenset(
            {
                "top_level_shape_invalid",
                "program_cell_mismatch",
                "fact_judgment_cardinality_invalid",
                "fact_judgment_shape_invalid",
                "numeric_alias_unknown_or_cross_case",
                "numeric_alias_duplicate",
                "enum_value_invalid",
                "counterevidence_alias_unknown_or_cross_case",
                "counterevidence_alias_duplicate",
                "local_rendering_failed",
            }
        ),
    },
}

_REGISTERED_KEYS = {
    "descriptor_ref",
    "family",
    "contract_ref",
    "acceptance_layer",
    "failure_subtype",
    "field_id",
    "failing_item_count",
    "raw_text_persisted",
    "private_reasoning_persisted",
    "credentials_persisted",
    "stack_persisted",
}
_REGISTERED_OPTIONAL_KEYS = {
    "case_numeric_authority": {
        "validator_rule_code",
        "match_paths",
        "semantic_classes",
        "capture_sequence",
        "provider_phase",
    },
    "case_delivery_identity": {
        "current_case_identity_digest",
        "registered_nonlocal_match_count",
        "provider_phase",
        "segment_id",
    }
}

# Historical descriptors remain validated by the canonical facade. This list
# only distinguishes already-supported telemetry from an unknown extension.
_LEGACY_FAILURE_TELEMETRY_FAMILIES = frozenset(
    {
        "strict_tool_arguments",
        "segmented_specialist_shape",
        "segmented_specialist_text",
        "segmented_specialist_authority",
        "segmented_specialist_fact_authority",
        "segmented_specialist_epistemic_status",
        "research_lead_contract",
        "memo_writer_contract",
        "scoped_identity_contract",
        "verifier_state_machine",
        "profile_artifact_lineage",
    }
)


def registered_failure_observation(
    family: str,
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    descriptor = _REGISTERED_DESCRIPTORS.get(str(family))
    if descriptor is None:
        raise ValueError("failure_observation_descriptor_family_unknown")
    payload = {
        "descriptor_ref": REGISTERED_FAILURE_OBSERVATION_DESCRIPTOR_REF,
        "family": str(family),
        "contract_ref": str(observation.get("contract_ref") or ""),
        "acceptance_layer": str(
            observation.get("acceptance_layer") or ""
        ),
        "failure_subtype": str(
            observation.get("failure_subtype") or ""
        ),
        "field_id": str(observation.get("field_id") or "unspecified"),
        "failing_item_count": observation.get("failing_item_count", 1),
        "raw_text_persisted": False,
        "private_reasoning_persisted": False,
        "credentials_persisted": False,
        "stack_persisted": False,
    }
    if family == "case_delivery_identity":
        for key in _REGISTERED_OPTIONAL_KEYS[family]:
            if key in observation:
                payload[key] = observation[key]
    if family == "case_numeric_authority":
        for key in _REGISTERED_OPTIONAL_KEYS[family]:
            if key in observation:
                payload[key] = observation[key]
    if not is_registered_failure_observation(payload):
        raise ValueError("failure_observation_descriptor_payload_invalid")
    return payload


def is_registered_failure_observation(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    family = str(value.get("family") or "")
    descriptor = _REGISTERED_DESCRIPTORS.get(family)
    if descriptor is None:
        return False
    optional_keys = _REGISTERED_OPTIONAL_KEYS.get(family, set())
    if (
        not _REGISTERED_KEYS.issubset(value)
        or set(value) - _REGISTERED_KEYS - optional_keys
    ):
        return False
    contract_ref_valid = (
        value.get("contract_ref") in descriptor["contract_refs"]
        if "contract_refs" in descriptor
        else value.get("contract_ref") == descriptor["contract_ref"]
    )
    optional_identity_valid = True
    optional_numeric_valid = True
    if family == "case_numeric_authority":
        is_v2 = str(value.get("contract_ref") or "").endswith(":v2")
        v2_keys = _REGISTERED_OPTIONAL_KEYS[family]
        if is_v2:
            optional_numeric_valid = bool(
                v2_keys.issubset(value)
                and value.get("validator_rule_code")
                == "material_numeric_provider_narrative_boundary_v2"
                and isinstance(value.get("match_paths"), list)
                and len(value["match_paths"])
                == int(value.get("failing_item_count") or 0)
                and all(
                    re.fullmatch(
                        r"\$(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])+",
                        str(path),
                    )
                    for path in value["match_paths"]
                )
                and isinstance(value.get("semantic_classes"), list)
                and bool(value["semantic_classes"])
                and all(
                    semantic_class
                    in {
                        "unknown_reporting_period_label",
                        "financial_amount",
                        "percentage",
                        "measurement",
                        "material_numeric_value",
                    }
                    for semantic_class in value["semantic_classes"]
                )
                and type(value.get("capture_sequence")) is int
                and int(value["capture_sequence"]) > 0
                and _SAFE_CODE.fullmatch(
                    str(value.get("provider_phase") or "")
                )
            )
        elif set(value) & v2_keys:
            optional_numeric_valid = False
    if family == "case_delivery_identity":
        if "current_case_identity_digest" in value:
            optional_identity_valid = bool(
                re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(value["current_case_identity_digest"]),
                )
                and type(value.get("registered_nonlocal_match_count"))
                is int
                and int(value["registered_nonlocal_match_count"]) > 0
                and _SAFE_CODE.fullmatch(
                    str(value.get("provider_phase") or "")
                )
                and _SAFE_CODE.fullmatch(
                    str(value.get("segment_id") or "")
                )
            )
    return bool(
        value.get("descriptor_ref")
        == REGISTERED_FAILURE_OBSERVATION_DESCRIPTOR_REF
        and contract_ref_valid
        and value.get("acceptance_layer")
        == descriptor["acceptance_layer"]
        and value.get("failure_subtype")
        in descriptor["failure_subtypes"]
        and _SAFE_CODE.fullmatch(str(value.get("field_id") or ""))
        and type(value.get("failing_item_count")) is int
        and int(value["failing_item_count"]) > 0
        and all(
            value.get(key) is False
            for key in (
                "raw_text_persisted",
                "private_reasoning_persisted",
                "credentials_persisted",
                "stack_persisted",
            )
        )
        and optional_numeric_valid
        and optional_identity_valid
    )


def normalize_optional_failure_observation(
    value: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Discard an unregistered optional extension without vetoing terminal truth."""

    observation = deepcopy(dict(value))
    telemetry = observation.get("failure_telemetry")
    if telemetry is None:
        return observation, False
    telemetry_keys = (
        set(telemetry) if isinstance(telemetry, Mapping) else set()
    )
    legacy_registered_family = (
        next(iter(telemetry_keys))
        if telemetry_keys
        in (
            {"case_numeric_authority"},
            {"case_delivery_identity"},
        )
        else None
    )
    if legacy_registered_family is not None:
        legacy_value = telemetry.get(legacy_registered_family)
        if isinstance(legacy_value, Mapping):
            try:
                observation["failure_telemetry"] = {
                    "registered_observation": (
                        registered_failure_observation(
                            legacy_registered_family,
                            legacy_value,
                        )
                    )
                }
                return observation, False
            except ValueError:
                pass
    registered = (
        telemetry_keys == {"registered_observation"}
        and is_registered_failure_observation(
            telemetry.get("registered_observation")
        )
    )
    legacy = bool(telemetry_keys) and telemetry_keys.issubset(
        _LEGACY_FAILURE_TELEMETRY_FAMILIES
    )
    if registered or legacy:
        return observation, False

    observation.pop("failure_telemetry", None)
    failure_codes = list(observation.get("failure_codes") or ())
    if OBSERVATION_EXTENSION_REJECTED_CODE not in failure_codes:
        failure_codes.append(OBSERVATION_EXTENSION_REJECTED_CODE)
    observation["failure_codes"] = failure_codes
    return observation, True
