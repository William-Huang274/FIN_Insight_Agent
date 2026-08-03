from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from sec_agent.runtime_resource_registry import (
    RuntimeResourceRegistryError,
    read_registered_runtime_bytes,
    read_registered_runtime_json,
)

from .fin_0_1_2_runtime_contract_binding import (
    Fin012RuntimeContractBindingError,
    Fin012RuntimeContractBindingProfile,
    Fin012RuntimeContractFamilyBinding,
    compile_fin_0_1_2_runtime_contract_binding,
)


FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_REF = (
    "fin_0_1_2.common_runtime.judgment_atom_family_binding:v1.3"
)
FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF = (
    "fin_0_1_2.common_runtime.judgment_atom_family:v1.3.0"
)
FIN_0_1_2_S3_COMMON_RUNTIME_SOURCE_REF = (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "source_v1_3.json"
)
FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_MANIFEST_REF = (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "binding_v1_3.json"
)
FIN_0_1_2_S3_RUNTIME_RESOURCE_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s3_runtime_resource_registry_v1_0.json"
)
FIN_0_1_2_S3_COMMON_RUNTIME_SOURCE_RESOURCE_ID = (
    "fin_0_1_2.s3.common_runtime_contract_family_source"
)
FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_RESOURCE_ID = (
    "fin_0_1_2.s3.common_runtime_contract_family_binding"
)
FIN_0_1_2_S3_ACTUAL_CONSUMER_OWNERS = {
    "prompt": (
        "DeterministicJudgmentAtomCompiledContract."
        "provider_system_instruction"
    ),
    "server_schema": "DeterministicJudgmentAtomCompiledContract.wire_schema",
    "local_validator": "DeterministicJudgmentAtomCompiledContract.assemble",
    "fake_provider": (
        "DeterministicJudgmentAtomCompiledContract.fake_provider_output"
    ),
    "selector": (
        "DeterministicJudgmentAtomCompiledContract.local_fact_interaction"
    ),
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
FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_PROFILE = (
    Fin012RuntimeContractBindingProfile(
        schema_version=(
            "fin_ia_0_1_2_common_runtime_contract_family_binding_v1_3"
        ),
        binding_ref=FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_REF,
        source_ref=FIN_0_1_2_S3_COMMON_RUNTIME_SOURCE_REF,
        compiled_contract_ref=(
            FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF
        ),
        actual_consumer_owners=FIN_0_1_2_S3_ACTUAL_CONSUMER_OWNERS,
        additional_compatibility_requirements={
            "historical_v1_0_binding_remains_supported": True,
            "historical_v1_1_binding_remains_immutable": True,
            "historical_v1_2_binding_remains_immutable": True,
            "S3_production_only": True,
            "local_deterministic_Fact_required": True,
        },
    )
)


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / FIN_0_1_2_S3_RUNTIME_RESOURCE_REGISTRY_REF).is_file():
            return parent
    raise Fin012RuntimeContractBindingError(
        "fin012_s3_runtime_contract_repository_root_not_found"
    )


def compile_fin_0_1_2_s3_runtime_contract_binding(
    *, source_bytes: bytes, manifest: Mapping[str, Any]
) -> Fin012RuntimeContractFamilyBinding:
    return compile_fin_0_1_2_runtime_contract_binding(
        source_bytes=source_bytes,
        manifest=manifest,
        profile=FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_PROFILE,
    )


@lru_cache(maxsize=1)
def load_fin_0_1_2_s3_runtime_contract_binding() -> (
    Fin012RuntimeContractFamilyBinding
):
    root = _repository_root()
    try:
        manifest = read_registered_runtime_json(
            root,
            FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_RESOURCE_ID,
            registry_ref=FIN_0_1_2_S3_RUNTIME_RESOURCE_REGISTRY_REF,
        )
        source_bytes = read_registered_runtime_bytes(
            root,
            FIN_0_1_2_S3_COMMON_RUNTIME_SOURCE_RESOURCE_ID,
            registry_ref=FIN_0_1_2_S3_RUNTIME_RESOURCE_REGISTRY_REF,
        )
    except RuntimeResourceRegistryError as exc:
        raise Fin012RuntimeContractBindingError(
            "fin012_s3_runtime_contract_resource_unreadable"
        ) from exc
    return compile_fin_0_1_2_s3_runtime_contract_binding(
        source_bytes=source_bytes,
        manifest=manifest,
    )
