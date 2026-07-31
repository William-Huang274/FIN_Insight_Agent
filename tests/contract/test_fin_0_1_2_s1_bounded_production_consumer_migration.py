from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    compile_fin_0_1_2_common_runtime_admission,
)
from apps.workbench.backend.application.deterministic_judgment_atom_contract import (
    DeterministicJudgmentAtomCompiledContract,
)
from apps.workbench.backend.application.fin_0_1_2_runtime_contract_binding import (
    FIN_0_1_2_COMMON_RUNTIME_BINDING_MANIFEST_REF,
    FIN_0_1_2_COMMON_RUNTIME_BINDING_REF,
    FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
    FIN_0_1_2_COMMON_RUNTIME_SOURCE_REF,
    FIN_0_1_2_ACTUAL_CONSUMER_OWNERS,
    Fin012RuntimeContractBindingError,
    compile_fin_0_1_2_runtime_contract_binding,
    load_fin_0_1_2_runtime_contract_binding,
)
from sec_agent.runtime_contract_governance import (
    REQUIRED_COMPILED_CONSUMERS,
    canonical_digest,
)
from test_fin_0_1_s4_t06_mu_deterministic_judgment_atom_planner_compiled_contract_implementation import (
    _CompiledAtomFake,
    _compiled_runtime,
)


SOURCE_PATH = ROOT / FIN_0_1_2_COMMON_RUNTIME_SOURCE_REF
MANIFEST_PATH = ROOT / FIN_0_1_2_COMMON_RUNTIME_BINDING_MANIFEST_REF
CAPSULE_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_stage_capsule_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CONTEXT_PATH = ROOT / "docs/project_os/current_context_pack.zh-CN.md"


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=lambda pairs: _reject_duplicate_keys(pairs),
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _fin012_runtime(ticker: str) -> tuple[Any, Any, _CompiledAtomFake]:
    input_pack, admission, fake = _compiled_runtime(ticker)
    compiled = compile_fin_0_1_2_common_runtime_admission(
        admission,
        updates={
            "admission_id": (
                f"fixture-fin012-s1-{ticker.lower()}-bounded-family-v1"
            ),
            "execution_mode": "zero_call_fin012_bounded_family_v1",
        },
    )
    return input_pack, compiled, fake


class _FirstFactUnknownAliasFake:
    def __init__(self, base: _CompiledAtomFake) -> None:
        self.base = base
        self.mutated = False

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.base.calls

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        result = dict(self.base(**kwargs))
        if self.mutated:
            return result
        request = json.loads(kwargs["messages"][1]["content"])
        contract = request.get("compiled_judgment_atom_contract")
        if (
            isinstance(contract, Mapping)
            and contract.get("family_id") == "specialist_fact_atoms"
        ):
            payload = json.loads(str(result["content"]))
            payload["fact_atoms"][0]["support_alias"] = "N-CROSS-CASE"
            result["content"] = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
            self.mutated = True
        return result


def test_default_binding_closes_all_ten_actual_consumers() -> None:
    binding = load_fin_0_1_2_runtime_contract_binding()
    assert binding.binding_ref == FIN_0_1_2_COMMON_RUNTIME_BINDING_REF
    assert binding.compiled_contract_ref == (
        FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF
    )
    assert binding.source_file_sha256 == hashlib.sha256(
        SOURCE_PATH.read_bytes()
    ).hexdigest()
    assert set(binding.all_consumer_receipts()) == set(
        REQUIRED_COMPILED_CONSUMERS
    )
    assert {
        row["source_digest"] for row in binding.compiled_consumers
    } == {binding.source_digest}
    assert {
        row["contract_version"] for row in binding.compiled_consumers
    } == {"v1.0.0"}
    assert {
        row["consumer_id"]: row["runtime_owner"]
        for row in binding.compiled_consumers
    } == FIN_0_1_2_ACTUAL_CONSUMER_OWNERS
    for method_name in (
        "provider_system_instruction",
        "wire_schema",
        "assemble",
        "fake_provider_output",
        "capacity_declaration",
        "assert_rendered_capacity",
    ):
        assert hasattr(DeterministicJudgmentAtomCompiledContract, method_name)
    assert hasattr(
        DeepSeekS3ThreeCellNodeExecutor,
        "_provider_interaction_capture",
    )
    assert BoundedAgentExecutionError.__name__ == "BoundedAgentExecutionError"


