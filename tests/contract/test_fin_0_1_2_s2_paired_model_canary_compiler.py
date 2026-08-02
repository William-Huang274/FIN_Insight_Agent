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
    S3ThreeCellBoundedAgentExecutor,
)
from apps.workbench.backend.application.fin_0_1_2_runtime_contract_binding import (
    FIN_0_1_2_COMMON_RUNTIME_BINDING_REF,
    Fin012RuntimeContractBindingError,
    load_fin_0_1_2_runtime_contract_binding,
)
from apps.workbench.backend.application.fin_0_1_2_s2_runtime_contract_binding import (
    FIN_0_1_2_S2_ACTUAL_CONSUMER_OWNERS,
    FIN_0_1_2_S2_COMMON_RUNTIME_BINDING_REF,
    FIN_0_1_2_S2_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
    FIN_0_1_2_S2_RUNTIME_RESOURCE_REGISTRY_REF,
    compile_fin_0_1_2_s2_runtime_contract_binding,
    load_fin_0_1_2_s2_runtime_contract_binding,
)
from apps.workbench.backend.application.fin_0_1_2_s2_paired_model_canary import (
    FAMILY_SEGMENTS,
    Fin012S2PairedCanaryError,
    Fin012S2PairedModelCanaryCompiler,
)
from sec_agent.runtime_contract_governance import canonical_digest
from sec_agent.runtime_resource_registry import (
    assert_no_unregistered_runtime_resource_literals,
    detect_repo_relative_runtime_resource_literals,
    load_runtime_resource_registry,
)
from test_fin_0_1_2_s1_bounded_production_consumer_migration import (
    _fin012_runtime,
)


S2_SOURCE = ROOT / (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "source_v1_1.json"
)
S2_BINDING = ROOT / (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "binding_v1_1.json"
)
S2_MODELS = ROOT / (
    "configs/runtime/fin_ia_0_1_2_s2_deepseek_model_candidate_"
    "registry_v1_0.json"
)
V1_SOURCE = ROOT / (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "source_v1_0.json"
)
T02_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t02_dual_model_route_current_"
    "contract_source_and_paired_canary_compiler_zero_call_"
    "implementation_v1_0.json"
)
CURRENT_PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_10.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _compiler(ticker: str) -> Fin012S2PairedModelCanaryCompiler:
    input_pack, admission, _ = _fin012_runtime(ticker)
    cell = S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
        input_pack.cell_inputs[0],
        policy_ref=admission.case_numeric_authority_policy_ref,
    )
    return Fin012S2PairedModelCanaryCompiler(
        cell_input=cell,
        as_of=input_pack.as_of,
        research_profile_ref=str(admission.research_profile_ref),
    )


