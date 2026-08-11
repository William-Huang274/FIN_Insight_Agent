from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (
    BUSINESS_PROJECTION_SCHEMA,
    CAPTURE_SCHEMA,
    EXECUTION_ENVELOPE_SCHEMA,
    FileCanonicalObjectStore,
    Fin012S3T03RunnerError,
    _CaptureFirstCompletion,
    _claim_execution_identity,
    build_fin_0_1_2_s3_business_input_projection,
    business_input_digest,
    compile_fresh_identity_execution_envelope,
    execute_bound_s3_t03,
    finalize_supervisor_exit,
    load_bound_s3_t03_execution_envelope,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from apps.workbench.backend.application.fin_0_1_2_s3_runtime_contract_binding import (
    load_fin_0_1_2_s3_runtime_contract_binding,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_2_s3_t02_production_runtime_integration import (
    _CurrentS3ProductionFake,
    _compiled_admission,
)
from test_fin_0_1_s3_t09_deepseek_transport_exact_input_preflight_repair import (
    _create_accepted_case,
    _prepare,
    _principal,
)


AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_"
    "execution_authority_decision_v1_0.json"
)
FRESH_IDENTITY = "fin012-s3-t03-nvda-primary-r1"


@pytest.fixture(scope="module")
def bound_inputs(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("s3-t03-bound-inputs")
    _, local, evidence, case, accepted = _create_accepted_case(root)
    tracked = _prepare(local, evidence, case, accepted)
    fresh = prepare_s3_three_cell_bounded_agent_exact_input(
        local,
        evidence,
        str(case["case_id"]),
        _principal(),
        decision_surface_contract_ref=str(accepted["contract_version_id"]),
        execution_identity=FRESH_IDENTITY,
    )
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    binding = load_fin_0_1_2_s3_runtime_contract_binding()
    envelope = compile_fresh_identity_execution_envelope(
        tracked_t02=tracked,
        fresh_t03=fresh,
        authority_ref=str(AUTHORITY.relative_to(ROOT)).replace("\\", "/"),
        authority_sha256=hashlib.sha256(AUTHORITY.read_bytes()).hexdigest(),
        runtime_contract_binding_ref=binding.binding_ref,
        runtime_contract_source_digest=binding.source_digest,
        hard_budget=authority["hard_budget"],
    )
    return tracked, fresh, envelope


def test_stable_business_projection_separates_fresh_execution_identity(bound_inputs) -> None:
    tracked, fresh, envelope = bound_inputs
    tracked_projection = build_fin_0_1_2_s3_business_input_projection(
        tracked.input_pack
    )
    fresh_projection = build_fin_0_1_2_s3_business_input_projection(
        fresh.input_pack
    )
    assert tracked_projection == fresh_projection
    assert tracked_projection["schema_version"] == BUSINESS_PROJECTION_SCHEMA
    assert business_input_digest(tracked.input_pack) == (
        "a19743ffdaa63319a5381262adc9c5b04751abadc9bc4781561c1aa905b744fc"
    )
    assert tracked.input_digest != fresh.input_digest
    assert envelope["schema_version"] == EXECUTION_ENVELOPE_SCHEMA
    assert envelope["fresh_t03"]["execution_identity"] == FRESH_IDENTITY
    assert envelope["fresh_t03"]["input_digest"] == (
        "b9cc749d0d2351e228750343a61d3fc03abfc8a70870fa96d12c8a03f118e085"
    )
    assert envelope["admission"] == {
        "issued": False,
        "persisted": False,
        "execution_enabled": False,
    }
    assert set(envelope["observed_counts"].values()) == {0}
    assert load_bound_s3_t03_execution_envelope(ROOT) == envelope


def test_business_mutations_remain_hard_bound(bound_inputs) -> None:
    tracked, fresh, _ = bound_inputs
    baseline = business_input_digest(fresh.input_pack)
    for mutate in (
        lambda row: row.update(query="mutated query"),
        lambda row: row.update(query="s3_graph_edge_projection_user_query"),
        lambda row: row["cell_inputs"][0]["authority_refs"][
            "accepted_evidence_refs"
        ].append("ev_mutation:v1"),
        lambda row: row["cell_inputs"][1]["numeric_input"].update(
            numeric_mutation="999"
        ),
    ):
        raw = fresh.input_pack.model_dump(mode="json")
        mutate(raw)
        assert business_input_digest(raw) != baseline
    mutated = fresh.model_copy(
        update={"input_pack": fresh.input_pack.model_copy(update={"query": "changed"})}
    )
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    binding = load_fin_0_1_2_s3_runtime_contract_binding()
    with pytest.raises(
        Fin012S3T03RunnerError, match="stable_business_input_mismatch"
    ):
        compile_fresh_identity_execution_envelope(
            tracked_t02=tracked,
            fresh_t03=mutated,
            authority_ref=str(AUTHORITY.relative_to(ROOT)),
            authority_sha256=hashlib.sha256(AUTHORITY.read_bytes()).hexdigest(),
            runtime_contract_binding_ref=binding.binding_ref,
            runtime_contract_source_digest=binding.source_digest,
            hard_budget=authority["hard_budget"],
        )


def test_success_persists_nine_captures_and_materializes_nine_artifacts(
    bound_inputs,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fresh, envelope = bound_inputs
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    admission = _compiled_admission(fresh)
    fake = _CurrentS3ProductionFake(safe_lead=True)
    result = execute_bound_s3_t03(
        runtime_root=tmp_path / "success",
        prepared=fresh,
        admission=admission,
        execution_envelope=envelope,
        completion=fake,
    )
    assert result["status"] == "success"
    assert result["business_promotable"]
    assert len(result["capture_objects"]) == 9
    assert len(result["artifacts"]) == 9
    assert result["terminal"]["artifact_count"] == 9
    assert len(result["terminal"]["local_fact_receipts"]) == 3
    store = FileCanonicalObjectStore(
        tmp_path / "success" / "restricted-audit-objects"
    )
    captures = [
        store.get_json(row["object_key"], expected_digest=row["digest"])
        for row in result["capture_objects"]
    ]
    assert all(row["schema_version"] == CAPTURE_SCHEMA for row in captures)
    serialized = json.dumps(captures, ensure_ascii=False)
    assert "fixture-not-a-real-secret" not in serialized
    assert "api_key_env" not in serialized
    assert "raw_response" not in serialized


def test_validation_failure_keeps_capture_and_quarantines_all_artifacts(
    bound_inputs,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fresh, envelope = bound_inputs
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    result = execute_bound_s3_t03(
        runtime_root=tmp_path / "validation-failure",
        prepared=fresh,
        admission=_compiled_admission(fresh),
        execution_envelope=envelope,
        completion=_CurrentS3ProductionFake(safe_lead=False),
    )
    assert result["status"] == "failed"
    assert len(result["capture_objects"]) == 7
    assert result["artifacts"] == []
    assert not result["business_promotable"]
    assert result["terminal"]["failed_output_quarantined"]
    assert result["terminal_object"] is not None


def test_malformed_output_is_captured_before_parse_failure(
    bound_inputs,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fresh, envelope = bound_inputs
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")

    def malformed(**kwargs: Any) -> Mapping[str, Any]:
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": "{malformed",
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
            "latency_ms": 1,
            "transport_attempt_count": 1,
        }

    result = execute_bound_s3_t03(
        runtime_root=tmp_path / "malformed",
        prepared=fresh,
        admission=_compiled_admission(fresh),
        execution_envelope=envelope,
        completion=malformed,
    )
    assert result["status"] == "failed"
    assert len(result["capture_objects"]) == 1
    store = FileCanonicalObjectStore(tmp_path / "malformed" / "restricted-audit-objects")
    capture = store.get_json(**{
        "object_key": result["capture_objects"][0]["object_key"],
        "expected_digest": result["capture_objects"][0]["digest"],
    })
    assert capture["assistant_output_text"] == "{malformed"
    assert result["artifacts"] == []


def test_transport_timeout_and_capture_store_failure_both_terminalize(
    bound_inputs,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fresh, envelope = bound_inputs
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")

    def timeout(**kwargs: Any) -> Mapping[str, Any]:
        raise TimeoutError("fixture timeout")

    timeout_result = execute_bound_s3_t03(
        runtime_root=tmp_path / "timeout",
        prepared=fresh,
        admission=_compiled_admission(fresh),
        execution_envelope=envelope,
        completion=timeout,
    )
    assert timeout_result["status"] == "failed"
    assert timeout_result["capture_objects"] == []
    assert timeout_result["terminal"]["observed_budget"]["provider_calls"] == 1

    class BrokenStore(FileCanonicalObjectStore):
        def put_json(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise OSError("fixture capture store unavailable")

    failure = execute_bound_s3_t03(
        runtime_root=tmp_path / "capture-store-failure",
        prepared=fresh,
        admission=_compiled_admission(fresh),
        execution_envelope=envelope,
        completion=_CurrentS3ProductionFake(safe_lead=True),
        object_store_factory=BrokenStore,
    )
    assert failure["status"] == "failed"
    assert failure["terminal_object"] is None
    assert (tmp_path / "capture-store-failure" / "execution-result.json").is_file()
    assert failure["artifacts"] == []


def test_supervisor_recovers_capture_after_abnormal_child_exit(
    bound_inputs,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fresh, envelope = bound_inputs
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    base = _CurrentS3ProductionFake(safe_lead=True)
    calls = 0

    def dies_after_one(**kwargs: Any) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SystemExit(17)
        return base(**kwargs)

    runtime = tmp_path / "supervisor-exit"
    with pytest.raises(SystemExit):
        execute_bound_s3_t03(
            runtime_root=runtime,
            prepared=fresh,
            admission=_compiled_admission(fresh),
            execution_envelope=envelope,
            completion=dies_after_one,
        )
    recovered = finalize_supervisor_exit(
        runtime_root=runtime,
        execution_envelope=envelope,
        exit_code=17,
        reason="fixture_abnormal_child_exit",
    )
    assert recovered["status"] == "failed"
    assert len(recovered["capture_objects"]) == 1
    assert recovered["artifacts"] == []
    assert recovered["terminal"]["supervisor_exit"]["capture_readback_verified"]
    state = json.loads((runtime / "execution-state.json").read_text(encoding="utf-8"))
    assert state["status"] == "terminal"
    assert state["terminal_materialized"]
    index = json.loads((runtime / "capture-index.json").read_text(encoding="utf-8"))
    assert index["terminal_materialized"]


def test_supervisor_scans_capture_store_when_index_lags(
    bound_inputs,
    tmp_path: Path,
) -> None:
    _, fresh, envelope = bound_inputs
    runtime = tmp_path / "lagging-index"
    _claim_execution_identity(runtime, envelope)
    store = FileCanonicalObjectStore(runtime / "restricted-audit-objects")
    capture = {
        "schema_version": CAPTURE_SCHEMA,
        "capture_sequence": 1,
        "stage": "fixture",
        "model_visible_request": [],
        "assistant_output_text": "fixture",
        "finish_reason": "stop",
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        "latency_ms": 1,
        "transport_attempt_count": 1,
        "nonsecret_inference_arguments": {},
        "capture_before_local_parse_or_validation": True,
        "credentials_included": False,
        "authorization_headers_included": False,
        "cookies_included": False,
        "private_reasoning_included": False,
        "raw_provider_response_included": False,
        "business_promotable": False,
    }
    stored = store.put_json(
        capture,
        namespace="s3-t03/restricted-provider-captures",
        artifact_type="restricted_provider_interaction_capture",
    )
    assert not (runtime / "capture-index.json").exists()
    recovered = finalize_supervisor_exit(
        runtime_root=runtime,
        execution_envelope=envelope,
        exit_code=9,
        reason="fixture_exit_between_capture_and_index",
    )
    assert recovered["capture_objects"] == [stored]
    assert recovered["terminal"]["supervisor_exit"]["capture_readback_verified"]


def test_budget_mutation_and_single_use_identity_fail_closed(
    bound_inputs,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fresh, envelope = bound_inputs
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    mutated = _compiled_admission(fresh).model_copy(update={"retry_budget": 1})
    with pytest.raises(Fin012S3T03RunnerError, match="admission_budget_mismatch"):
        execute_bound_s3_t03(
            runtime_root=tmp_path / "bad-budget",
            prepared=fresh,
            admission=mutated,
            execution_envelope=envelope,
            completion=_CurrentS3ProductionFake(safe_lead=True),
        )

    runtime = tmp_path / "single-use"
    _claim_execution_identity(runtime, envelope)
    with pytest.raises(Fin012S3T03RunnerError, match="already_claimed"):
        _claim_execution_identity(runtime, envelope)


def test_envelope_digest_rejects_mutation(bound_inputs) -> None:
    _, fresh, envelope = bound_inputs
    mutated = deepcopy(envelope)
    mutated["fresh_t03"]["input_digest"] = canonical_digest("mutation")
    with pytest.raises(Fin012S3T03RunnerError, match="envelope_digest_mismatch"):
        execute_bound_s3_t03(
            runtime_root=ROOT / ".tmp-never-created",
            prepared=fresh,
            admission=_compiled_admission(fresh),
            execution_envelope=mutated,
            completion=_CurrentS3ProductionFake(safe_lead=True),
        )


def test_two_credential_cleared_fresh_processes_rederive_identical_envelope(
    tmp_path: Path,
) -> None:
    script = r'''
from pathlib import Path
import hashlib, json, sys
root = Path(sys.argv[1])
fixture = Path(sys.argv[2])
sys.path[:0] = [str(root), str(root / "src"), str(root / "tests" / "contract")]
from test_fin_0_1_s3_t09_deepseek_transport_exact_input_preflight_repair import _create_accepted_case, _prepare, _principal
from apps.workbench.backend.application.research_runtime import prepare_s3_three_cell_bounded_agent_exact_input
from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import compile_fresh_identity_execution_envelope
from apps.workbench.backend.application.fin_0_1_2_s3_runtime_contract_binding import load_fin_0_1_2_s3_runtime_contract_binding
authority_path = root / "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_authority_decision_v1_0.json"
_, local, evidence, case, accepted = _create_accepted_case(fixture)
tracked = _prepare(local, evidence, case, accepted)
fresh = prepare_s3_three_cell_bounded_agent_exact_input(local, evidence, str(case["case_id"]), _principal(), decision_surface_contract_ref=str(accepted["contract_version_id"]), execution_identity="fin012-s3-t03-nvda-primary-r1")
authority = json.loads(authority_path.read_text(encoding="utf-8"))
binding = load_fin_0_1_2_s3_runtime_contract_binding()
envelope = compile_fresh_identity_execution_envelope(tracked_t02=tracked, fresh_t03=fresh, authority_ref=str(authority_path.relative_to(root)).replace("\\", "/"), authority_sha256=hashlib.sha256(authority_path.read_bytes()).hexdigest(), runtime_contract_binding_ref=binding.binding_ref, runtime_contract_source_digest=binding.source_digest, hard_budget=authority["hard_budget"])
print("FRESH_ENVELOPE=" + json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
'''
    env = {
        key: value
        for key, value in os.environ.items()
        if "API_KEY" not in key.upper()
        and "AUTHORIZATION" not in key.upper()
        and "COOKIE" not in key.upper()
    }
    outputs = []
    for index in (1, 2):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(ROOT),
                str(tmp_path / f"fresh-{index}"),
            ],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        line = next(
            row
            for row in completed.stdout.splitlines()
            if row.startswith("FRESH_ENVELOPE=")
        )
        outputs.append(line.removeprefix("FRESH_ENVELOPE="))
    assert outputs[0] == outputs[1]
    envelope = json.loads(outputs[0])
    assert envelope["admission"]["issued"] is False
    assert set(envelope["observed_counts"].values()) == {0}