def test_stage_capsule_records_g1_without_product_or_compiler_inflation() -> None:
    capsule = _load_json(CAPSULE_PATH)
    binding = load_fin_0_1_2_runtime_contract_binding()
    assert capsule["status"] == "S1_T02_G1_pass_T03_ready"
    assert capsule["gates"]["G1_contract_closure"].startswith("pass_")
    assert capsule["gates"]["G2_deterministic_proof"] == "pending_S1_T03"
    recorded = capsule["runtime_contract_family_binding"]
    assert recorded["source_file_sha256"] == binding.source_file_sha256
    assert recorded["source_canonical_digest"] == binding.source_digest
    assert recorded["consumer_count"] == 10
    assert set(recorded["consumer_ids"]) == set(REQUIRED_COMPILED_CONSUMERS)
    assert not recorded["generalized_cross_family_compiler_claimed"]
    assert all(value == 0 for value in capsule["observed_counts"].values())
    assert not capsule["product_truth"]["DELL_R2"]
    assert not capsule["product_truth"]["MU_R2"]
    assert not capsule["product_truth"]["NVDA_R3"]
    corrections = {
        row["topic"]: row
        for row in capsule["corrections_without_historical_rewrite"]
    }
    assert corrections["capture_index_runtime_owner"][
        "actual_runtime_owner"
    ] == "DeepSeekS3ThreeCellNodeExecutor._provider_interaction_capture"
    assert corrections["source_digest_terminology"][
        "runtime_binding_digest"
    ] != corrections["source_digest_terminology"][
        "frozen_plan_source_digest_must_equal"
    ]


def test_stage_capsule_is_the_current_t03_projection() -> None:
    capsule = _load_json(CAPSULE_PATH)
    program = _load_json(PROGRAM_BACKLOG)
    s4 = _load_json(S4_BACKLOG)
    capsule_sha = hashlib.sha256(CAPSULE_PATH.read_bytes()).hexdigest()
    assert program["next_action"]["item_id"] == capsule["next_action"]
    assert program["next_action"][
        "FIN_0_1_2_S1_stage_capsule_sha256"
    ] == capsule_sha
    assert s4["current_next_action"] == capsule["next_action"]
    assert s4["FIN_0_1_2_S1_stage_plan"][
        "stage_capsule_sha256"
    ] == capsule_sha
    context = CONTEXT_PATH.read_text(encoding="utf-8")
    assert f"current next=`{capsule['next_action']}`" in context


@pytest.mark.parametrize(
    ("mutation", "failure_code"),
    [
        (
            lambda manifest: manifest.update(source_file_sha256="0" * 64),
            "source_file_digest_invalid",
        ),
        (
            lambda manifest: manifest.update(
                source_canonical_digest="0" * 64
            ),
            "source_canonical_digest_invalid",
        ),
        (
            lambda manifest: manifest["actual_consumers"].pop(),
            "actual_consumer_surface_incomplete",
        ),
        (
            lambda manifest: manifest["actual_consumers"][0].update(
                runtime_owner="if ticker DELL then prompt"
            ),
            "case_specific_consumer_forbidden",
        ),
        (
            lambda manifest: manifest["actual_consumers"][0].update(
                runtime_owner="DifferentCompiler.prompt"
            ),
            "actual_consumer_owner_drift:prompt",
        ),
        (
            lambda manifest: manifest.update(
                source_ref="configs/runtime/other.json"
            ),
            "source_ref_invalid",
        ),
        (
            lambda manifest: manifest["compatibility"].update(
                generalized_cross_family_compiler_claimed=True
            ),
            "compatibility_boundary_invalid",
        ),
    ],
)
def test_source_binding_manifest_mutations_fail_closed(
    mutation: Any,
    failure_code: str,
) -> None:
    manifest = deepcopy(_manifest())
    mutation(manifest)
    with pytest.raises(
        Fin012RuntimeContractBindingError,
        match=failure_code,
    ):
        compile_fin_0_1_2_runtime_contract_binding(
            source_bytes=SOURCE_PATH.read_bytes(),
            manifest=manifest,
        )


