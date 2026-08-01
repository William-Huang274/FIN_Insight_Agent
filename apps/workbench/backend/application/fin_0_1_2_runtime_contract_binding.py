from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from sec_agent.runtime_contract_governance import (
    LOCAL_TRUTH_FIELDS,
    REQUIRED_COMPILED_CONSUMERS,
    compile_runtime_contract_source,
    validate_runtime_contract_source,
)
from sec_agent.runtime_resource_registry import (
    RuntimeResourceRegistryError,
    read_registered_runtime_bytes,
    read_registered_runtime_json,
)


FIN_0_1_2_COMMON_RUNTIME_BINDING_REF = (
    "fin_0_1_2.common_runtime.judgment_atom_family_binding:v1"
)
FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF = (
    "fin_0_1_2.common_runtime.judgment_atom_family:v1.0.0"
)
FIN_0_1_2_COMMON_RUNTIME_SOURCE_REF = (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "source_v1_0.json"
)
FIN_0_1_2_COMMON_RUNTIME_BINDING_MANIFEST_REF = (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "binding_v1_0.json"
)
FIN_0_1_2_COMMON_RUNTIME_SOURCE_RESOURCE_ID = (
    "fin_0_1_2.common_runtime_contract_family_source"
)
FIN_0_1_2_COMMON_RUNTIME_BINDING_RESOURCE_ID = (
    "fin_0_1_2.common_runtime_contract_family_binding"
)
FIN_0_1_2_ACTUAL_CONSUMER_OWNERS = {
    "prompt": (
        "DeterministicJudgmentAtomCompiledContract."
        "provider_system_instruction"
    ),
    "server_schema": "DeterministicJudgmentAtomCompiledContract.wire_schema",
    "local_validator": "DeterministicJudgmentAtomCompiledContract.assemble",
    "fake_provider": (
        "DeterministicJudgmentAtomCompiledContract.fake_provider_output"
    ),
    "selector": "DeterministicJudgmentAtomCompiledContract.assemble",
    "renderer": "DeterministicJudgmentAtomCompiledContract.assemble",
    "capacity": (
        "DeterministicJudgmentAtomCompiledContract.capacity_declaration"
    ),
    "budget": (
        "DeterministicJudgmentAtomCompiledContract.assert_rendered_capacity"
    ),
    "typed_failure": "BoundedAgentExecutionError",
    "capture_index": (
        "DeepSeekS3ThreeCellNodeExecutor._provider_interaction_capture"
    ),
}


