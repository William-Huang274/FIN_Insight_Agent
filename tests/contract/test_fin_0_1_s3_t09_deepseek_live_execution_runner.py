from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.prepare_fin_ia_0_1_s3_t09_three_cell_exact_input import prepare
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    EXPECTED_ADMISSION_DIGEST,
    EXPECTED_ADMISSION_ID,
    EXPECTED_RUNTIME_ROOT_NAME,
    execute,
    load_execution_target,
    preflight,
)
from sec_agent.canonical_runtime.facade import _is_secret_safe_bounded_failure_code


ADMISSION = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_exact_admission_v1_0.json"
)
REPLACEMENT_ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_output_v2_exact_admission_v1_0.json"
)
REPLACEMENT_ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s3_t09_replacement_exact_admission_issuance_v1_0.json"
)


class _InvalidShapeFakeProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        self.calls.append(dict(kwargs))
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": json.dumps({"unexpected": "shape"}),
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "call_id": "fake-s3-live-runner-call-1",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "latency_ms": 1,
            "transport_attempt_count": 1,
            "raw_response": {
                "usage": {
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 10,
                }
            },
        }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(_sha256(path).encode("ascii"))
    return digest.hexdigest()


def test_canonical_failure_code_allowlist_is_typed_and_closed() -> None:
    assert _is_secret_safe_bounded_failure_code(
        "s3_bounded_specialist_output_schema_invalid:"
        "demand_authenticity_and_sustainability"
    )
    assert _is_secret_safe_bounded_failure_code(
        "bounded_agent_specialist_result_keys_unexpected"
    )
    assert not _is_secret_safe_bounded_failure_code("provider_error:secret-value")
    assert not _is_secret_safe_bounded_failure_code("s3_bounded_error secret-value")
    assert not _is_secret_safe_bounded_failure_code("s3_bounded_" + "x" * 300)


def test_runner_preflight_recompiles_exact_input_without_execution_state(
    tmp_path: Path, monkeypatch
) -> None:
    runtime_root = tmp_path / EXPECTED_RUNTIME_ROOT_NAME
    prepare(runtime_root)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-a-real-key")
    database_path = runtime_root / "canonical-runtime" / "canonical.sqlite"
    object_root = runtime_root / "canonical-runtime" / "objects"
    database_digest_before = _sha256(database_path)
    object_digest_before = _tree_digest(object_root)
    result = preflight(runtime_root, ADMISSION)
    assert result["status"] == "pass_exact_zero_call_execution_preflight"
    assert result["admission_id"] == EXPECTED_ADMISSION_ID
    assert result["admission_digest"] == EXPECTED_ADMISSION_DIGEST
    assert set(result["execution_state_counts_before"].values()) == {0}
    assert set(result["execution_state_counts_after"].values()) == {0}
    assert set(result["observed_counts"].values()) == {0}
    assert _sha256(database_path) == database_digest_before
    assert _tree_digest(object_root) == object_digest_before


def test_runner_output_prefix_preserves_historical_runtime_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    runtime_root = tmp_path / EXPECTED_RUNTIME_ROOT_NAME
    prepare(runtime_root)
    historical = runtime_root / "live_execution_preflight.json"
    historical.write_text('{"historical":true}\n', encoding="utf-8")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-a-real-key")

    preflight(runtime_root, ADMISSION, output_prefix="owner_grade_v3")

    assert historical.read_text(encoding="utf-8") == '{"historical":true}\n'
    assert (runtime_root / "owner_grade_v3_live_execution_preflight.json").exists()


def test_runner_wires_one_fake_call_to_terminal_failure_and_forbids_reuse(
    tmp_path: Path, monkeypatch
) -> None:
    runtime_root = tmp_path / EXPECTED_RUNTIME_ROOT_NAME
    prepare(runtime_root)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-a-real-key")
    fake = _InvalidShapeFakeProvider()
    result = execute(runtime_root, ADMISSION, chat_completion_fn=fake)
    assert len(fake.calls) == 1
    assert result["status"] == "terminal_failed_admission_consumed_no_retry"
    assert result["canonical_terminal_truth"]["work_unit_state"] == "failed"
    assert result["canonical_terminal_truth"]["attempt_state"] == "failed"
    assert result["canonical_terminal_truth"]["research_run_state"] == "failed"
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    assert {
        key: result["provider_execution"]["observed_counts"][key]
        for key in (
            "model_calls",
            "provider_calls",
            "network_calls",
            "source_network_calls",
            "external_tool_calls",
        )
    } == {
        "model_calls": 1,
        "provider_calls": 1,
        "network_calls": 1,
        "source_network_calls": 0,
        "external_tool_calls": 0,
    }
    try:
        preflight(runtime_root, ADMISSION)
    except RuntimeError as exc:
        assert str(exc) == "s3_t09_exact_execution_identity_already_consumed"
    else:
        raise AssertionError("consumed runner identity was reusable")


def test_replacement_target_allows_historical_terminal_run_and_forbids_own_reuse(
    tmp_path: Path, monkeypatch
) -> None:
    runtime_root = tmp_path / EXPECTED_RUNTIME_ROOT_NAME
    prepare(runtime_root)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-not-a-real-key")

    legacy_fake = _InvalidShapeFakeProvider()
    legacy = execute(runtime_root, ADMISSION, chat_completion_fn=legacy_fake)
    assert legacy["canonical_terminal_truth"]["research_run_state"] == "failed"

    target = load_execution_target(REPLACEMENT_ISSUANCE)
    replacement_preflight = preflight(runtime_root, REPLACEMENT_ADMISSION, target)
    assert replacement_preflight["maximum_output_tokens"] == 10200
    assert replacement_preflight["execution_state_counts_before"] == {
        "canonical_work_units": 1,
        "canonical_attempts": 1,
        "canonical_research_run_versions": 1,
        "canonical_artifact_versions": 0,
    }
    replacement_fake = _InvalidShapeFakeProvider()
    replacement = execute(
        runtime_root,
        REPLACEMENT_ADMISSION,
        chat_completion_fn=replacement_fake,
        target=target,
    )
    assert len(replacement_fake.calls) == 1
    assert replacement["identity"]["work_unit_id"] == target.work_unit_id
    assert replacement["identity"]["attempt_id"] == target.attempt_id
    assert replacement["identity"]["research_run_id"] == target.research_run_id
    assert replacement["canonical_terminal_truth"]["research_run_state"] == "failed"
    try:
        preflight(runtime_root, REPLACEMENT_ADMISSION, target)
    except RuntimeError as exc:
        assert str(exc) == "s3_t09_exact_execution_identity_already_consumed"
    else:
        raise AssertionError("consumed replacement runner identity was reusable")