def test_runtime_budget_drift_fails_before_consumer_use() -> None:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    source["budget_contract"]["provider_candidate_maximum"] = 7
    source_bytes = json.dumps(
        source,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    manifest = deepcopy(_manifest())
    manifest["source_file_sha256"] = hashlib.sha256(source_bytes).hexdigest()
    manifest["source_canonical_digest"] = canonical_digest(source)
    binding = compile_fin_0_1_2_runtime_contract_binding(
        source_bytes=source_bytes,
        manifest=manifest,
    )
    with pytest.raises(
        Fin012RuntimeContractBindingError,
        match="provider_candidate_budget_drift",
    ):
        binding.assert_runtime_compatibility(
            provider_candidate_maximum=6,
            selected_maxima=(3, 2, 3),
            provider_output_max_utf8_bytes=4800,
            local_rendered_max_utf8_bytes=16384,
        )


def test_fin012_admission_omission_drift_and_old_ref_mix_fail_closed() -> None:
    _, historical, _ = _compiled_runtime("MU")
    binding = load_fin_0_1_2_runtime_contract_binding()

    missing = historical.model_copy(
        update={
            "judgment_atom_compiled_contract_ref": (
                FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF
            ),
            "provider_output_capture_policy_ref": (
                S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ),
        }
    )
    with pytest.raises(ValueError, match="admission_binding_ref_invalid"):
        missing.assert_profile_admissible()

    drift = historical.model_copy(
        update={
            "judgment_atom_compiled_contract_ref": (
                FIN_0_1_2_COMMON_RUNTIME_COMPILED_CONTRACT_REF
            ),
            "runtime_contract_family_binding_ref": binding.binding_ref,
            "runtime_contract_family_source_digest": "0" * 64,
            "provider_output_capture_policy_ref": (
                S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ),
        }
    )
    with pytest.raises(ValueError, match="admission_source_digest_invalid"):
        drift.assert_profile_admissible()

    mixed = historical.model_copy(
        update={
            "runtime_contract_family_binding_ref": binding.binding_ref,
            "runtime_contract_family_source_digest": binding.source_digest,
        }
    )
    with pytest.raises(ValueError, match="requires_fin012_contract_ref"):
        mixed.assert_profile_admissible()


def test_historical_admission_digest_payload_omits_new_unset_fields() -> None:
    _, historical, _ = _compiled_runtime("MU")
    payload = historical.digest_payload()
    assert "runtime_contract_family_binding_ref" not in payload
    assert "runtime_contract_family_source_digest" not in payload
    historical.assert_profile_admissible()


def test_compiled_surface_binds_every_consumer_and_separates_file_hash_from_digest() -> None:
    input_pack, admission, _ = _fin012_runtime("MU")
    binding = load_fin_0_1_2_runtime_contract_binding()
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=input_pack.cell_inputs[0],
        validated_segments={},
        as_of=input_pack.as_of,
        contract_ref=admission.judgment_atom_compiled_contract_ref,
        research_profile_ref=admission.research_profile_ref,
        runtime_contract_family_binding_ref=(
            admission.runtime_contract_family_binding_ref
        ),
        runtime_contract_family_source_digest=(
            admission.runtime_contract_family_source_digest
        ),
    )
    surface = compiler.compiled_surface("facts_explanation_and_terminal")
    assert surface["runtime_contract_family_binding"]["source_digest"] == (
        binding.source_digest
    )
    assert surface["runtime_contract_family_binding"][
        "source_file_sha256"
    ] == binding.source_file_sha256
    assert surface["runtime_contract_family_binding"]["source_digest"] != (
        binding.source_file_sha256
    )
    assert set(surface["compiled_consumer_bindings"]) == set(
        REQUIRED_COMPILED_CONSUMERS
    )
    assert surface["capacity"]["local_rendered_max_utf8_bytes"] == 16384
    assert surface["model_visible_contract"][
        "runtime_contract_family_binding"
    ]["consumer_id"] == "prompt"


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_production_binding_reaches_full_fake_with_capture_index(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    input_pack, admission, fake = _fin012_runtime(ticker)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": f"fixture-fin012-s1-{ticker.lower()}",
            "attempt_id": f"fixture-fin012-s1-{ticker.lower()}",
        },
    )
    binding = load_fin_0_1_2_runtime_contract_binding()
    assert len(fake.calls) == 12
    assert fake.compiled_calls == 9
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    for capture in result.provider_output_captures:
        observed = capture["runtime_contract_family_binding"]
        assert observed["source_digest"] == binding.source_digest
        assert observed["consumer_binding"]["consumer_id"] == (
            "capture_index"
        )
        assert capture["credentials_included"] is False
        assert "api_key" not in json.dumps(capture, ensure_ascii=False).lower()
    for call in fake.calls:
        contract = call["request"].get("compiled_judgment_atom_contract")
        if isinstance(contract, Mapping):
            assert contract["runtime_contract_family_binding"][
                "source_digest"
            ] == binding.source_digest


def test_post_provider_failure_keeps_capture_and_typed_failure_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, base = _fin012_runtime("MU")
    fake = _FirstFactUnknownAliasFake(base)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    with pytest.raises(BoundedAgentExecutionError) as exc_info:
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": "fixture-fin012-s1-failure",
                "attempt_id": "fixture-fin012-s1-failure",
            },
        )
    error = exc_info.value
    assert len(error.provider_output_captures) == 1
    capture_binding = error.provider_output_captures[0][
        "runtime_contract_family_binding"
    ]
    assert capture_binding["consumer_binding"]["consumer_id"] == (
        "capture_index"
    )
    failure_binding = error.failure_observation[
        "runtime_contract_family_binding"
    ]
    assert failure_binding["source_digest"] == capture_binding[
        "source_digest"
    ]
    assert failure_binding["consumer_binding"]["consumer_id"] == (
        "typed_failure"
    )