class Fin012RuntimeContractBindingError(ValueError):
    """Typed failure for the bounded FIN 0.1.2 family binding."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _duplicate_key_guard(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise Fin012RuntimeContractBindingError(
                f"fin012_runtime_contract_duplicate_key:{key}"
            )
        output[key] = value
    return output


def _nonblank(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Fin012RuntimeContractBindingError(code)
    return value.strip()


@dataclass(frozen=True)
class Fin012RuntimeContractFamilyBinding:
    binding_ref: str
    source_ref: str
    source_file_sha256: str
    source_digest: str
    contract_id: str
    contract_version: str
    compiled_contract_ref: str
    local_truth_fields: tuple[str, ...]
    provider_surface: str
    budget_contract: Mapping[str, int]
    failure_and_capture: Mapping[str, Any]
    compiled_consumers: tuple[Mapping[str, Any], ...]

    def consumer_receipt(self, consumer_id: str) -> dict[str, Any]:
        for row in self.compiled_consumers:
            if row["consumer_id"] == consumer_id:
                return dict(row)
        raise Fin012RuntimeContractBindingError(
            f"fin012_runtime_contract_consumer_unbound:{consumer_id}"
        )

    def all_consumer_receipts(self) -> dict[str, dict[str, Any]]:
        return {
            consumer_id: self.consumer_receipt(consumer_id)
            for consumer_id in REQUIRED_COMPILED_CONSUMERS
        }

    def assert_admission_binding(
        self,
        *,
        binding_ref: str | None,
        source_digest: str | None,
    ) -> None:
        if binding_ref != self.binding_ref:
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_admission_binding_ref_invalid"
            )
        if source_digest != self.source_digest:
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_admission_source_digest_invalid"
            )

    def assert_runtime_compatibility(
        self,
        *,
        provider_candidate_maximum: int,
        selected_maxima: tuple[int, ...],
        provider_output_max_utf8_bytes: int,
        local_rendered_max_utf8_bytes: int,
    ) -> None:
        budget = self.budget_contract
        if provider_candidate_maximum != budget[
            "provider_candidate_maximum"
        ]:
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_provider_candidate_budget_drift"
            )
        if any(
            value <= 0 or value > budget["selected_atom_maximum"]
            for value in selected_maxima
        ):
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_selected_atom_budget_drift"
            )
        if provider_output_max_utf8_bytes != budget[
            "provider_output_max_utf8_bytes"
        ]:
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_provider_output_budget_drift"
            )
        if local_rendered_max_utf8_bytes != budget[
            "local_rendered_max_utf8_bytes"
        ]:
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_local_rendered_budget_drift"
            )


def compile_fin_0_1_2_runtime_contract_binding(
    *,
    source_bytes: bytes,
    manifest: Mapping[str, Any],
) -> Fin012RuntimeContractFamilyBinding:
    if manifest.get("schema_version") != (
        "fin_ia_0_1_2_common_runtime_contract_family_binding_v1_0"
    ):
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_binding_manifest_schema_invalid"
        )
    if manifest.get("binding_ref") != FIN_0_1_2_COMMON_RUNTIME_BINDING_REF:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_binding_ref_invalid"
        )
    if manifest.get("compiled_contract_ref") != (
        FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF
    ):
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_compiled_ref_invalid"
        )
    if manifest.get("source_ref") != FIN_0_1_2_COMMON_RUNTIME_SOURCE_REF:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_source_ref_invalid"
        )
    compatibility = manifest.get("compatibility")
    if not isinstance(compatibility, Mapping):
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_compatibility_missing"
        )
    if (
        compatibility.get("FIN_0_1_2_binding_is_mandatory_for_new_contract_ref")
        is not True
        or compatibility.get("admission_optional_activation_forbidden")
        is not True
        or compatibility.get("case_specific_consumer_branch_forbidden")
        is not True
        or compatibility.get("generalized_cross_family_compiler_claimed")
        is not False
    ):
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_compatibility_boundary_invalid"
        )
    source_file_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if manifest.get("source_file_sha256") != source_file_sha256:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_source_file_digest_invalid"
        )
    try:
        source = json.loads(
            source_bytes.decode("utf-8"),
            object_pairs_hook=_duplicate_key_guard,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_source_json_invalid"
        ) from exc
    validate_runtime_contract_source(source)
    compiled = compile_runtime_contract_source(source)
    if manifest.get("source_canonical_digest") != compiled["source_digest"]:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_source_canonical_digest_invalid"
        )
    if manifest.get("contract_id") != compiled["contract_id"]:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_id_drift"
        )
    if manifest.get("contract_version") != compiled["contract_version"]:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_version_drift"
        )
    actual = manifest.get("actual_consumers")
    if not isinstance(actual, list):
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_actual_consumers_missing"
        )
    owner_by_id: dict[str, str] = {}
    for row in actual:
        if not isinstance(row, Mapping):
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_actual_consumer_invalid"
            )
        consumer_id = _nonblank(
            row.get("consumer_id"),
            "fin012_runtime_contract_actual_consumer_id_missing",
        )
        if consumer_id in owner_by_id:
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_actual_consumer_duplicate"
            )
        owner_by_id[consumer_id] = _nonblank(
            row.get("runtime_owner"),
            "fin012_runtime_contract_actual_consumer_owner_missing",
        )
        if re.search(
            r"(?:^|[^A-Za-z0-9])(DELL|MU|NVDA|ticker)(?:$|[^A-Za-z0-9])",
            owner_by_id[consumer_id],
            flags=re.IGNORECASE,
        ):
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_case_specific_consumer_forbidden"
            )
    if set(owner_by_id) != set(REQUIRED_COMPILED_CONSUMERS):
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_actual_consumer_surface_incomplete"
        )
    for consumer_id, expected_owner in (
        FIN_0_1_2_ACTUAL_CONSUMER_OWNERS.items()
    ):
        if owner_by_id.get(consumer_id) != expected_owner:
            raise Fin012RuntimeContractBindingError(
                "fin012_runtime_contract_actual_consumer_owner_drift:"
                f"{consumer_id}"
            )
    compiled_consumers = tuple(
        {
            **dict(row),
            "binding_ref": FIN_0_1_2_COMMON_RUNTIME_BINDING_REF,
            "runtime_owner": owner_by_id[str(row["consumer_id"])],
        }
        for row in compiled["compiled_consumers"]
    )
    budget = source["budget_contract"]
    return Fin012RuntimeContractFamilyBinding(
        binding_ref=FIN_0_1_2_COMMON_RUNTIME_BINDING_REF,
        source_ref=_nonblank(
            manifest.get("source_ref"),
            "fin012_runtime_contract_source_ref_missing",
        ),
        source_file_sha256=source_file_sha256,
        source_digest=str(compiled["source_digest"]),
        contract_id=str(compiled["contract_id"]),
        contract_version=str(compiled["contract_version"]),
        compiled_contract_ref=(
            FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF
        ),
        local_truth_fields=tuple(LOCAL_TRUTH_FIELDS),
        provider_surface=str(compiled["provider_surface"]),
        budget_contract={key: int(value) for key, value in budget.items()},
        failure_and_capture=dict(source["failure_and_capture"]),
        compiled_consumers=compiled_consumers,
    )


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / FIN_0_1_2_COMMON_RUNTIME_SOURCE_REF).is_file():
            return parent
    raise Fin012RuntimeContractBindingError(
        "fin012_runtime_contract_repository_root_not_found"
    )


@lru_cache(maxsize=1)
def load_fin_0_1_2_runtime_contract_binding() -> (
    Fin012RuntimeContractFamilyBinding
):
    root = _repository_root()
    try:
        manifest = read_registered_runtime_json(
            root,
            FIN_0_1_2_COMMON_RUNTIME_BINDING_RESOURCE_ID,
        )
    except RuntimeResourceRegistryError as exc:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_binding_manifest_unreadable"
        ) from exc
    try:
        source_bytes = read_registered_runtime_bytes(
            root,
            FIN_0_1_2_COMMON_RUNTIME_SOURCE_RESOURCE_ID,
        )
    except RuntimeResourceRegistryError as exc:
        raise Fin012RuntimeContractBindingError(
            "fin012_runtime_contract_source_unreadable"
        ) from exc
    return compile_fin_0_1_2_runtime_contract_binding(
        source_bytes=source_bytes,
        manifest=manifest,
    )