def _mutate_content(
    response: Mapping[str, Any],
    mutation: Any,
) -> dict[str, Any]:
    changed = deepcopy(dict(response))
    output = json.loads(str(changed["content"]))
    mutation(output)
    changed["content"] = json.dumps(
        output,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return changed


def test_s2_versioned_binding_is_current_without_rewriting_v1_history() -> None:
    historical = load_fin_0_1_2_runtime_contract_binding()
    current = load_fin_0_1_2_s2_runtime_contract_binding()

    assert historical.binding_ref == FIN_0_1_2_COMMON_RUNTIME_BINDING_REF
    assert current.binding_ref == FIN_0_1_2_S2_COMMON_RUNTIME_BINDING_REF
    assert current.compiled_contract_ref == (
        FIN_0_1_2_S2_COMMON_RUNTIME_COMPILED_CONTRACT_REF
    )
    assert current.contract_version == "v1.1.0"
    assert current.source_file_sha256 == hashlib.sha256(
        S2_SOURCE.read_bytes()
    ).hexdigest()
    assert current.source_digest == canonical_digest(_load(S2_SOURCE))
    assert {
        row["consumer_id"]: row["runtime_owner"]
        for row in current.compiled_consumers
    } == FIN_0_1_2_S2_ACTUAL_CONSUMER_OWNERS
    assert hashlib.sha256(V1_SOURCE.read_bytes()).hexdigest() == (
        "b9a0e990dbf01ce11e76012c246240494cf38029b11b2c289008ae490fc2283f"
    )


def test_s2_resources_are_typed_and_digest_bound() -> None:
    registry = load_runtime_resource_registry(
        ROOT,
        FIN_0_1_2_S2_RUNTIME_RESOURCE_REGISTRY_REF,
    )
    assert len(registry.resources) == 3
    assert {row.repo_relative_path for row in registry.resources} == {
        S2_SOURCE.relative_to(ROOT).as_posix(),
        S2_BINDING.relative_to(ROOT).as_posix(),
        S2_MODELS.relative_to(ROOT).as_posix(),
    }
    detected = detect_repo_relative_runtime_resource_literals(ROOT, registry)
    assert set(detected) == {
        S2_SOURCE.relative_to(ROOT).as_posix(),
        S2_BINDING.relative_to(ROOT).as_posix(),
        FIN_0_1_2_S2_RUNTIME_RESOURCE_REGISTRY_REF,
    }
    assert assert_no_unregistered_runtime_resource_literals(
        ROOT,
        registry_ref=FIN_0_1_2_S2_RUNTIME_RESOURCE_REGISTRY_REF,
        ignored_literals=(FIN_0_1_2_S2_RUNTIME_RESOURCE_REGISTRY_REF,),
    ) == detected


def test_binding_v11_mutations_fail_closed_without_affecting_v10() -> None:
    source_bytes = S2_SOURCE.read_bytes()
    manifest = _load(S2_BINDING)

    wrong_owner = deepcopy(manifest)
    wrong_owner["actual_consumers"][1]["runtime_owner"] = (
        "LegacyExecutor.server_schema"
    )
    with pytest.raises(
        Fin012RuntimeContractBindingError,
        match="actual_consumer_owner_drift:server_schema",
    ):
        compile_fin_0_1_2_s2_runtime_contract_binding(
            source_bytes=source_bytes,
            manifest=wrong_owner,
        )

    wrong_scope = deepcopy(manifest)
    wrong_scope["compatibility"]["S2_paired_canary_only"] = False
    with pytest.raises(
        Fin012RuntimeContractBindingError,
        match=(
            "fin012_runtime_contract_profile_compatibility_invalid:"
            "S2_paired_canary_only"
        ),
    ):
        compile_fin_0_1_2_s2_runtime_contract_binding(
            source_bytes=source_bytes,
            manifest=wrong_scope,
        )

    assert load_fin_0_1_2_runtime_contract_binding().contract_version == (
        "v1.0.0"
    )


@pytest.mark.parametrize(
    ("mutation", "failure_code"),
    (
        (
            lambda registry: registry["candidates"][0].update(
                model="deepseek-v4-pro"
            ),
            "model_candidates_invalid",
        ),
        (
            lambda registry: registry["provider_route"].update(
                fallback_budget=1
            ),
            "provider_route_invalid",
        ),
        (
            lambda registry: registry["comparison"].update(
                primary_call_count=5
            ),
            "comparison_contract_invalid",
        ),
    ),
)
def test_candidate_route_and_budget_mutations_fail_closed(
    mutation: Any,
    failure_code: str,
) -> None:
    registry = _load(S2_MODELS)
    mutation(registry)
    with pytest.raises(Fin012S2PairedCanaryError, match=failure_code):
        Fin012S2PairedModelCanaryCompiler.validate_candidate_registry(
            registry
        )


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_fake_matrix_is_six_passes_with_local_identity(
    ticker: str,
) -> None:
    compiler = _compiler(ticker)
    outcomes = compiler.run_fake_matrix()

    assert len(outcomes) == 6
    assert [row["status"] for row in outcomes] == ["pass"] * 6
    assert all(row["assembled"] for row in outcomes)
    assert all(
        row["assembled"]["program_cell_id"] == compiler.program_cell_id
        for row in outcomes
    )
    assert all(
        "program_cell_id"
        not in json.loads(row["capture"]["assistant_output_text"])
        for row in outcomes
    )
    assert all(
        row["capture"]["capture_before_local_validation"] is True
        and row["capture"]["credentials_included"] is False
        and row["capture"]["business_promotable"] is False
        for row in outcomes
    )


def test_each_family_pair_has_byte_identical_model_visible_request() -> None:
    calls = _compiler("MU").compile_primary_calls()
    assert len(calls) == 6
    for family_id in FAMILY_SEGMENTS:
        pair = [call for call in calls if call.family_id == family_id]
        assert len(pair) == 2
        assert {call.candidate.model for call in pair} == {
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        }
        assert pair[0].messages == pair[1].messages
        assert pair[0].model_visible_request_digest == (
            pair[1].model_visible_request_digest
        )
        assert pair[0].request_equivalence_digest == (
            pair[1].request_equivalence_digest
        )
        assert pair[0].inference_arguments["model"] != (
            pair[1].inference_arguments["model"]
        )
        payload = json.loads(pair[0].messages[1]["content"])
        assert "program_cell_id" not in payload["required_output_schema"]
        assert payload["provider_output_program_cell_id_forbidden"] is True
        assert payload["local_prerequisite_origin"].startswith(
            "deterministic_fake_fixture"
        )


def test_fact_pair_sees_bounded_evidence_context_but_may_return_only_aliases() -> None:
    calls = _compiler("MU").compile_primary_calls()
    call = next(
        row for row in calls if row.family_id == "specialist_fact_atoms"
    )
    payload = json.loads(call.messages[1]["content"])
    supports = payload["compiled_judgment_atom_contract"][
        "allowed_supports"
    ]
    assert 1 <= len(supports) <= 6
    assert all(
        set(row["selection_context"]) == {"statement", "boundary"}
        for row in supports
    )
    assert "statement" not in json.dumps(
        payload["required_output_schema"],
        ensure_ascii=False,
    )


@pytest.mark.parametrize(
    ("ticker", "target_family", "mutation", "failure_fragment"),
    (
        (
            "DELL",
            "specialist_fact_atoms",
            lambda output: output["fact_atoms"][0].update(
                support_alias="X-CROSS-CASE"
            ),
            "fact_atom_alias_unknown_or_duplicate",
        ),
        (
            "MU",
            "claim_candidate_atoms",
            lambda output: output["claim_candidate_atoms"][0].update(
                claim_kind="insufficient_evidence"
            ),
            "claim_atom_epistemic_support_role_invalid",
        ),
        (
            "NVDA",
            "what_would_change_atoms",
            lambda output: output["what_would_change_atoms"][0].update(
                review_cadence="bound_date",
                review_date_alias="D-CROSS-CASE",
            ),
            "wwc_date_alias_unknown",
        ),
    ),
)
def test_three_case_semantic_mutations_fail_one_call_and_collect_remaining(
    ticker: str,
    target_family: str,
    mutation: Any,
    failure_fragment: str,
) -> None:
    compiler = _compiler(ticker)

    def mutate(call: Any, response: dict[str, Any]) -> Mapping[str, Any]:
        if (
            call.family_id == target_family
            and call.candidate.candidate_id == "flash_stable"
        ):
            return _mutate_content(response, mutation)
        return response

    outcomes = compiler.run_fake_matrix(mutate_response=mutate)
    failed = [row for row in outcomes if row["status"] == "failed"]
    assert len(failed) == 1
    assert failure_fragment in failed[0]["terminal_result"]["code"]
    assert failed[0]["terminal_result"]["stop_remaining_calls"] is False
    assert failed[0]["capture"]["assistant_output_text"]
    assert [row["status"] for row in outcomes].count("pass") == 5
    assert [row["status"] for row in outcomes].count("not_started") == 0


def test_provider_authored_local_identity_fails_but_does_not_abort_matrix() -> None:
    compiler = _compiler("MU")

    def mutate(call: Any, response: dict[str, Any]) -> Mapping[str, Any]:
        if call.call_id.endswith("specialist_fact_atoms-flash_stable-r1"):
            return _mutate_content(
                response,
                lambda output: output.update(
                    program_cell_id=compiler.program_cell_id
                ),
            )
        return response

    outcomes = compiler.run_fake_matrix(mutate_response=mutate)
    assert outcomes[0]["status"] == "failed"
    assert "provider_authored_local_identity:program_cell_id" in (
        outcomes[0]["terminal_result"]["code"]
    )
    assert [row["status"] for row in outcomes[1:]] == ["pass"] * 5


def test_transport_failure_stops_remaining_calls_after_capture() -> None:
    compiler = _compiler("MU")

    def mutate(call: Any, response: dict[str, Any]) -> Mapping[str, Any]:
        if call.call_id.endswith("specialist_fact_atoms-flash_stable-r1"):
            return {**response, "status": "error", "finish_reason": None}
        return response

    outcomes = compiler.run_fake_matrix(mutate_response=mutate)
    assert outcomes[0]["status"] == "failed"
    assert outcomes[0]["terminal_result"]["phase"] == "provider_transport"
    assert outcomes[0]["capture"]["assistant_output_text"]
    assert [row["status"] for row in outcomes[1:]] == ["not_started"] * 5


def test_wwc_six_valid_candidates_are_locally_selected_to_three() -> None:
    compiler = _compiler("MU")
    call = next(
        row
        for row in compiler.compile_primary_calls()
        if row.family_id == "what_would_change_atoms"
        and row.candidate.candidate_id == "flash_stable"
    )
    response = compiler.fake_provider_response(call)
    raw = json.loads(response["content"])
    assert len(raw["what_would_change_atoms"]) == 6
    outcome = compiler.materialize_response(call, response)
    assert outcome["status"] == "pass"
    assert len(outcome["assembled"]["what_would_change"]) == 3
    assert outcome["terminal_result"]["business_promotable"] is False


def test_T02_result_binds_current_implementation_and_preserves_zero_calls() -> None:
    result = _load(T02_RESULT)

    assert result["status"].startswith("pass_S2_T02_zero_call_")
    for row in result["implementation_bindings"]:
        path = ROOT / row["ref"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        assert path.stat().st_size == row["bytes"]
    assert result["verification"]["combined_contract_tests"]["failed"] == 0
    assert result["verification"]["model_calls"] == 0
    assert result["verification"]["provider_calls"] == 0
    assert result["verification"]["network_calls"] == 0
    assert result["stage_acceptance"]["S2_T02"] == "engineering_pass"
    assert result["stage_acceptance"]["S2_T03"].startswith("not_authorized")


def test_current_projection_and_backlog_route_only_to_T03_authority() -> None:
    result = _load(T02_RESULT)
    projection = _load(CURRENT_PROJECTION)
    backlog = _load(PROGRAM_BACKLOG)

    assert projection["implementation_binding"]["ref"] == (
        T02_RESULT.relative_to(ROOT).as_posix()
    )
    assert projection["implementation_binding"]["sha256"] == (
        hashlib.sha256(T02_RESULT.read_bytes()).hexdigest()
    )
    truth = projection["current_truth"]
    assert truth["S2_T02_engineering_passed"] is True
    assert truth["S2_model_canary_authorized"] is False
    assert truth["S2_model_calls"] == 0
    assert truth["current_next_action"] == result["next_action"]
    assert backlog["next_action"]["item_id"] == result["next_action"]
    assert backlog["next_action"]["current_projection_sha256"] == (
        hashlib.sha256(CURRENT_PROJECTION.read_bytes()).hexdigest()
    )
